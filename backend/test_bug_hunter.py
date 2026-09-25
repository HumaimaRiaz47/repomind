"""
Focused tests for the Bug Hunter agent.

Tests cover:
1. _parse_findings() — all edge cases, no network needed.
2. generate_bug_hypotheses() with a mock AIClient — verifies
   the client is called and the result matches expected structure.
3. Integration smoke test against the real AI (skipped if Ollama
   is unavailable) using the cloned Flask repository.

Run from the backend/ directory:

    python test_bug_hunter.py
"""

import json
import os
import sys
import unittest
import warnings
from unittest.mock import MagicMock, patch

# ── Make sure the app package is importable ────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from app.agents.bug_hunter import (
    _parse_findings,
    build_bug_hunter_prompt,
    generate_bug_hypotheses,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _minimal_finding(**overrides):
    """Return a valid finding dict, with optional field overrides."""
    base = {
        "title": "Test finding",
        "file": "app/example.py",
        "function": "some_function",
        "severity": "medium",
        "confidence": 0.75,
        "reason": "Some reason.",
        "hypothesis": "It will fail under X.",
    }
    base.update(overrides)
    return base


def _make_context(files=None):
    """Return a minimal repository context."""
    return {
        "repository": {
            "path": "/fake/repo",
            "source_file_count": 1,
            "test_file_count": 0,
            "directory_count": 1,
            "has_tests": False,
            "config_files": [],
        },
        "files": files or [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for _parse_findings()
# ─────────────────────────────────────────────────────────────────────────────

class TestParseFindings(unittest.TestCase):

    def test_valid_single_finding(self):
        raw = json.dumps({"findings": [_minimal_finding()]})
        result = _parse_findings(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Test finding")

    def test_valid_multiple_findings(self):
        raw = json.dumps({
            "findings": [
                _minimal_finding(title="Bug A"),
                _minimal_finding(title="Bug B", severity="high"),
            ]
        })
        result = _parse_findings(raw)
        self.assertEqual(len(result), 2)

    def test_markdown_code_fence_stripped(self):
        inner = json.dumps({"findings": [_minimal_finding()]})
        raw = f"```json\n{inner}\n```"
        result = _parse_findings(raw)
        self.assertEqual(len(result), 1)

    def test_empty_findings_list(self):
        raw = json.dumps({"findings": []})
        result = _parse_findings(raw)
        self.assertEqual(result, [])

    def test_invalid_json_returns_empty(self):
        with warnings.catch_warnings(record=True):
            result = _parse_findings("not json at all")
        self.assertEqual(result, [])

    def test_missing_findings_key_returns_empty(self):
        raw = json.dumps({"bugs": []})
        with warnings.catch_warnings(record=True):
            result = _parse_findings(raw)
        self.assertEqual(result, [])

    def test_findings_not_a_list_returns_empty(self):
        raw = json.dumps({"findings": "oops"})
        with warnings.catch_warnings(record=True):
            result = _parse_findings(raw)
        self.assertEqual(result, [])

    def test_malformed_finding_missing_key_dropped(self):
        good = _minimal_finding(title="Good")
        bad = {k: v for k, v in _minimal_finding().items() if k != "hypothesis"}
        raw = json.dumps({"findings": [bad, good]})
        result = _parse_findings(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Good")

    def test_invalid_severity_dropped(self):
        finding = _minimal_finding(severity="critical")
        raw = json.dumps({"findings": [finding]})
        result = _parse_findings(raw)
        self.assertEqual(result, [])

    def test_confidence_clamped_below_zero(self):
        finding = _minimal_finding(confidence=-5)
        raw = json.dumps({"findings": [finding]})
        result = _parse_findings(raw)
        self.assertEqual(result[0]["confidence"], 0.0)

    def test_confidence_clamped_above_one(self):
        finding = _minimal_finding(confidence=99)
        raw = json.dumps({"findings": [finding]})
        result = _parse_findings(raw)
        self.assertEqual(result[0]["confidence"], 1.0)

    def test_non_dict_item_in_list_dropped(self):
        raw = json.dumps({"findings": ["not-a-dict", _minimal_finding()]})
        result = _parse_findings(raw)
        self.assertEqual(len(result), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for generate_bug_hypotheses() with a mocked AIClient
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateBugHypotheses(unittest.TestCase):

    def _run_with_mock_response(self, ai_response: str):
        """
        Patch AIClient.generate() to return ai_response, run
        generate_bug_hypotheses(), and return the result.
        """
        with patch("app.agents.bug_hunter.AIClient") as MockClient:
            instance = MagicMock()
            instance.generate.return_value = ai_response
            MockClient.return_value = instance

            context = _make_context()
            result = generate_bug_hypotheses(context)

            # Verify the client was instantiated and called exactly once.
            MockClient.assert_called_once()
            instance.generate.assert_called_once()

        return result

    def test_client_is_called(self):
        raw = json.dumps({"findings": [_minimal_finding()]})
        result = self._run_with_mock_response(raw)
        # generate() was called → findings populated from AI response.
        self.assertIn("findings", result)

    def test_valid_ai_response_returns_findings(self):
        finding = _minimal_finding(title="Null pointer dereference")
        raw = json.dumps({"findings": [finding]})
        result = self._run_with_mock_response(raw)
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["title"], "Null pointer dereference")

    def test_return_structure_always_has_findings_key(self):
        # Even on bad AI output the dict key must exist.
        result = self._run_with_mock_response("bad response")
        self.assertIn("findings", result)
        self.assertIsInstance(result["findings"], list)

    def test_empty_ai_response_returns_empty_findings(self):
        result = self._run_with_mock_response(json.dumps({"findings": []}))
        self.assertEqual(result["findings"], [])

    def test_prompt_contains_source_code(self):
        """build_bug_hunter_prompt must include source_code from context."""
        context = _make_context(files=[{
            "path": "app/calc.py",
            "source_code": "def add(a, b):\n    return a + b\n",
            "analysis": {"functions": [], "classes": [], "imports": [], "exception_handlers": []},
        }])
        prompt = build_bug_hunter_prompt(context)
        self.assertIn("def add(a, b):", prompt)
        self.assertIn("app/calc.py", prompt)

    def test_all_required_fields_present(self):
        finding = _minimal_finding()
        raw = json.dumps({"findings": [finding]})
        result = self._run_with_mock_response(raw)
        returned = result["findings"][0]
        for key in ("title", "file", "function", "severity", "confidence",
                    "reason", "hypothesis"):
            self.assertIn(key, returned, f"Missing key: {key}")


# ─────────────────────────────────────────────────────────────────────────────
# Integration smoke test against the real AI (Ollama)
# ─────────────────────────────────────────────────────────────────────────────

class TestBugHunterIntegration(unittest.TestCase):

    def _flask_repo_path(self):
        return os.path.join(
            os.path.dirname(__file__),
            "repositories",
            "flask",
        )

    def test_real_ai_on_flask_repo(self):
        """
        Run the Bug Hunter against the cloned Flask repo using the real
        Ollama model. Skipped if AI_PROVIDER != 'ollama' or Ollama is down.
        """
        provider = os.getenv("AI_PROVIDER", "placeholder")
        if provider != "ollama":
            print("\n[integration] SKIPPED — set AI_PROVIDER=ollama to run.")
            return

        repo_path = self._flask_repo_path()
        if not os.path.isdir(repo_path):
            print("\n[integration] SKIPPED — Flask repo not cloned yet.")
            return

        from app.ingestion.context_builder import build_repository_context

        # Only scan a small subset of Flask to keep the test fast.
        # Use the helpers/ module — short, self-contained file.
        context = build_repository_context(repo_path)

        # Limit to 3 files so the prompt stays manageable.
        context["files"] = context["files"][:3]

        try:
            result = generate_bug_hypotheses(context)
        except RuntimeError as err:
            print(f"\n[integration] SKIPPED — Ollama unavailable: {err}")
            return

        self.assertIn("findings", result)
        self.assertIsInstance(result["findings"], list)

        print(f"\n[integration] PASSED — {len(result['findings'])} finding(s) returned.")
        for f in result["findings"]:
            print(f"  [{f['severity'].upper()}] {f['title']}  ({f['file']})")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
