import json
import re
import warnings
from typing import Any, Dict, List

from app.ai.client import AIClient

# Required keys every finding dict must contain.
_REQUIRED_FINDING_KEYS = {
    "title",
    "file",
    "function",
    "severity",
    "confidence",
    "reason",
    "hypothesis",
}

_VALID_SEVERITIES = {"low", "medium", "high"}


def build_bug_hunter_prompt(
    repository_context: Dict[str, Any]
) -> str:
    """
    Build the prompt sent to the AI Bug Hunter.

    Each file is presented with its actual source code first,
    followed by its AST summary, so the model can reason about
    real logic rather than metadata alone.
    """

    repo_meta = repository_context.get("repository", {})
    files = repository_context.get("files", [])

    # Build a compact, model-friendly representation of each file.
    file_blocks = []

    for file_data in files:
        path = file_data.get("path", "unknown")
        source = file_data.get("source_code", "").strip()
        analysis = file_data.get("analysis", {})
        error = file_data.get("analysis_error")

        block_lines = [f"=== FILE: {path} ==="]

        if source:
            block_lines.append("-- source code --")
            block_lines.append(source)
        else:
            block_lines.append("-- source code unavailable --")

        if error:
            block_lines.append(f"-- parse error: {error} --")
        elif analysis:
            functions = analysis.get("functions", [])
            classes = analysis.get("classes", [])
            imports = analysis.get("imports", [])
            handlers = analysis.get("exception_handlers", [])

            ast_summary = {
                "functions": [
                    {"name": f["name"], "line": f["line"], "args": f["args"]}
                    for f in functions
                ],
                "classes": [c["name"] for c in classes],
                "imports": imports[:20],           # cap to keep prompt short
                "exception_handlers": handlers,
            }

            block_lines.append("-- AST summary --")
            block_lines.append(json.dumps(ast_summary, indent=2))

        file_blocks.append("\n".join(block_lines))

    files_section = "\n\n".join(file_blocks)

    repo_summary = (
        f"Files: {repo_meta.get('source_file_count', '?')}  "
        f"Test files: {repo_meta.get('test_file_count', '?')}  "
        f"Has tests: {repo_meta.get('has_tests', '?')}"
    )

    return f"""You are RepoMind's Bug Hunter — a precise static analysis agent.

Analyze the Python source files below and identify real, concrete
software reliability issues.

Rules:
- Do NOT report vague or hypothetical concerns.
- Only report issues that are visible in the provided source code.
- For each finding you must provide all seven fields.
- severity must be exactly one of: low, medium, high.
- confidence must be a number between 0.0 and 1.0.
- function should name the specific function, or null if file-level.
- reason must cite specific lines or patterns from the code.

Repository summary: {repo_summary}

{files_section}

Return ONLY a JSON object — no explanation, no markdown, no extra text.
The JSON must follow this exact schema:

{{
    "findings": [
        {{
            "title": "short descriptive title",
            "file": "relative/path/to/file.py",
            "function": "function_name_or_null",
            "severity": "low|medium|high",
            "confidence": 0.0,
            "reason": "what in the code led to this finding",
            "hypothesis": "concrete failure scenario that could be reproduced"
        }}
    ]
}}

If you find no issues, return: {{"findings": []}}
"""


def _parse_findings(raw: str) -> List[Dict[str, Any]]:
    """
    Extract a valid findings list from the model's raw text response.

    Handles:
    - Markdown code fences  (```json ... ```)
    - Leading/trailing whitespace
    - Invalid JSON          → returns []
    - Missing "findings"    → returns []
    - Malformed items       → silently drops them
    """

    # Strip markdown fences if present.
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        warnings.warn(
            f"Bug Hunter: AI response is not valid JSON ({exc}). "
            "Returning empty findings.",
            stacklevel=2,
        )
        return []

    if not isinstance(data, dict):
        warnings.warn(
            "Bug Hunter: AI response JSON is not an object. "
            "Returning empty findings.",
            stacklevel=2,
        )
        return []

    raw_findings = data.get("findings")

    if not isinstance(raw_findings, list):
        warnings.warn(
            "Bug Hunter: 'findings' key missing or not a list. "
            "Returning empty findings.",
            stacklevel=2,
        )
        return []

    valid = []
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        if not _REQUIRED_FINDING_KEYS.issubset(item.keys()):
            continue
        # Normalise severity — drop items with unknown severity.
        if item.get("severity") not in _VALID_SEVERITIES:
            continue
        # Normalise confidence to float in [0, 1].
        try:
            item["confidence"] = max(0.0, min(1.0, float(item["confidence"])))
        except (TypeError, ValueError):
            item["confidence"] = 0.0
        valid.append(item)

    return valid


def generate_bug_hypotheses(
    repository_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Use AIClient to analyse the repository context and return
    a structured list of bug findings.
    """

    client = AIClient()
    prompt = build_bug_hunter_prompt(repository_context)
    raw_response = client.generate(prompt)
    findings = _parse_findings(raw_response)

    return {"findings": findings}
