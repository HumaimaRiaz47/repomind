import os
import subprocess
import sys
import tempfile
from typing import Dict, Any

# pytest exit codes
# 0 — all tests passed
# 1 — at least one test FAILED (assertion/exception inside the test body)
# 2 — collection/infrastructure error (e.g. ImportError, syntax error)
# 3 — internal pytest error
# 4 — command-line usage error
# 5 — no tests were collected
_PYTEST_EXIT_TESTS_FAILED = 1
_PYTEST_EXIT_COLLECTION_ERROR = 2


def _build_env(repository_path: str) -> dict:
    """
    Build a subprocess environment that makes the cloned repository's
    own code importable by generated tests.

    Adds to PYTHONPATH:
    - repository_path          (flat-layout: import mymodule)
    - repository_path/src      (src-layout:  import mypackage)

    Both entries are prepended so they take priority over any
    identically-named system packages.
    """
    env = dict(os.environ)

    extra = [repository_path]

    src_dir = os.path.join(repository_path, "src")
    if os.path.isdir(src_dir):
        extra.append(src_dir)

    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        extra + ([existing] if existing else [])
    )

    return env


def run_test(test_code: str, repository_path: str) -> Dict[str, Any]:
    """
    Execute a generated pytest test inside the target repository.

    Return dict keys:
        status       — "passed" | "failed" | "error" | "timeout"
        return_code  — pytest exit code, or None on timeout/OS error
        stdout       — captured stdout
        stderr       — captured stderr

    Status semantics:
        passed  — all test assertions passed (pytest exit 0)
        failed  — a test assertion or unhandled exception inside the
                  test body caused at least one test to fail (exit 1)
        error   — the test file could not be collected or executed due
                  to an infrastructure problem such as an ImportError,
                  a syntax error, or a pytest internal error (exit 2+)
        timeout — the subprocess exceeded the 60-second time limit
    """

    test_file = None

    try:
        # Write the generated test to a temporary file inside the repo
        # so that relative imports and conftest.py files are discovered.
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix="_repomind_test.py",
            dir=repository_path,
            delete=False,
            encoding="utf-8",
        ) as file:
            file.write(test_code)
            test_file = file.name

        env = _build_env(repository_path)

        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-q", "--tb=short"],
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

        if result.returncode == 0:
            status = "passed"
        elif result.returncode == _PYTEST_EXIT_TESTS_FAILED:
            # At least one test assertion or unhandled exception in the
            # test body — this is genuine test failure evidence.
            status = "failed"
        else:
            # returncode 2  → collection error (ImportError, SyntaxError …)
            # returncode 3+ → pytest internal/usage errors
            # Treat all of these as infrastructure problems, not as
            # evidence that the bug hypothesis is confirmed.
            status = "error"

        return {
            "status": status,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "return_code": None,
            "stdout": "",
            "stderr": "Test execution timed out.",
        }

    except Exception as e:
        return {
            "status": "error",
            "return_code": None,
            "stdout": "",
            "stderr": str(e),
        }

    finally:
        if test_file and os.path.exists(test_file):
            os.remove(test_file)