import json
import re
import warnings
from typing import Any, Dict, List, Optional

from app.ai.client import AIClient

# Fallback test body used when the model response cannot be parsed or
# does not contain executable test code. Uses pytest.skip() so the
# test runner can distinguish a skipped test from a passing one.
_FALLBACK_TEMPLATE = '''\
def {test_name}():
    """
    RepoMind: test generation failed for this finding.

    Hypothesis:
    {hypothesis}
    """
    import pytest
    pytest.skip("RepoMind: AI test generation did not produce executable code.")
'''


def _find_source_for_file(
    repository_context: Dict[str, Any],
    file_path: Optional[str],
) -> str:
    """
    Return the source_code string for a given relative file path from
    the repository context, or an empty string if not found.
    """
    if not file_path:
        return ""
    for file_data in repository_context.get("files", []):
        if file_data.get("path") == file_path:
            return file_data.get("source_code", "")
    return ""


def _safe_test_name(function_name: Optional[str], title: Optional[str]) -> str:
    """Derive a safe pytest function name from the finding's function or title."""
    if function_name and function_name not in ("null", "None"):
        base = function_name
    elif title:
        base = title
    else:
        base = "unknown"

    # Keep only alphanumerics and underscores; collapse runs of non-word chars.
    safe = re.sub(r"\W+", "_", base).strip("_").lower()
    return f"test_{safe or 'finding'}_repomind"


def build_test_generation_prompt(
    finding: Dict[str, Any],
    source_code: str,
) -> str:
    """
    Build the prompt that asks the AI to produce a pytest reproduction
    test for a specific bug finding.
    """

    file_path = finding.get("file", "unknown")
    function_name = finding.get("function") or "unknown"
    title = finding.get("title", "")
    hypothesis = finding.get("hypothesis", "")
    reason = finding.get("reason", "")
    severity = finding.get("severity", "unknown")
    confidence = finding.get("confidence", 0.0)

    source_block = (
        f"```python\n{source_code.strip()}\n```"
        if source_code.strip()
        else "(source code not available)"
    )

    return f"""You are RepoMind's Test Generator — a precise automated testing agent.

Your job is to write a single pytest reproduction test for the bug hypothesis below.

Bug finding:
  Title:      {title}
  File:       {file_path}
  Function:   {function_name}
  Severity:   {severity}
  Confidence: {confidence}
  Reason:     {reason}
  Hypothesis: {hypothesis}

Source code of the relevant file:
{source_block}

Write a pytest test function that:
1. Imports the relevant function or class from the module.
2. Calls the function with inputs that should trigger the suspected failure.
3. Uses a real assertion (e.g. assert result == expected) to confirm the failure.
4. Will FAIL if the bug is present and PASS if it is fixed.

Rules:
- The test function name must start with "test_".
- Use only the standard library and pytest. Do not import third-party packages
  unless they are already imported in the source code shown above.
- Do NOT write "assert True" as the entire test body.
- Do NOT add explanatory prose — only the test code.
- If the function cannot be imported directly, simulate the logic inline.

Return ONLY a JSON object with this exact schema — no markdown, no explanation:

{{
    "test_name": "test_function_name_here",
    "test_code": "def test_function_name_here():\\n    # test body here\\n    assert ..."
}}
"""


def _parse_test_response(
    raw: str,
    fallback_name: str,
    hypothesis: str,
) -> Dict[str, str]:
    """
    Parse the model response into {test_name, test_code}.

    Falls back to a pytest.skip() stub on any parsing failure or when
    the returned code is not usable (e.g. contains only assert True).
    """

    fallback = {
        "test_name": fallback_name,
        "test_code": _FALLBACK_TEMPLATE.format(
            test_name=fallback_name,
            hypothesis=hypothesis or "no hypothesis provided",
        ),
    }

    # Strip markdown code fences.
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        warnings.warn(
            f"Test Generator: AI response is not valid JSON ({exc}). "
            "Using fallback test.",
            stacklevel=3,
        )
        return fallback

    if not isinstance(data, dict):
        warnings.warn(
            "Test Generator: AI response is not a JSON object. Using fallback.",
            stacklevel=3,
        )
        return fallback

    test_code = data.get("test_code", "")
    test_name = data.get("test_name") or fallback_name

    if not isinstance(test_code, str) or not test_code.strip():
        warnings.warn(
            "Test Generator: 'test_code' missing or empty. Using fallback.",
            stacklevel=3,
        )
        return fallback

    # Require at least one def test_ in the code.
    if not re.search(r"def\s+test_\w+\s*\(", test_code):
        warnings.warn(
            "Test Generator: response does not contain a test function. "
            "Using fallback.",
            stacklevel=3,
        )
        return fallback

    # Reject responses whose only assertion is the placeholder.
    stripped = re.sub(r"\s+", " ", test_code)
    if re.fullmatch(r".*def test_\w+\s*\(\s*\)\s*:\s*(\"\"\".*?\"\"\"\s*)?assert True\s*", stripped):
        warnings.warn(
            "Test Generator: response only contains 'assert True'. Using fallback.",
            stacklevel=3,
        )
        return fallback

    return {"test_name": test_name, "test_code": test_code}


def generate_tests(
    repository_context: Dict[str, Any],
    findings: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Use AIClient to generate a pytest reproduction test for each finding.
    """

    client = AIClient()
    tests: List[Dict[str, Any]] = []

    for finding in findings.get("findings", []):

        file_path = finding.get("file")
        function_name = finding.get("function")
        hypothesis = finding.get("hypothesis", "")

        source_code = _find_source_for_file(repository_context, file_path)
        fallback_name = _safe_test_name(function_name, finding.get("title"))

        prompt = build_test_generation_prompt(finding, source_code)
        raw_response = client.generate(prompt)
        parsed = _parse_test_response(raw_response, fallback_name, hypothesis)

        tests.append({
            "finding_title": finding.get("title"),
            "file": file_path,
            "function": function_name,
            "hypothesis": hypothesis,
            "test_name": parsed["test_name"],
            "test_code": parsed["test_code"],
            "status": "generated",
        })

    return {
        "tests": tests,
        "test_count": len(tests),
    }
