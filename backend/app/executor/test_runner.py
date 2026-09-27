import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Pytest exit codes
# ---------------------------------------------------------------------------
#
# 0 = tests completed successfully
# 1 = at least one test failed
# 2 = test collection error
# 3 = internal pytest error
# 4 = command-line usage error
# 5 = no tests were collected
#
_PYTEST_EXIT_TESTS_FAILED = 1
_PYTEST_EXIT_COLLECTION_ERROR = 2
_PYTEST_EXIT_NO_TESTS = 5


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def _build_env(repository_path: str) -> dict:
    """
    Build the environment used to execute generated tests.

    The cloned repository and its optional src/ directory are placed
    at the beginning of PYTHONPATH so generated tests can import the
    repository's real implementation.
    """
    env = dict(os.environ)

    extra_paths = [repository_path]

    src_dir = os.path.join(repository_path, "src")

    if os.path.isdir(src_dir):
        extra_paths.append(src_dir)

    existing_pythonpath = env.get("PYTHONPATH", "")

    if existing_pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(
            extra_paths + [existing_pythonpath]
        )
    else:
        env["PYTHONPATH"] = os.pathsep.join(extra_paths)

    return env


# ---------------------------------------------------------------------------
# Output classification helpers
# ---------------------------------------------------------------------------

def _pytest_output_indicates_skipped(
    stdout: str,
    stderr: str,
) -> bool:
    """
    Detect a pytest run where tests were skipped.

    Pytest can return exit code 0 when a test is skipped, so exit code
    alone is not sufficient to identify a genuine passing reproduction.

    Examples detected:
        1 skipped
        2 skipped, 1 warning
    """
    output = f"{stdout}\n{stderr}".lower()

    return bool(
        re.search(r"\b\d+\s+skipped\b", output)
    )


def _pytest_output_indicates_infrastructure_error(
    stdout: str,
    stderr: str,
) -> bool:
    """
    Detect fatal Python/pytest startup or infrastructure failures.

    These must never be interpreted as evidence that the suspected
    repository bug was reproduced.
    """
    output = f"{stdout}\n{stderr}".lower()

    markers = (
        "fatal python error",
        "keyboardinterrupt",
        "error while finding module specification",
        "could not import",
        "internal error",
    )

    return any(
        marker in output
        for marker in markers
    )


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

def run_test(
    test_code: str,
    repository_path: str,
) -> Dict[str, Any]:
    """
    Execute one generated pytest reproduction test.

    Returns:

        {
            "status": "passed" | "failed" | "skipped" |
                      "error" | "timeout",

            "return_code": int | None,
            "stdout": str,
            "stderr": str,
        }

    Status meaning:

        passed
            The generated reproduction test actually passed.

        failed
            The generated reproduction test executed and failed.
            This can provide evidence that the suspected bug is
            reproducible.

        skipped
            Pytest completed but the generated test was skipped.
            This provides no evidence about the hypothesis.

        error
            The generated test could not be executed reliably because
            of collection, interpreter, pytest, import, or other
            infrastructure problems.

        timeout
            The pytest process exceeded the 60-second limit.
    """

    test_file = None

    try:
        # ---------------------------------------------------------------
        # Create temporary test file inside the repository
        # ---------------------------------------------------------------

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix="_repomind_test.py",
            dir=repository_path,
            delete=False,
            encoding="utf-8",
        ) as file:
            file.write(test_code)
            test_file = file.name

        # ---------------------------------------------------------------
        # Build execution environment
        # ---------------------------------------------------------------

        env = _build_env(repository_path)

        # ---------------------------------------------------------------
        # Subprocess configuration
        # ---------------------------------------------------------------
        #
        # On Windows, CREATE_NEW_PROCESS_GROUP prevents the pytest
        # subprocess from sharing the parent's console process group.
        #
        # stdin=DEVNULL prevents pytest from waiting for interactive
        # input.
        #

        run_kwargs: Dict[str, Any] = {
            "cwd": repository_path,
            "capture_output": True,
            "text": True,
            "timeout": 60,
            "env": env,
            "stdin": subprocess.DEVNULL,
        }

        if os.name == "nt":
            run_kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
            )

        # ---------------------------------------------------------------
        # Execute pytest
        # ---------------------------------------------------------------

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                test_file,
                "-q",
                "--tb=short",
            ],
            **run_kwargs,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        # ---------------------------------------------------------------
        # Classify result
        # ---------------------------------------------------------------

        # First detect fatal infrastructure/interpreter problems.
        # These must take priority over exit code 1.
        if _pytest_output_indicates_infrastructure_error(
            stdout,
            stderr,
        ):
            status = "error"

        # Pytest exit code 0 can mean either:
        #   - genuine passing test
        #   - skipped test
        elif result.returncode == 0:

            if _pytest_output_indicates_skipped(
                stdout,
                stderr,
            ):
                status = "skipped"
            else:
                status = "passed"

        # Exit code 1 means an executed test failed.
        elif result.returncode == _PYTEST_EXIT_TESTS_FAILED:
            status = "failed"

        # Exit code 5 means no tests were collected.
        elif result.returncode == _PYTEST_EXIT_NO_TESTS:
            status = "error"

        # Exit code 2+ represents collection/internal/usage/etc.
        else:
            status = "error"

        return {
            "status": status,
            "return_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    # ---------------------------------------------------------------
    # Timeout
    # ---------------------------------------------------------------

    except subprocess.TimeoutExpired as exc:
        stdout = ""

        stderr = "Test execution timed out after 60 seconds."

        if exc.stdout:
            if isinstance(exc.stdout, bytes):
                stdout = exc.stdout.decode(
                    "utf-8",
                    errors="replace",
                )
            else:
                stdout = exc.stdout

        if exc.stderr:
            if isinstance(exc.stderr, bytes):
                stderr += "\n" + exc.stderr.decode(
                    "utf-8",
                    errors="replace",
                )
            else:
                stderr += "\n" + exc.stderr

        return {
            "status": "timeout",
            "return_code": None,
            "stdout": stdout,
            "stderr": stderr,
        }

    # ---------------------------------------------------------------
    # Any unexpected OS/runtime problem
    # ---------------------------------------------------------------

    except Exception as exc:
        return {
            "status": "error",
            "return_code": None,
            "stdout": "",
            "stderr": str(exc),
        }

    # ---------------------------------------------------------------
    # Always remove temporary test file
    # ---------------------------------------------------------------

    finally:
        if test_file and os.path.exists(test_file):
            try:
                os.remove(test_file)
            except OSError:
                # Cleanup failure should not replace the actual test
                # execution result.
                pass