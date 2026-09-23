import subprocess
import sys
from typing import Dict, Any


def run_regression_tests(
    repository_path: str
) -> Dict[str, Any]:
    """
    Run the repository's existing pytest test suite
    after a proposed fix has been applied.
    """

    try:

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q"
            ],
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:

            status = "passed"

        else:

            status = "failed"

        return {
            "status": status,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except subprocess.TimeoutExpired:

        return {
            "status": "timeout",
            "return_code": None,
            "stdout": "",
            "stderr": "Regression test suite timed out."
        }

    except Exception as e:

        return {
            "status": "error",
            "return_code": None,
            "stdout": "",
            "stderr": str(e)
        }