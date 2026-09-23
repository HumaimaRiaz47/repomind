from typing import Dict, Any


def validate_finding(
    finding: Dict[str, Any],
    execution_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate a bug hypothesis based on the execution result.
    """

    status = execution_result.get("status")

    if status == "failed":

        return {
            "status": "validated",
            "confidence": 0.95,
            "reason": (
                "The generated reproduction test failed during execution, "
                "providing execution evidence that the suspected issue "
                "may be reproducible."
            )
        }

    elif status == "passed":

        return {
            "status": "rejected",
            "confidence": 0.90,
            "reason": (
                "The generated reproduction test passed, so the current "
                "hypothesis was not reproduced by this test."
            )
        }

    elif status == "timeout":

        return {
            "status": "needs_review",
            "confidence": 0.50,
            "reason": (
                "The generated test exceeded the execution timeout."
            )
        }

    else:

        return {
            "status": "needs_review",
            "confidence": 0.40,
            "reason": (
                "The test could not be evaluated successfully."
            )
        }