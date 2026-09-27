import json
import os
import re
import shutil
import warnings
from typing import Any, Dict, List, Optional

from app.ai.client import AIClient
from app.executor.test_runner import run_test
from app.executor.regression_runner import run_regression_tests

# Required keys every AI fix response must contain.
_REQUIRED_FIX_KEYS = {"file_path", "explanation", "original_code", "fixed_code"}


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_fix_prompt(
    finding: Dict[str, Any],
    validation: Dict[str, Any],
    source_code: str,
    test_code: str,
    execution_output: str,
) -> str:
    """
    Build the prompt that asks the AI to propose a minimal source-code fix.
    """

    file_path = finding.get("file", "unknown")
    function_name = finding.get("function") or "unknown"
    title = finding.get("title", "")
    hypothesis = finding.get("hypothesis", "")
    reason = finding.get("reason", "")
    severity = finding.get("severity", "unknown")

    source_block = (
        f"```python\n{source_code.strip()}\n```"
        if source_code.strip()
        else "(source code not available)"
    )

    test_block = (
        f"```python\n{test_code.strip()}\n```"
        if test_code.strip()
        else "(test code not available)"
    )

    output_block = execution_output.strip() or "(no output captured)"

    return f"""You are RepoMind's Fix Agent — a precise automated code repair agent.

A bug has been confirmed by a failing reproduction test. Your job is to propose
the minimal source-code change that fixes the bug without altering unrelated logic.

Bug finding:
  Title:      {title}
  File:       {file_path}
  Function:   {function_name}
  Severity:   {severity}
  Reason:     {reason}
  Hypothesis: {hypothesis}

Current source code of {file_path}:
{source_block}

Reproduction test (this test currently FAILS):
{test_block}

Test failure output:
```
{output_block}
```

Rules:
- Propose the MINIMAL change that fixes the bug.
- Do not refactor, rename, or reformat unrelated code.
- The fix must make the reproduction test PASS.
- Only modify the file shown above.
- original_code must be an exact substring of the current source.
- fixed_code is the replacement for that exact substring.

Return ONLY a JSON object — no explanation, no markdown, no extra text:

{{
    "file_path": "{file_path}",
    "explanation": "one sentence describing what was changed and why",
    "original_code": "exact lines to replace (must exist verbatim in the file)",
    "fixed_code": "replacement lines",
    "diff": "optional unified diff or empty string"
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Response parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_fix_response(raw: str) -> Optional[Dict[str, Any]]:
    """
    Parse the AI fix response.

    Returns a validated dict on success, or None on any failure.
    Handles markdown fences, invalid JSON, and missing/empty fields.
    """

    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        warnings.warn(
            f"Fix Agent: AI response is not valid JSON ({exc}).",
            stacklevel=3,
        )
        return None

    if not isinstance(data, dict):
        warnings.warn("Fix Agent: AI response is not a JSON object.", stacklevel=3)
        return None

    missing = _REQUIRED_FIX_KEYS - data.keys()
    if missing:
        warnings.warn(
            f"Fix Agent: AI response missing required keys: {missing}.",
            stacklevel=3,
        )
        return None

    for key in ("original_code", "fixed_code", "explanation", "file_path"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            warnings.warn(
                f"Fix Agent: field '{key}' is empty or not a string.",
                stacklevel=3,
            )
            return None

    # Normalise optional diff field
    if "diff" not in data:
        data["diff"] = ""

    return data


# ─────────────────────────────────────────────────────────────────────────────
# Safe patch application
# ─────────────────────────────────────────────────────────────────────────────

def _apply_patch(
    repository_path: str,
    fix_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply the fix to the target file inside the repository.

    Safety checks:
    1. The target file must exist relative to repository_path.
    2. original_code must appear verbatim in the file.
    3. A .bak backup is created before any modification.
    4. Only the first occurrence of original_code is replaced.

    Returns a dict describing the patch result.
    """

    file_path = fix_data["file_path"]
    original_code = fix_data["original_code"]
    fixed_code = fix_data["fixed_code"]

    # Resolve the absolute path safely (prevent path traversal)
    abs_path = os.path.normpath(os.path.join(repository_path, file_path))
    if not abs_path.startswith(os.path.normpath(repository_path)):
        return {
            "status": "error",
            "reason": f"Path traversal detected: '{file_path}' is outside the repository.",
        }

    if not os.path.isfile(abs_path):
        return {
            "status": "error",
            "reason": f"Target file does not exist: '{file_path}'.",
        }

    with open(abs_path, "r", encoding="utf-8") as fh:
        current_content = fh.read()

    if original_code not in current_content:
        return {
            "status": "error",
            "reason": (
                "original_code does not appear verbatim in the target file. "
                "The file may have changed, or the AI produced an incorrect snippet."
            ),
        }

    # Create a backup before modifying.
    backup_path = abs_path + ".repomind.bak"
    shutil.copy2(abs_path, backup_path)

    new_content = current_content.replace(original_code, fixed_code, 1)

    with open(abs_path, "w", encoding="utf-8") as fh:
        fh.write(new_content)

    return {
        "status": "applied",
        "file": file_path,
        "backup": backup_path,
    }


def _rollback_patch(patch_result: Dict[str, Any], repository_path: str) -> bool:
    """
    Restore the backup created by _apply_patch.
    Returns True if rollback succeeded, False otherwise.
    """
    backup = patch_result.get("backup")
    file_path = patch_result.get("file")
    if not backup or not file_path:
        return False
    abs_path = os.path.normpath(os.path.join(repository_path, file_path))
    if os.path.isfile(backup):
        shutil.copy2(backup, abs_path)
        os.remove(backup)
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Source lookup helper
# ─────────────────────────────────────────────────────────────────────────────

