"""
Tests for the test execution + validation integration loop.

Coverage:
1. _build_env() — unit tests, no subprocess.
2. run_test()   — unit tests with mocked subprocess.
3. validate_finding() — unit tests for all four status branches.
4. Deterministic integration test using a tiny temporary Python
   repository with a deliberately reproducible bug, demonstrating
   the full:  hypothesis → test → execution → failure → validated
   pipeline without touching any AI components.

Run from the backend/ directory:

    python test_execution_validation.py
"""

import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

from app.agents.validation_agent import validate_finding
from app.executor.test_runner import _build_env, run_test


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

class _TempRepo:
    """
    Context manager that creates a temporary directory acting as a
    minimal Python repository with a single buggy module.

    Usage:
        with _TempRepo() as repo:
            repo.path        # absolute path to the temp directory
            repo.write(filename, content)
    """

    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix="repomind_integ_")
        return self

    def write(self, filename: str, content: str):
        full = os.path.join(self.path, filename)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(content))

    def __exit__(self, *_):
        shutil.rmtree(self.path, ignore_errors=True)


def _minimal_finding(**overrides):
    base = {
        "title": "Division by zero",
        "file": "calc.py",
        "function": "divide",
        "severity": "high",
        "confidence": 0.9,
        "reason": "No zero-guard.",
        "hypothesis": "divide(1, 0) raises ZeroDivisionError.",
    }
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for _build_env()
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildEnv(unittest.TestCase):

    def test_repo_path_in_pythonpath(self):
        with _TempRepo() as repo:
            env = _build_env(repo.path)
            self.assertIn(repo.path, env["PYTHONPATH"])

    def test_src_dir_added_when_present(self):
        with _TempRepo() as repo:
            src = os.path.join(repo.path, "src")
            os.makedirs(src)
            env = _build_env(repo.path)
            self.assertIn(src, env["PYTHONPATH"])

    def test_src_dir_not_added_when_absent(self):
        with _TempRepo() as repo:
            env = _build_env(repo.path)
            src = os.path.join(repo.path, "src")
            self.assertNotIn(src, env["PYTHONPATH"])

    def test_repo_path_is_first_in_pythonpath(self):
        with _TempRepo() as repo:
            env = _build_env(repo.path)
            first = env["PYTHONPATH"].split(os.pathsep)[0]
            self.assertEqual(first, repo.path)

    def test_existing_pythonpath_preserved(self):
        with _TempRepo() as repo:
            original = dict(os.environ)
            os.environ["PYTHONPATH"] = "/some/existing/path"
            try:
                env = _build_env(repo.path)
                self.assertIn("/some/existing/path", env["PYTHONPATH"])
            finally:
                if "PYTHONPATH" in original:
                    os.environ["PYTHONPATH"] = original["PYTHONPATH"]
                else:
                    os.environ.pop("PYTHONPATH", None)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for run_test() with mocked subprocess
# ─────────────────────────────────────────────────────────────────────────────

