"""
Comprehensive tests for the Fix Agent.

Coverage:
1. _parse_fix_response()  — all parsing/validation edge cases
2. _apply_patch()         — file checks, backup, mismatch, path traversal
3. _rollback_patch()      — backup restore
4. generate_fix()         — not_applicable guard, proposed-only (no path),
                            patch applied, mocked AI responses
5. End-to-end deterministic integration — tiny temp repo with a known bug,
   verifying the complete pipeline:
       validated finding → fix generated → patch applied →
       repro test passes → regression passes → fix_verified
6. Ollama live integration test (skipped when AI_PROVIDER != "ollama")

Run from backend/:
    python test_fix_agent.py
    AI_PROVIDER=ollama python test_fix_agent.py
"""

import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
import warnings
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

from app.agents.fix_agent import (
    _apply_patch,
    _find_source,
    _parse_fix_response,
    _rollback_patch,
    build_fix_prompt,
    generate_fix,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

class _TempRepo:
    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix="repomind_fix_test_")
        return self

    def write(self, filename: str, content: str):
        full = os.path.join(self.path, filename)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(content))

    def read(self, filename: str) -> str:
        with open(os.path.join(self.path, filename), encoding="utf-8") as f:
            return f.read()

    def __exit__(self, *_):
        shutil.rmtree(self.path, ignore_errors=True)


def _minimal_finding(**overrides):
    base = {
        "title": "Division by zero",
        "file": "calc.py",
        "function": "divide",
        "severity": "high",
        "confidence": 0.95,
        "reason": "No zero-guard before division.",
        "hypothesis": "divide(1, 0) raises ZeroDivisionError.",
    }
    base.update(overrides)
    return base


def _validated():
    return {"status": "validated", "confidence": 0.95, "reason": "Test failed."}


def _rejected():
    return {"status": "rejected", "confidence": 0.9, "reason": "Test passed."}


def _minimal_context(files=None):
    return {
        "repository": {"source_file_count": 1, "has_tests": False},
        "files": files or [],
    }