def _find_source(
    repository_context: Dict[str, Any],
    file_path: Optional[str],
) -> str:
    """Return source_code for file_path from the repository context."""
    if not file_path:
        return ""
    for file_data in repository_context.get("files", []):
        if file_data.get("path") == file_path:
            return file_data.get("source_code", "")
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────────────────────

def generate_fix(
    finding: Dict[str, Any],
    validation: Dict[str, Any],
    repository_context: Dict[str, Any],
    *,
    test: Optional[Dict[str, Any]] = None,
    execution: Optional[Dict[str, Any]] = None,
    repository_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate and apply a minimal source-code fix for a validated finding.

    Parameters
    ----------
    finding            — bug hypothesis from Bug Hunter
    validation         — result from Validation Agent (must be "validated")
    repository_context — full repository context from context_builder
    test               — test dict from Test Generator (optional)
    execution          — execution result from test_runner (optional)
    repository_path    — absolute path to the cloned repository (optional;
                         required for patch application and regression)

    Returns a dict with:
        status  — "not_applicable" | "proposed" | "applied" | "fix_verified"
                  | "fix_failed" | "regression_failed" | "no_regression_tests"
                  | "needs_review" | "error"
        ...     — additional fields describing the fix and its outcome
    """

    # ── Guard: only fix validated findings ───────────────────────────────────
    if validation.get("status") != "validated":
        return {
            "status": "not_applicable",
            "reason": "The finding was not validated, so no fix is proposed.",
        }

    file_path = finding.get("file")
    source_code = _find_source(repository_context, file_path)
    test_code = (test or {}).get("test_code", "")
    execution_output = (
        (execution or {}).get("stdout", "")
        + "\n"
        + (execution or {}).get("stderr", "")
    ).strip()

    # ── Step 1: Ask AI for a fix ──────────────────────────────────────────────
    client = AIClient()
    prompt = build_fix_prompt(
        finding, validation, source_code, test_code, execution_output
    )
    raw_response = client.generate(prompt)
    fix_data = _parse_fix_response(raw_response)

    if fix_data is None:
        return {
            "status": "proposed",
            "file": file_path,
            "function": finding.get("function"),
            "explanation": "AI response could not be parsed.",
            "original_code": None,
            "fixed_code": None,
            "diff": None,
            "patch_result": None,
            "requires_review": True,
        }

    # ── Step 2: Apply the patch (only if repository_path is known) ───────────
    if not repository_path:
        # No path provided — return the proposal without applying.
        return {
            "status": "proposed",
            "file": fix_data["file_path"],
            "function": finding.get("function"),
            "explanation": fix_data["explanation"],
            "original_code": fix_data["original_code"],
            "fixed_code": fix_data["fixed_code"],
            "diff": fix_data.get("diff", ""),
            "patch_result": None,
            "requires_review": True,
        }

    patch_result = _apply_patch(repository_path, fix_data)

    if patch_result["status"] != "applied":
        return {
            "status": "error",
            "file": fix_data["file_path"],
            "explanation": fix_data["explanation"],
            "original_code": fix_data["original_code"],
            "fixed_code": fix_data["fixed_code"],
            "diff": fix_data.get("diff", ""),
            "patch_result": patch_result,
            "requires_review": True,
        }

    # ── Step 3: Re-run the reproduction test ─────────────────────────────────
    if test_code:
        repro_result = run_test(test_code, repository_path)
    else:
        repro_result = {"status": "skipped", "return_code": None,
                        "stdout": "", "stderr": "No test provided."}

    # ── Step 4: Run regression suite ─────────────────────────────────────────
    regression = run_regression_tests(repository_path)

    # ── Step 5: Determine fix status ─────────────────────────────────────────
    repro_status = repro_result.get("status")
    regression_status = regression.get("status")

    if repro_status == "passed" and regression_status == "passed":
        # Both the reproduction test and regression suite pass — fix is safe.
        fix_status = "fix_verified"
    elif repro_status != "passed":
        # Reproduction test still fails — fix did not resolve the issue.
        # Rollback the patch so the repo is clean for retries.
        _rollback_patch(patch_result, repository_path)
        fix_status = "fix_failed"
    elif regression_status == "no_regression_tests":
        # Repro passed but no existing regression tests exist to validate
        # against — we cannot confirm the fix is regression-safe.
        # Rollback to preserve a clean state.
        _rollback_patch(patch_result, repository_path)
        fix_status = "no_regression_tests"
    elif regression_status != "passed":
        # Repro passed but regression broke — fix introduces a regression.
        # Rollback to preserve a clean state.
        _rollback_patch(patch_result, repository_path)
        fix_status = "regression_failed"
    else:
        fix_status = "needs_review"

    # Clean up backup on success (keep it on failure for debugging)
    if fix_status == "fix_verified":
        backup = patch_result.get("backup")
        if backup and os.path.isfile(backup):
            os.remove(backup)

    return {
        "status": fix_status,
        "file": fix_data["file_path"],
        "function": finding.get("function"),
        "explanation": fix_data["explanation"],
        "original_code": fix_data["original_code"],
        "fixed_code": fix_data["fixed_code"],
        "diff": fix_data.get("diff", ""),
        "patch_result": patch_result,
        "repro_result": repro_result,
        "regression": regression,
        "requires_review": fix_status != "fix_verified",
    }