class TestRunTestUnit(unittest.TestCase):

    def _mock_run(self, returncode, stdout="", stderr=""):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        mock_result.stdout = stdout
        mock_result.stderr = stderr
        return mock_result

    def _run_with_mock(self, returncode, stdout="", stderr=""):
        with _TempRepo() as repo:
            with patch("app.executor.test_runner.subprocess.run") as mock_sub:
                mock_sub.return_value = self._mock_run(returncode, stdout, stderr)
                result = run_test("def test_x(): pass", repo.path)
        return result

    def test_returncode_0_gives_passed(self):
        result = self._run_with_mock(0)
        self.assertEqual(result["status"], "passed")

    def test_returncode_1_gives_failed(self):
        result = self._run_with_mock(1)
        self.assertEqual(result["status"], "failed")

    def test_returncode_2_gives_error_not_failed(self):
        """Collection error must NOT be reported as a test failure."""
        result = self._run_with_mock(2)
        self.assertEqual(result["status"], "error")

    def test_returncode_3_gives_error(self):
        result = self._run_with_mock(3)
        self.assertEqual(result["status"], "error")

    def test_result_contains_required_keys(self):
        result = self._run_with_mock(0)
        for key in ("status", "return_code", "stdout", "stderr"):
            self.assertIn(key, result)

    def test_timeout_gives_timeout_status(self):
        with _TempRepo() as repo:
            with patch("app.executor.test_runner.subprocess.run") as mock_sub:
                mock_sub.side_effect = __import__("subprocess").TimeoutExpired(
                    cmd="pytest", timeout=60
                )
                result = run_test("def test_x(): pass", repo.path)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["return_code"], None)

    def test_os_error_gives_error_status(self):
        with _TempRepo() as repo:
            with patch("app.executor.test_runner.subprocess.run") as mock_sub:
                mock_sub.side_effect = OSError("disk full")
                result = run_test("def test_x(): pass", repo.path)
        self.assertEqual(result["status"], "error")
        self.assertIn("disk full", result["stderr"])

    def test_temp_file_is_cleaned_up(self):
        """The temp test file must be removed even if pytest fails."""
        with _TempRepo() as repo:
            captured = {}
            original_run = __import__("subprocess").run

            def capturing_run(args, **kwargs):
                # Record the temp filename passed to pytest
                captured["test_file"] = args[3]   # index 3 = the file path
                m = MagicMock()
                m.returncode = 1
                m.stdout = ""
                m.stderr = ""
                return m

            with patch("app.executor.test_runner.subprocess.run", side_effect=capturing_run):
                run_test("def test_x(): pass", repo.path)

            if "test_file" in captured:
                self.assertFalse(os.path.exists(captured["test_file"]),
                                 "Temp test file was not deleted.")

    def test_env_passed_to_subprocess(self):
        """subprocess.run must receive the env kwarg with PYTHONPATH set."""
        with _TempRepo() as repo:
            with patch("app.executor.test_runner.subprocess.run") as mock_sub:
                mock_sub.return_value = self._mock_run(0)
                run_test("def test_x(): pass", repo.path)

            _, kwargs = mock_sub.call_args
            self.assertIn("env", kwargs)
            self.assertIn("PYTHONPATH", kwargs["env"])
            self.assertIn(repo.path, kwargs["env"]["PYTHONPATH"])


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for validate_finding()
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateFinding(unittest.TestCase):

    def test_failed_gives_validated(self):
        result = validate_finding(
            _minimal_finding(),
            {"status": "failed", "return_code": 1, "stdout": "", "stderr": ""}
        )
        self.assertEqual(result["status"], "validated")
        self.assertGreater(result["confidence"], 0.8)

    def test_passed_gives_rejected(self):
        result = validate_finding(
            _minimal_finding(),
            {"status": "passed", "return_code": 0, "stdout": "", "stderr": ""}
        )
        self.assertEqual(result["status"], "rejected")

    def test_timeout_gives_needs_review(self):
        result = validate_finding(
            _minimal_finding(),
            {"status": "timeout", "return_code": None, "stdout": "", "stderr": ""}
        )
        self.assertEqual(result["status"], "needs_review")

    def test_error_gives_needs_review(self):
        """Infrastructure error must NOT confirm a bug hypothesis."""
        result = validate_finding(
            _minimal_finding(),
            {"status": "error", "return_code": 2, "stdout": "", "stderr": "ImportError"}
        )
        self.assertEqual(result["status"], "needs_review")

    def test_validated_has_reason(self):
        result = validate_finding(
            _minimal_finding(),
            {"status": "failed", "return_code": 1, "stdout": "FAILED", "stderr": ""}
        )
        self.assertIn("reason", result)
        self.assertIsInstance(result["reason"], str)
        self.assertGreater(len(result["reason"]), 0)

    def test_rejected_has_reason(self):
        result = validate_finding(
            _minimal_finding(),
            {"status": "passed", "return_code": 0, "stdout": "1 passed", "stderr": ""}
        )
        self.assertIn("reason", result)

    def test_all_statuses_have_confidence(self):
        for status in ("failed", "passed", "timeout", "error"):
            with self.subTest(status=status):
                result = validate_finding(
                    _minimal_finding(),
                    {"status": status, "return_code": None, "stdout": "", "stderr": ""}
                )
                self.assertIn("confidence", result)
                self.assertGreaterEqual(result["confidence"], 0.0)
                self.assertLessEqual(result["confidence"], 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic integration test: hypothesis → test → execution → validation
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutionValidationLoop(unittest.TestCase):
    """
    Exercises the full execution+validation loop using a tiny temporary
    Python repository with a deliberately reproducible bug.

    The repository is created and destroyed in-process — no AI calls,
    no network, no Ollama required.
    """

    def test_failing_test_produces_validated(self):
        """
        A test that reproduces an actual bug (division by zero) must
        produce: execution.status == 'failed' → validation.status == 'validated'.
        """
        with _TempRepo() as repo:
            repo.write("calc.py", """\
                def divide(a, b):
                    return a / b
            """)

            # Reproduction test — will FAIL because divide(1, 0) raises.
            test_code = textwrap.dedent("""\
                def test_divide_by_zero_handled():
                    from calc import divide
                    result = divide(1, 0)
                    assert result == 0
            """)

            execution = run_test(test_code, repo.path)

            self.assertEqual(execution["status"], "failed",
                             f"Expected 'failed', got {execution['status']!r}. "
                             f"stdout: {execution['stdout'][:300]}")
            self.assertEqual(execution["return_code"], 1)

            validation = validate_finding(_minimal_finding(), execution)

            self.assertEqual(validation["status"], "validated")
            self.assertGreater(validation["confidence"], 0.8)

    def test_passing_test_produces_rejected(self):
        """
        A test that passes (bug is not triggered) must produce:
        execution.status == 'passed' → validation.status == 'rejected'.
        """
        with _TempRepo() as repo:
            repo.write("calc.py", """\
                def divide(a, b):
                    if b == 0:
                        return None
                    return a / b
            """)

            # This test passes because the fixed function handles zero.
            test_code = textwrap.dedent("""\
                def test_divide_safe():
                    from calc import divide
                    assert divide(10, 2) == 5.0
            """)

            execution = run_test(test_code, repo.path)
            self.assertEqual(execution["status"], "passed")

            validation = validate_finding(_minimal_finding(), execution)
            self.assertEqual(validation["status"], "rejected")

    def test_import_error_produces_error_not_failed(self):
        """
        A test that fails to collect due to a missing import must produce
        execution.status == 'error' (returncode 2), NOT 'failed' (returncode 1).
        This preserves the semantic: only returncode 1 = confirmed test failure.
        """
        with _TempRepo() as repo:
            test_code = textwrap.dedent("""\
                import nonexistent_module_xyz

                def test_something():
                    assert True
            """)

            execution = run_test(test_code, repo.path)
            self.assertEqual(execution["status"], "error",
                             f"Expected 'error', got {execution['status']!r}")

            validation = validate_finding(_minimal_finding(), execution)
            self.assertEqual(validation["status"], "needs_review",
                             "An infrastructure error must not confirm a bug hypothesis.")

    def test_flat_layout_module_importable(self):
        """
        A module at the repo root (flat layout) must be importable
        from within a generated test.
        """
        with _TempRepo() as repo:
            repo.write("utils.py", """\
                def greet(name):
                    return f"Hello, {name}!"
            """)

            test_code = textwrap.dedent("""\
                def test_greet():
                    from utils import greet
                    assert greet("world") == "Hello, world!"
            """)

            execution = run_test(test_code, repo.path)
            self.assertEqual(execution["status"], "passed",
                             f"Flat-layout import failed. stdout: {execution['stdout'][:300]}")

    def test_src_layout_module_importable(self):
        """
        A module inside src/ (src layout) must be importable
        from within a generated test.
        """
        with _TempRepo() as repo:
            repo.write("src/mylib/__init__.py", "")
            repo.write("src/mylib/math_utils.py", """\
                def square(x):
                    return x * x
            """)

            test_code = textwrap.dedent("""\
                def test_square():
                    from mylib.math_utils import square
                    assert square(4) == 16
            """)

            execution = run_test(test_code, repo.path)
            self.assertEqual(execution["status"], "passed",
                             f"src-layout import failed. stdout: {execution['stdout'][:300]}")

    def test_full_pipeline_sequence(self):
        """
        Demonstrate the complete pipeline sequence in one test:

            bug hypothesis
                ↓
            reproduction test (pre-written, not AI-generated)
                ↓
            pytest execution
                ↓
            execution.status == "failed"
                ↓
            validation.status == "validated"
        """
        # --- step 1: bug hypothesis (as generated by Bug Hunter) ---
        finding = {
            "title": "Off-by-one in paginate()",
            "file": "pagination.py",
            "function": "paginate",
            "severity": "high",
            "confidence": 0.95,
            "reason": "start = page * limit skips the first item.",
            "hypothesis": (
                "Calling paginate(items, page=1, limit=5) returns items[5:10] "
                "instead of items[0:5], so the first item is never returned."
            ),
        }

        with _TempRepo() as repo:
            # --- step 2: write the buggy module ---
            repo.write("pagination.py", """\
                def paginate(items, page, limit):
                    start = page * limit        # BUG: should be (page-1)*limit
                    return items[start:start + limit]
            """)

            # --- step 3: reproduction test (as generated by Test Generator) ---
            test_code = textwrap.dedent("""\
                def test_paginate_first_page_starts_at_index_0():
                    from pagination import paginate
                    items = list(range(20))
                    page_1 = paginate(items, page=1, limit=5)
                    # First page must start at index 0, not 5
                    assert page_1[0] == 0
            """)

            # --- step 4: execute ---
            execution = run_test(test_code, repo.path)

            # --- step 5: validate ---
            validation = validate_finding(finding, execution)

        # Assertions on the complete pipeline output
        self.assertEqual(execution["status"], "failed",
                         f"Expected test to fail (bug is present). "
                         f"stdout: {execution['stdout'][:300]}")
        self.assertEqual(validation["status"], "validated",
                         f"Expected finding to be validated. "
                         f"Validation: {validation}")
        self.assertGreater(validation["confidence"], 0.8)
        print(
            f"\n[pipeline] PASSED — finding '{finding['title']}' "
            f"validated with confidence {validation['confidence']}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
