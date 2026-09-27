import subprocess
import sys
from typing import Dict, Any

from app.executor.test_runner import _build_env

# pytest exit code 5 = no tests were collected
_PYTEST_EXIT_NO_TESTS = 5


def run_regression_tests(
    repository_path: str
) -> Dict[str, Any]:
    """
    Run the repository's existing pytest test suite
    after a proposed fix has been applied.

    Return dict keys:
        status       — "passed" | "failed" | "no_regression_tests" | "error" | "timeout"
        return_code  — pytest exit code, or None on timeout/OS error
        stdout       — captured stdout
        stderr       — captured stderr

    Status semantics:
        passed              — all tests passed (pytest exit 0)
        failed              — at least one test failed (pytest exit 1+, except 5)
        no_regression_tests — no tests were collected (pytest exit 5); the fix
                              cannot be considered regression-safe without ≥1 test
        error               — infrastructure/internal pytest error
        timeout             — subprocess exceeded the time limit
    """

    try:

        env = _build_env(repository_path)

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=short"],
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        if result.returncode == 0:
            status = "passed"
        elif result.returncode == _PYTEST_EXIT_NO_TESTS:
            status = "no_regression_tests"
        else:
            status = "failed"

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
            "stderr": "Regression test suite timed out.",
        }

    except Exception as e:

        return {
            "status": "error",
            "return_code": None,
            "stdout": "",
            "stderr": str(e),
        }