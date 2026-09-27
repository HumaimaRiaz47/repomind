from typing import Dict, Any


def validate_finding(
    finding: Dict[str, Any],
    execution_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Validate a bug hypothesis based on the execution result.

    Execution statuses are mapped to validation decisions:

        failed
            The reproduction test actually failed. The hypothesis is
            considered validated.

        passed
            The reproduction test passed. The hypothesis is rejected.

        skipped
            The generated test did not evaluate the hypothesis.

        error
            The generated test could not be executed reliably.

        timeout
            The test did not complete within the allowed time.
    """

    status = execution_result.get("status")

    if status == "failed":
        return {
            "status": "validated",
            "confidence": 0.95,
            "reason": (
                "The generated reproduction test failed during execution, "
                "providing execution evidence that the suspected issue "
                "is reproducible."
            ),
        }

    if status == "passed":
        return {
            "status": "rejected",
            "confidence": 0.90,
            "reason": (
                "The generated reproduction test passed, so the current "
                "hypothesis was not reproduced by this test."
            ),
        }

    if status == "skipped":
        return {
            "status": "test_generation_error",
            "confidence": 0.20,
            "reason": (
                "The generated reproduction test was skipped, so the "
                "bug hypothesis was not evaluated."
            ),
        }

    if status == "error":
        return {
            "status": "test_generation_error",
            "confidence": 0.30,
            "reason": (
                "The generated test could not be collected or executed "
                "reliably because of an execution or infrastructure "
                "problem. The bug hypothesis remains unconfirmed."
            ),
        }

    if status == "timeout":
        return {
            "status": "needs_review",
            "confidence": 0.50,
            "reason": (
                "The generated test exceeded the execution timeout, "
                "so the bug hypothesis could not be reliably evaluated."
            ),
        }

    return {
        "status": "needs_review",
        "confidence": 0.40,
        "reason": (
            "The test returned an unknown execution status, so the "
            "bug hypothesis could not be evaluated reliably."
        ),
    }