def _good_fix_response(file_path="calc.py",
                        original="    return a / b",
                        fixed="    if b == 0:\n        return None\n    return a / b"):
    return json.dumps({
        "file_path": file_path,
        "explanation": "Added a zero-guard before division.",
        "original_code": original,
        "fixed_code": fixed,
        "diff": "",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for _parse_fix_response()
# ─────────────────────────────────────────────────────────────────────────────

class TestParseFixResponse(unittest.TestCase):

    def test_valid_response_returns_dict(self):
        result = _parse_fix_response(_good_fix_response())
        self.assertIsNotNone(result)
        self.assertIn("file_path", result)
        self.assertIn("original_code", result)
        self.assertIn("fixed_code", result)
        self.assertIn("explanation", result)

    def test_markdown_fence_stripped(self):
        inner = _good_fix_response()
        result = _parse_fix_response(f"```json\n{inner}\n```")
        self.assertIsNotNone(result)

    def test_invalid_json_returns_none(self):
        with warnings.catch_warnings(record=True):
            result = _parse_fix_response("not json")
        self.assertIsNone(result)

    def test_non_dict_json_returns_none(self):
        with warnings.catch_warnings(record=True):
            result = _parse_fix_response(json.dumps(["a", "b"]))
        self.assertIsNone(result)

    def test_missing_required_key_returns_none(self):
        data = json.loads(_good_fix_response())
        del data["original_code"]
        with warnings.catch_warnings(record=True):
            result = _parse_fix_response(json.dumps(data))
        self.assertIsNone(result)

    def test_empty_original_code_returns_none(self):
        data = json.loads(_good_fix_response())
        data["original_code"] = ""
        with warnings.catch_warnings(record=True):
            result = _parse_fix_response(json.dumps(data))
        self.assertIsNone(result)

    def test_empty_fixed_code_returns_none(self):
        data = json.loads(_good_fix_response())
        data["fixed_code"] = "   "
        with warnings.catch_warnings(record=True):
            result = _parse_fix_response(json.dumps(data))
        self.assertIsNone(result)

    def test_empty_explanation_returns_none(self):
        data = json.loads(_good_fix_response())
        data["explanation"] = ""
        with warnings.catch_warnings(record=True):
            result = _parse_fix_response(json.dumps(data))
        self.assertIsNone(result)

    def test_diff_field_optional(self):
        data = json.loads(_good_fix_response())
        del data["diff"]
        result = _parse_fix_response(json.dumps(data))
        self.assertIsNotNone(result)
        self.assertEqual(result["diff"], "")

    def test_diff_field_preserved_when_present(self):
        data = json.loads(_good_fix_response())
        data["diff"] = "some diff"
        result = _parse_fix_response(json.dumps(data))
        self.assertEqual(result["diff"], "some diff")


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for _apply_patch()
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyPatch(unittest.TestCase):

    BUGGY_SOURCE = "def divide(a, b):\n    return a / b\n"
    ORIGINAL = "    return a / b"
    FIXED = "    if b == 0:\n        return None\n    return a / b"

    def _fix_data(self, file_path="calc.py", original=None, fixed=None):
        return {
            "file_path": file_path,
            "explanation": "guard",
            "original_code": original or self.ORIGINAL,
            "fixed_code": fixed or self.FIXED,
            "diff": "",
        }

    def test_successful_patch_returns_applied(self):
        with _TempRepo() as repo:
            repo.write("calc.py", self.BUGGY_SOURCE)
            result = _apply_patch(repo.path, self._fix_data())
        self.assertEqual(result["status"], "applied")

    def test_patch_modifies_file(self):
        with _TempRepo() as repo:
            repo.write("calc.py", self.BUGGY_SOURCE)
            _apply_patch(repo.path, self._fix_data())
            content = repo.read("calc.py")
        self.assertIn("if b == 0", content)
        self.assertNotIn("    return a / b\n", content.split("if b == 0")[0])

    def test_backup_is_created(self):
        with _TempRepo() as repo:
            repo.write("calc.py", self.BUGGY_SOURCE)
            result = _apply_patch(repo.path, self._fix_data())
            self.assertTrue(os.path.isfile(result["backup"]))

    def test_missing_file_returns_error(self):
        with _TempRepo() as repo:
            result = _apply_patch(repo.path, self._fix_data("nonexistent.py"))
        self.assertEqual(result["status"], "error")
        self.assertIn("does not exist", result["reason"])

    def test_original_code_mismatch_returns_error(self):
        with _TempRepo() as repo:
            repo.write("calc.py", self.BUGGY_SOURCE)
            fd = self._fix_data(original="    return a * b")  # doesn't exist
            result = _apply_patch(repo.path, fd)
        self.assertEqual(result["status"], "error")
        self.assertIn("verbatim", result["reason"])

    def test_path_traversal_returns_error(self):
        with _TempRepo() as repo:
            fd = self._fix_data(file_path="../../etc/passwd")
            result = _apply_patch(repo.path, fd)
        self.assertEqual(result["status"], "error")
        self.assertIn("traversal", result["reason"])

    def test_only_first_occurrence_replaced(self):
        src = "x = 1\nx = 1\n"
        with _TempRepo() as repo:
            repo.write("dup.py", src)
            fd = {
                "file_path": "dup.py",
                "explanation": "e",
                "original_code": "x = 1",
                "fixed_code": "x = 2",
                "diff": "",
            }
            _apply_patch(repo.path, fd)
            content = repo.read("dup.py")
        self.assertEqual(content.count("x = 1"), 1)
        self.assertEqual(content.count("x = 2"), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for _rollback_patch()
# ─────────────────────────────────────────────────────────────────────────────

class TestRollbackPatch(unittest.TestCase):

    def test_rollback_restores_original(self):
        original = "def divide(a, b):\n    return a / b\n"
        with _TempRepo() as repo:
            repo.write("calc.py", original)
            patch_result = _apply_patch(repo.path, {
                "file_path": "calc.py",
                "explanation": "e",
                "original_code": "    return a / b",
                "fixed_code": "    return None",
                "diff": "",
            })
            self.assertEqual(patch_result["status"], "applied")

            # Verify the file was changed
            self.assertIn("return None", repo.read("calc.py"))

            # Rollback
            rolled_back = _rollback_patch(patch_result, repo.path)
            self.assertTrue(rolled_back)

            # File must be back to original
            self.assertEqual(repo.read("calc.py"), original)

    def test_rollback_removes_backup(self):
        with _TempRepo() as repo:
            repo.write("f.py", "x = 1\n")
            pr = _apply_patch(repo.path, {
                "file_path": "f.py",
                "explanation": "e",
                "original_code": "x = 1",
                "fixed_code": "x = 2",
                "diff": "",
            })
            _rollback_patch(pr, repo.path)
            self.assertFalse(os.path.isfile(pr["backup"]))

    def test_rollback_returns_false_on_missing_backup(self):
        result = _rollback_patch({"backup": None, "file": None}, "/some/repo")
        self.assertFalse(result)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for generate_fix() with a mocked AIClient
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateFixUnit(unittest.TestCase):

    def test_not_validated_returns_not_applicable(self):
        result = generate_fix(
            _minimal_finding(), _rejected(), _minimal_context()
        )
        self.assertEqual(result["status"], "not_applicable")

    def test_no_repository_path_returns_proposed(self):
        """Without repository_path the agent proposes but doesn't apply."""
        with patch("app.agents.fix_agent.AIClient") as MockClient:
            instance = MagicMock()
            instance.generate.return_value = _good_fix_response()
            MockClient.return_value = instance

            result = generate_fix(
                _minimal_finding(), _validated(), _minimal_context()
                # repository_path not passed
            )

        self.assertEqual(result["status"], "proposed")
        self.assertIsNotNone(result["explanation"])
        self.assertIsNone(result["patch_result"])

    def test_invalid_ai_response_returns_proposed_with_review(self):
        with patch("app.agents.fix_agent.AIClient") as MockClient:
            instance = MagicMock()
            instance.generate.return_value = "not json"
            MockClient.return_value = instance

            result = generate_fix(
                _minimal_finding(), _validated(), _minimal_context()
            )

        self.assertEqual(result["status"], "proposed")
        self.assertTrue(result["requires_review"])
        self.assertIsNone(result["original_code"])

    def test_ai_client_is_called(self):
        with patch("app.agents.fix_agent.AIClient") as MockClient:
            instance = MagicMock()
            instance.generate.return_value = _good_fix_response()
            MockClient.return_value = instance

            generate_fix(_minimal_finding(), _validated(), _minimal_context())

            MockClient.assert_called_once()
            instance.generate.assert_called_once()

    def test_prompt_contains_finding_details(self):
        finding = _minimal_finding()
        with patch("app.agents.fix_agent.AIClient") as MockClient:
            instance = MagicMock()
            instance.generate.return_value = _good_fix_response()
            MockClient.return_value = instance

            generate_fix(finding, _validated(), _minimal_context())
            call_prompt = instance.generate.call_args[0][0]

        self.assertIn(finding["title"], call_prompt)
        self.assertIn(finding["hypothesis"], call_prompt)

    def test_prompt_contains_source_code_from_context(self):
        ctx = _minimal_context(files=[
            {"path": "calc.py", "source_code": "def divide(a, b):\n    return a / b\n"}
        ])
        with patch("app.agents.fix_agent.AIClient") as MockClient:
            instance = MagicMock()
            instance.generate.return_value = _good_fix_response()
            MockClient.return_value = instance

            generate_fix(_minimal_finding(), _validated(), ctx)
            call_prompt = instance.generate.call_args[0][0]

        self.assertIn("def divide", call_prompt)

    def test_patch_file_not_found_returns_error(self):
        with _TempRepo() as repo:
            # File 'calc.py' doesn't exist in the repo
            with patch("app.agents.fix_agent.AIClient") as MockClient:
                instance = MagicMock()
                instance.generate.return_value = _good_fix_response()
                MockClient.return_value = instance

                result = generate_fix(
                    _minimal_finding(), _validated(), _minimal_context(),
                    repository_path=repo.path,
                )

        self.assertEqual(result["status"], "error")
        self.assertIn("does not exist", result["patch_result"]["reason"])

    def test_original_code_mismatch_returns_error(self):
        with _TempRepo() as repo:
            repo.write("calc.py", "def divide(a, b):\n    return a / b\n")
            # AI returns wrong original_code
            bad_fix = json.dumps({
                "file_path": "calc.py",
                "explanation": "fix",
                "original_code": "    return a * b",   # doesn't exist
                "fixed_code": "    return a / b",
                "diff": "",
            })
            with patch("app.agents.fix_agent.AIClient") as MockClient:
                instance = MagicMock()
                instance.generate.return_value = bad_fix
                MockClient.return_value = instance

                result = generate_fix(
                    _minimal_finding(), _validated(), _minimal_context(),
                    repository_path=repo.path,
                )

        self.assertEqual(result["status"], "error")


# ─────────────────────────────────────────────────────────────────────────────
# Fix-status outcome tests (mocked run_test / run_regression_tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestFixOutcomes(unittest.TestCase):
    """
    Test the fix_verified / fix_failed / regression_failed logic by mocking
    run_test and run_regression_tests so no subprocess is needed.
    """

    BUGGY_SOURCE = "def divide(a, b):\n    return a / b\n"
    ORIGINAL = "    return a / b"
    FIXED = "    if b == 0:\n        return None\n    return a / b"

    def _run(self, repro_status, regression_status, test_code="def test_x(): pass"):
        with _TempRepo() as repo:
            repo.write("calc.py", self.BUGGY_SOURCE)

            with patch("app.agents.fix_agent.AIClient") as MockClient, \
                 patch("app.agents.fix_agent.run_test") as mock_run, \
                 patch("app.agents.fix_agent.run_regression_tests") as mock_reg:

                instance = MagicMock()
                instance.generate.return_value = _good_fix_response(
                    original=self.ORIGINAL, fixed=self.FIXED
                )
                MockClient.return_value = instance

                mock_run.return_value = {
                    "status": repro_status, "return_code": 0 if repro_status == "passed" else 1,
                    "stdout": "", "stderr": "",
                }
                mock_reg.return_value = {
                    "status": regression_status, "return_code": 0 if regression_status == "passed" else 1,
                    "stdout": "", "stderr": "",
                }

                result = generate_fix(
                    _minimal_finding(), _validated(), _minimal_context(),
                    test={"test_code": test_code},
                    execution={"status": "failed", "stdout": "F", "stderr": ""},
                    repository_path=repo.path,
                )

        return result

    def test_repro_passed_and_regression_passed_gives_fix_verified(self):
        result = self._run("passed", "passed")
        self.assertEqual(result["status"], "fix_verified")
        self.assertFalse(result["requires_review"])

    def test_repro_still_fails_gives_fix_failed(self):
        result = self._run("failed", "passed")
        self.assertEqual(result["status"], "fix_failed")
        self.assertTrue(result["requires_review"])

    def test_regression_fails_gives_regression_failed(self):
        result = self._run("passed", "failed")
        self.assertEqual(result["status"], "regression_failed")
        self.assertTrue(result["requires_review"])

    def test_fix_failed_triggers_rollback(self):
        """After fix_failed the source file must be restored to the original."""
        with _TempRepo() as repo:
            original_src = self.BUGGY_SOURCE
            repo.write("calc.py", original_src)

            with patch("app.agents.fix_agent.AIClient") as MockClient, \
                 patch("app.agents.fix_agent.run_test") as mock_run, \
                 patch("app.agents.fix_agent.run_regression_tests") as mock_reg:

                instance = MagicMock()
                instance.generate.return_value = _good_fix_response(
                    original=self.ORIGINAL, fixed=self.FIXED
                )
                MockClient.return_value = instance
                mock_run.return_value = {
                    "status": "failed", "return_code": 1, "stdout": "", "stderr": ""
                }
                mock_reg.return_value = {
                    "status": "passed", "return_code": 0, "stdout": "", "stderr": ""
                }

                generate_fix(
                    _minimal_finding(), _validated(), _minimal_context(),
                    test={"test_code": "def test_x(): pass"},
                    execution={"status": "failed", "stdout": "", "stderr": ""},
                    repository_path=repo.path,
                )

            content = repo.read("calc.py")

        self.assertEqual(content, original_src,
                         "File was not rolled back after fix_failed.")

    def test_regression_failed_triggers_rollback(self):
        """After regression_failed the source file must also be restored."""
        with _TempRepo() as repo:
            original_src = self.BUGGY_SOURCE
            repo.write("calc.py", original_src)

            with patch("app.agents.fix_agent.AIClient") as MockClient, \
                 patch("app.agents.fix_agent.run_test") as mock_run, \
                 patch("app.agents.fix_agent.run_regression_tests") as mock_reg:

                instance = MagicMock()
                instance.generate.return_value = _good_fix_response(
                    original=self.ORIGINAL, fixed=self.FIXED
                )
                MockClient.return_value = instance
                mock_run.return_value = {
                    "status": "passed", "return_code": 0, "stdout": "", "stderr": ""
                }
                mock_reg.return_value = {
                    "status": "failed", "return_code": 1, "stdout": "", "stderr": ""
                }

                generate_fix(
                    _minimal_finding(), _validated(), _minimal_context(),
                    test={"test_code": "def test_x(): pass"},
                    execution={"status": "failed", "stdout": "", "stderr": ""},
                    repository_path=repo.path,
                )

            content = repo.read("calc.py")

        self.assertEqual(content, original_src,
                         "File was not rolled back after regression_failed.")

    def test_fix_verified_removes_backup(self):
        with _TempRepo() as repo:
            repo.write("calc.py", self.BUGGY_SOURCE)

            with patch("app.agents.fix_agent.AIClient") as MockClient, \
                 patch("app.agents.fix_agent.run_test") as mock_run, \
                 patch("app.agents.fix_agent.run_regression_tests") as mock_reg:

                instance = MagicMock()
                instance.generate.return_value = _good_fix_response(
                    original=self.ORIGINAL, fixed=self.FIXED
                )
                MockClient.return_value = instance
                mock_run.return_value = {
                    "status": "passed", "return_code": 0, "stdout": "", "stderr": ""
                }
                mock_reg.return_value = {
                    "status": "passed", "return_code": 0, "stdout": "", "stderr": ""
                }

                result = generate_fix(
                    _minimal_finding(), _validated(), _minimal_context(),
                    test={"test_code": "def test_x(): pass"},
                    execution={"status": "failed", "stdout": "", "stderr": ""},
                    repository_path=repo.path,
                )

            backup = result["patch_result"]["backup"]
            self.assertFalse(os.path.isfile(backup),
                             "Backup was not cleaned up after fix_verified.")


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic end-to-end integration test (no AI, no network)
# ─────────────────────────────────────────────────────────────────────────────

class TestFixAgentEndToEnd(unittest.TestCase):
    """
    Complete pipeline test using a tiny temporary repository.
    A mocked AIClient returns a pre-crafted fix so the test is
    deterministic and does not require Ollama.

    Pipeline:
        validated finding
            → AI proposes fix (mocked)
            → patch applied to file
            → reproduction test re-run (real subprocess)
            → regression suite run (real subprocess)
            → fix_verified
    """

    BUGGY_SOURCE = "def divide(a, b):\n    return a / b\n"
    FIXED_SOURCE = "def divide(a, b):\n    if b == 0:\n        return None\n    return a / b\n"
    ORIGINAL_SNIPPET = "    return a / b"
    FIXED_SNIPPET = "    if b == 0:\n        return None\n    return a / b"

    REPRO_TEST = textwrap.dedent("""\
        def test_divide_by_zero_returns_none():
            from calc import divide
            result = divide(1, 0)
            assert result is None
    """)

    REGRESSION_TEST = textwrap.dedent("""\
        def test_divide_normal():
            from calc import divide
            assert divide(10, 2) == 5.0
    """)

    def test_full_fix_pipeline(self):
        """
        Demonstrates:
            validated finding
                ↓
            fix proposed by (mocked) AI
                ↓
            patch applied to calc.py
                ↓
            reproduction test re-run → passes (bug fixed)
                ↓
            regression suite → passes (no regressions)
                ↓
            final status == "fix_verified"
        """
        with _TempRepo() as repo:
            # --- setup buggy module + regression test ---
            repo.write("calc.py", self.BUGGY_SOURCE)
            repo.write("tests/test_calc.py", self.REGRESSION_TEST)

            finding = {
                "title": "ZeroDivisionError in divide()",
                "file": "calc.py",
                "function": "divide",
                "severity": "high",
                "confidence": 0.95,
                "reason": "No zero-guard before division.",
                "hypothesis": "divide(1, 0) raises ZeroDivisionError.",
            }
            validation = {"status": "validated", "confidence": 0.95, "reason": "Test failed."}
            context = _minimal_context(files=[
                {"path": "calc.py", "source_code": self.BUGGY_SOURCE}
            ])
            test = {"test_code": self.REPRO_TEST}
            execution = {"status": "failed", "return_code": 1,
                         "stdout": "ZeroDivisionError", "stderr": ""}

            ai_fix = json.dumps({
                "file_path": "calc.py",
                "explanation": "Added a None-return guard when b == 0.",
                "original_code": self.ORIGINAL_SNIPPET,
                "fixed_code": self.FIXED_SNIPPET,
                "diff": "",
            })

            with patch("app.agents.fix_agent.AIClient") as MockClient:
                instance = MagicMock()
                instance.generate.return_value = ai_fix
                MockClient.return_value = instance

                result = generate_fix(
                    finding, validation, context,
                    test=test,
                    execution=execution,
                    repository_path=repo.path,
                )

            # ── assertions ───────────────────────────────────────────────────
            self.assertEqual(result["status"], "fix_verified",
                             f"Expected fix_verified, got {result['status']}. "
                             f"repro: {result.get('repro_result')}, "
                             f"regression: {result.get('regression')}")

            self.assertFalse(result["requires_review"])

            # The file must contain the fix
            content = repo.read("calc.py")
            self.assertIn("if b == 0", content)

            # No leftover backup file
            self.assertFalse(
                os.path.isfile(os.path.join(repo.path, "calc.py.repomind.bak"))
            )

            print(
                f"\n[e2e] PASSED — status={result['status']} | "
                f"repro={result['repro_result']['status']} | "
                f"regression={result['regression']['status']}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Live Ollama integration test
# ─────────────────────────────────────────────────────────────────────────────

class TestFixAgentOllamaIntegration(unittest.TestCase):

    def test_ollama_generates_fix_for_divide_bug(self):
        """
        Calls the real Ollama model to propose a fix for a simple
        division-by-zero bug. Verifies that:
        - AIClient is called (live)
        - A parseable fix response is returned
        - The fix contains non-empty original_code and fixed_code

        The test does NOT apply the patch (repository_path is omitted)
        to keep it fast and side-effect-free.

        Skipped when AI_PROVIDER != "ollama".
        """
        provider = os.getenv("AI_PROVIDER", "placeholder")
        if provider != "ollama":
            print("\n[ollama] SKIPPED — set AI_PROVIDER=ollama to run.")
            return

        source_code = "def divide(a, b):\n    return a / b\n"
        finding = {
            "title": "ZeroDivisionError in divide()",
            "file": "calc.py",
            "function": "divide",
            "severity": "high",
            "confidence": 0.95,
            "reason": "No zero-guard before division.",
            "hypothesis": "divide(1, 0) raises ZeroDivisionError unhandled.",
        }
        context = _minimal_context(files=[
            {"path": "calc.py", "source_code": source_code}
        ])
        test = {
            "test_code": (
                "def test_divide_by_zero():\n"
                "    from calc import divide\n"
                "    result = divide(1, 0)\n"
                "    assert result is None\n"
            )
        }
        execution = {
            "status": "failed", "return_code": 1,
            "stdout": "ZeroDivisionError: division by zero", "stderr": "",
        }

        try:
            result = generate_fix(
                finding, _validated(), context,
                test=test, execution=execution,
                # No repository_path — proposes only, does not apply
            )
        except RuntimeError as err:
            print(f"\n[ollama] SKIPPED — Ollama unavailable: {err}")
            return

        print(f"\n[ollama] status: {result['status']}")
        print(f"  explanation: {result.get('explanation', '')}")
        print(f"  original_code: {repr(result.get('original_code', ''))}")
        print(f"  fixed_code: {repr(result.get('fixed_code', ''))}")

        self.assertIn(result["status"], ("proposed",),
                      f"Unexpected status: {result['status']}")

        # If the model produced a parseable fix, verify the fields are non-empty
        if result.get("original_code"):
            self.assertTrue(result["original_code"].strip())
            self.assertTrue(result["fixed_code"].strip())
            self.assertTrue(result["explanation"].strip())


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
