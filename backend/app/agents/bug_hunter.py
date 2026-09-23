import json
from typing import Dict, Any


def build_bug_hunter_prompt(
    repository_context: Dict[str, Any]
) -> str:
    """
    Build the prompt used by the AI Bug Hunter.
    """

    context = json.dumps(
        repository_context,
        indent=2,
        default=str
    )

    return f"""
You are RepoMind's Bug Hunter.

Analyze the provided software repository context and identify
potential software reliability issues.

Do not report vague concerns.

For every finding:

1. Identify the file.
2. Identify the function when possible.
3. Explain the suspected issue.
4. State a concrete failure hypothesis.
5. Assign severity: low, medium, or high.
6. Provide a confidence value between 0 and 1.
7. Explain what evidence in the code led to the hypothesis.

Focus on issues that could potentially be reproduced through
execution and testing.

Repository context:

{context}

Return structured JSON with this format:

{{
    "findings": [
        {{
            "title": "...",
            "file": "...",
            "function": "...",
            "severity": "...",
            "confidence": 0.0,
            "reason": "...",
            "hypothesis": "..."
        }}
    ]
}}
"""


def generate_bug_hypotheses(
    repository_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Temporary compatibility implementation.

    Keeps the existing RepoMind pipeline working while the
    real AI provider is being connected.
    """

    findings = []

    for file_data in repository_context.get("files", []):

        analysis = file_data.get("analysis", {})

        if not analysis:
            continue

        functions = analysis.get("functions", [])

        for function in functions:

            function_name = function.get(
                "name",
                "unknown"
            )

            findings.append({
                "title": (
                    f"Review function '{function_name}'"
                ),
                "file": file_data.get("path"),
                "function": function_name,
                "severity": "low",
                "confidence": 0.30,
                "reason": (
                    "Function identified for "
                    "AI-assisted reliability analysis."
                ),
                "hypothesis": (
                    f"The function '{function_name}' "
                    "may contain an edge case that "
                    "requires validation."
                )
            })

    return {
        "findings": findings
    }