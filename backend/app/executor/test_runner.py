import subprocess
import sys
import tempfile
import os
from typing import Dict, Any


def run_test(test_code: str, repository_path: str) -> Dict[str, Any]:
    """
    Execute a generated pytest test inside the target repository.
    """

    test_file = None

    try:
        # Create a temporary test file inside the repository
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix="_repomind_test.py",
            dir=repository_path,
            delete=False,
            encoding="utf-8"
        ) as file:

            file.write(test_code)
            test_file = file.name

        # Run pytest
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                test_file,
                "-q"
            ],
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=60
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
            "stderr": "Test execution timed out."
        }

    except Exception as e:
        return {
            "status": "error",
            "return_code": None,
            "stdout": "",
            "stderr": str(e)
        }

    finally:
        # Remove temporary test file
        if test_file and os.path.exists(test_file):
            os.remove(test_file)