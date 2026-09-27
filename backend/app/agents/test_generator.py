import json
import re
import warnings
from typing import Any, Dict, List, Optional, Tuple

from app.ai.client import AIClient


# ---------------------------------------------------------------------------
# Fallback test
# ---------------------------------------------------------------------------
#
# If the AI cannot produce a safe, executable reproduction test, we deliberately
# skip the test. The execution/validation layer can then distinguish:
#
#   skipped -> test generation problem
#
# from:
#
#   failed  -> actual reproduction failure
#   passed  -> reproduction test passed
#
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


# ---------------------------------------------------------------------------
# Repository source helpers
# ---------------------------------------------------------------------------

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


def _safe_test_name(
    function_name: Optional[str],
    title: Optional[str],
) -> str:
    """
    Derive a safe pytest function name from the finding's function or title.
    """
    if function_name and function_name not in ("null", "None"):
        base = function_name
    elif title:
        base = title
    else:
        base = "unknown"

    # Keep only alphanumerics and underscores.
    safe = re.sub(r"\W+", "_", base).strip("_").lower()

    return f"test_{safe or 'finding'}_repomind"


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

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

    return f"""You are RepoMind's Test Generator — a precise automated
software reliability testing agent.

Your job is to write ONE pytest reproduction test for the bug hypothesis below.

The purpose of this test is to experimentally determine whether the suspected
bug is actually reproducible in the CURRENT repository code.

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

CRITICAL REQUIREMENTS:

1. Test the REAL implementation from the repository.

2. Import the target function or class from its real source module.

3. Do NOT redefine the target function or class inside the test.

4. Do NOT copy or simulate the implementation inside the test.

5. Call the real target implementation with inputs that reproduce
   the suspected problem.

6. The test MUST FAIL naturally when the suspected bug exists.

7. The test MUST PASS when the bug has been correctly fixed.

8. Do NOT catch the suspected exception.

9. Do NOT use try/except around the suspected failure.

10. Do NOT use pytest.raises() to catch the suspected failure.

11. Do NOT use assert True.

12. Do NOT use assert False to manufacture a failure.

13. Do NOT hide, suppress, convert, or swallow the suspected exception.

14. Do not generate a test that passes simply because the suspected
    exception occurred.

For example, if the repository contains:

    def divide(a, b):
        return a / b

and the bug hypothesis is that divide(1, 0) raises ZeroDivisionError,
the correct reproduction test is:

    from calculator import divide

    def test_divide_by_zero():
        divide(1, 0)

This test MUST naturally fail with ZeroDivisionError while the bug exists.

Do NOT generate this:

    def test_divide_by_zero():
        try:
            divide(1, 0)
        except ZeroDivisionError:
            assert True

The second version is INVALID because it passes when the bug exists.

Additional rules:
- The test function name must start with "test_".
- Use pytest only when actually necessary.
- Use only the standard library and packages already available in the
  repository.
- Do not add explanatory prose outside the code.
- If the target cannot be imported safely from the supplied repository
  context, do not invent a replacement implementation. The system will
  use its safe fallback.

Return ONLY a JSON object with this exact schema:

{{
    "test_name": "test_function_name_here",
    "test_code": "from module import function\\n\\ndef test_function_name_here():\\n    function(problematic_input)"
}}
"""


# ---------------------------------------------------------------------------
# Generated-test validation helpers
# ---------------------------------------------------------------------------

def _contains_forbidden_reproduction_pattern(test_code: str) -> Tuple[bool, str]:
    """
    Reject generated tests that can hide the suspected bug.

    A reproduction test must fail naturally when the bug exists.
    """

    # pytest.raises() catches/controls the suspected exception and therefore
    # does not provide the failure semantics RepoMind needs.
    if re.search(r"\bpytest\s*\.\s*raises\s*\(", test_code):
        return False, "uses pytest.raises() to catch the suspected failure"

    # try/except can swallow the suspected exception and turn a real bug
    # into a passing test.
    if re.search(r"\btry\s*:", test_code):
        if re.search(r"\bexcept(?:\s+[\w.]+)?\s*:", test_code):
            return False, "uses try/except around the reproduction"

    # assert True can explicitly turn the bug into a passing test.
    if re.search(r"\bassert\s+True\b", test_code, re.IGNORECASE):
        return False, "contains 'assert True'"

    # assert False can manufacture a failure unrelated to the target bug.
    if re.search(r"\bassert\s+False\b", test_code, re.IGNORECASE):
        return False, "contains 'assert False'"

    return True, ""


def _check_local_target_definition(
    test_code: str,
    function_name: Optional[str],
) -> Tuple[bool, str]:
    """
    Reject tests that redefine the target function locally.

    RepoMind must execute the repository's implementation, not a copy
    generated by the model.
    """

    if not function_name:
        return True, ""

    if function_name in ("null", "None", "unknown", ""):
        return True, ""

    fn = re.escape(function_name)

    locally_defined = bool(
        re.search(
            rf"^\s*def\s+{fn}\s*\(",
            test_code,
            re.MULTILINE,
        )
    )

    if locally_defined:
        return False, (
            f"redefines target function '{function_name}' inside the test"
        )

    return True, ""


def _check_import_safety(
    test_code: str,
    function_name: Optional[str],
) -> Tuple[bool, str]:
    """
    Perform conservative import-safety checks on generated test code.

    Returns:
        (True, "") if the code looks safe
        (False, reason) if an obvious runtime NameError/import problem exists

    Checks:
    1. pytest is referenced without being imported.
    2. The target function is called directly without being imported.
    3. The target function is not allowed to be locally redefined.
    """

    # ------------------------------------------------------------------
    # Check 1: pytest used without import
    # ------------------------------------------------------------------

    uses_pytest = bool(
        re.search(r"\bpytest\s*\.", test_code)
    )

    if uses_pytest:
        has_pytest_import = bool(
            re.search(
                r"^\s*import\s+pytest\b",
                test_code,
                re.MULTILINE,
            )
            or re.search(
                r"^\s*from\s+pytest\b",
                test_code,
                re.MULTILINE,
            )
        )

        if not has_pytest_import:
            return False, "uses pytest without 'import pytest'"

    # ------------------------------------------------------------------
    # Check 2: target function must be imported
    # ------------------------------------------------------------------

    if function_name and function_name not in (
        "null",
        "None",
        "unknown",
        "",
    ):
        fn = re.escape(function_name)

        # Detect bare calls such as:
        #
        #     divide(1, 0)
        #
        # but not:
        #
        #     obj.divide(1, 0)
        #
        called_bare = bool(
            re.search(
                rf"(?<!\.)(?<!\w){fn}\s*\(",
                test_code,
            )
        )

        if called_bare:
            imported = bool(
                re.search(
                    rf"^\s*from\s+\S+\s+import\s+.*\b{fn}\b",
                    test_code,
                    re.MULTILINE,
                )
                or re.search(
                    rf"^\s*import\s+.*\b{fn}\b",
                    test_code,
                    re.MULTILINE,
                )
            )

            if not imported:
                return False, (
                    f"calls '{function_name}' without importing it "
                    "from the repository"
                )

    return True, ""


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_test_response(
    raw: str,
    fallback_name: str,
    hypothesis: str,
    function_name: Optional[str] = None,
) -> Dict[str, str]:
    """
    Parse the model response into:

        {
            "test_name": "...",
            "test_code": "..."
        }

    Falls back to a pytest.skip() stub whenever:
    - JSON is invalid
    - test code is missing
    - no pytest test function exists
    - forbidden reproduction patterns are detected
    - target function is redefined
    - required imports are missing
    """

    fallback = {
        "test_name": fallback_name,
        "test_code": _FALLBACK_TEMPLATE.format(
            test_name=fallback_name,
            hypothesis=hypothesis or "no hypothesis provided",
        ),
    }

    if not isinstance(raw, str):
        warnings.warn(
            "Test Generator: AI response is not a string. "
            "Using fallback test.",
            stacklevel=3,
        )
        return fallback

    # Strip markdown code fences if the model accidentally returns them.
    cleaned = re.sub(
        r"```(?:json)?\s*",
        "",
        raw,
    ).strip()

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
            "Test Generator: AI response is not a JSON object. "
            "Using fallback.",
            stacklevel=3,
        )
        return fallback

    test_code = data.get("test_code", "")
    test_name = data.get("test_name") or fallback_name

    if not isinstance(test_code, str) or not test_code.strip():
        warnings.warn(
            "Test Generator: 'test_code' missing or empty. "
            "Using fallback.",
            stacklevel=3,
        )
        return fallback

    # ------------------------------------------------------------------
    # Require a real pytest test function.
    # ------------------------------------------------------------------

    if not re.search(
        r"def\s+test_\w+\s*\(",
        test_code,
    ):
        warnings.warn(
            "Test Generator: response does not contain a test function. "
            "Using fallback.",
            stacklevel=3,
        )
        return fallback

    # ------------------------------------------------------------------
    # Reject semantically invalid reproduction tests.
    # ------------------------------------------------------------------

    safe, reason = _contains_forbidden_reproduction_pattern(
        test_code
    )

    if not safe:
        warnings.warn(
            "Test Generator: invalid reproduction test — "
            f"{reason}. Using fallback.",
            stacklevel=3,
        )
        return fallback

    # ------------------------------------------------------------------
    # Reject local redefinition of the target function.
    # ------------------------------------------------------------------

    safe, reason = _check_local_target_definition(
        test_code,
        function_name,
    )

    if not safe:
        warnings.warn(
            "Test Generator: invalid reproduction test — "
            f"{reason}. Using fallback.",
            stacklevel=3,
        )
        return fallback

    # ------------------------------------------------------------------
    # Check obvious missing imports / undefined target function.
    # ------------------------------------------------------------------

    safe, reason = _check_import_safety(
        test_code,
        function_name,
    )

    if not safe:
        warnings.warn(
            "Test Generator: generated test has import safety issue — "
            f"{reason}. Using fallback.",
            stacklevel=3,
        )
        return fallback

    return {
        "test_name": str(test_name),
        "test_code": test_code,
    }


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

def generate_tests(
    repository_context: Dict[str, Any],
    findings: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Use AIClient to generate a pytest reproduction test for each finding.

    The generated test is structurally and semantically validated before
    being returned to the execution stage.
    """

    client = AIClient()
    tests: List[Dict[str, Any]] = []

    for finding in findings.get("findings", []):

        file_path = finding.get("file")
        function_name = finding.get("function")
        hypothesis = finding.get("hypothesis", "")

        source_code = _find_source_for_file(
            repository_context,
            file_path,
        )

        fallback_name = _safe_test_name(
            function_name,
            finding.get("title"),
        )

        prompt = build_test_generation_prompt(
            finding,
            source_code,
        )

        raw_response = client.generate(prompt)

        parsed = _parse_test_response(
            raw_response,
            fallback_name,
            hypothesis,
            function_name,
        )

        tests.append(
            {
                "finding_title": finding.get("title"),
                "file": file_path,
                "function": function_name,
                "hypothesis": hypothesis,
                "test_name": parsed["test_name"],
                "test_code": parsed["test_code"],
                "status": "generated",
            }
        )

    return {
        "tests": tests,
        "test_count": len(tests),
    }