"""
Focused tests for the Test Generator agent.

Tests cover:
1. _parse_test_response() — all edge cases, no network needed.
2. generate_tests() with a mocked AIClient — verifies the client
   is called, prompt contains finding + source code, and output
   preserves the expected structure.
3. Integration smoke test against the real Ollama model (skipped
   when AI_PROVIDER != "ollama").

Run from the backend/ directory:

    python test_test_generator.py
    AI_PROVIDER=ollama python test_test_generator.py
"""

import json
import os
import sys
import unittest
import warnings
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

from app.agents.test_generator import (
    _find_source_for_file,
    _parse_test_response,
    _safe_test_name,
    build_test_generation_prompt,
    generate_tests,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _good_test_code(name="test_my_bug_repomind"):
    return (
        f"def {name}():\n"
        "    result = 1 / 0\n"
        "    assert result == 0\n"
    )

def _good_ai_response(name="test_my_bug_repomind"):
    return json.dumps({"test_name": name, "test_code": _good_test_code(name)})


def _minimal_finding(**overrides):
    base = {
        "title": "Division by zero",
        "file": "app/calc.py",
        "function": "divide",
        "severity": "high",
        "confidence": 0.9,
        "reason": "No zero-guard before division.",
        "hypothesis": "Calling divide(1, 0) raises ZeroDivisionError.",
    }
    base.update(overrides)
    return base


def _make_context(files=None):
    return {
        "repository": {"source_file_count": 1, "test_file_count": 0,
                       "has_tests": False, "directory_count": 1,
                       "config_files": [], "path": "/repo"},
        "files": files or [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for helper functions
# ─────────────────────────────────────────────────────────────────────────────

class TestHelpers(unittest.TestCase):

    def test_find_source_returns_code(self):
        ctx = _make_context(files=[
            {"path": "app/calc.py", "source_code": "def divide(a, b): return a/b"}
        ])
        result = _find_source_for_file(ctx, "app/calc.py")
        self.assertIn("def divide", result)

    def test_find_source_unknown_path_returns_empty(self):
        ctx = _make_context()
        self.assertEqual(_find_source_for_file(ctx, "missing.py"), "")

    def test_find_source_none_path_returns_empty(self):
        self.assertEqual(_find_source_for_file(_make_context(), None), "")

    def test_safe_test_name_from_function(self):
        name = _safe_test_name("my_func", "Some title")
        self.assertTrue(name.startswith("test_"))
        self.assertIn("my_func", name)

    def test_safe_test_name_from_title_when_no_function(self):
        name = _safe_test_name(None, "Division by zero")
        self.assertTrue(name.startswith("test_"))
        self.assertIn("division", name)

    def test_safe_test_name_null_string_uses_title(self):
        name = _safe_test_name("null", "Race condition")
        self.assertIn("race", name)

    def test_safe_test_name_special_chars_stripped(self):
        name = _safe_test_name("foo-bar/baz", None)
        self.assertNotIn("-", name)
        self.assertNotIn("/", name)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for _parse_test_response()
# ─────────────────────────────────────────────────────────────────────────────

class TestParseTestResponse(unittest.TestCase):

    FALLBACK_NAME = "test_fallback_repomind"
    HYPOTHESIS = "It will fail."

    def _parse(self, raw):
        return _parse_test_response(raw, self.FALLBACK_NAME, self.HYPOTHESIS)

    def test_valid_response_returns_test_code(self):
        raw = _good_ai_response()
        result = self._parse(raw)
        self.assertIn("def test_", result["test_code"])
        self.assertNotIn("pytest.skip", result["test_code"])

    def test_markdown_fence_stripped(self):
        inner = _good_ai_response()
        raw = f"```json\n{inner}\n```"
        result = self._parse(raw)
        self.assertIn("def test_", result["test_code"])

    def test_invalid_json_returns_fallback(self):
        with warnings.catch_warnings(record=True):
            result = self._parse("not json")
        self.assertIn("pytest.skip", result["test_code"])
        self.assertEqual(result["test_name"], self.FALLBACK_NAME)

    def test_non_dict_json_returns_fallback(self):
        with warnings.catch_warnings(record=True):
            result = self._parse(json.dumps(["a", "b"]))
        self.assertIn("pytest.skip", result["test_code"])

    def test_missing_test_code_key_returns_fallback(self):
        raw = json.dumps({"test_name": "test_foo"})
        with warnings.catch_warnings(record=True):
            result = self._parse(raw)
        self.assertIn("pytest.skip", result["test_code"])

    def test_empty_test_code_returns_fallback(self):
        raw = json.dumps({"test_name": "test_foo", "test_code": ""})
        with warnings.catch_warnings(record=True):
            result = self._parse(raw)
        self.assertIn("pytest.skip", result["test_code"])

    def test_no_def_test_in_code_returns_fallback(self):
        raw = json.dumps({"test_name": "test_foo", "test_code": "print('hello')"})
        with warnings.catch_warnings(record=True):
            result = self._parse(raw)
        self.assertIn("pytest.skip", result["test_code"])

    def test_assert_true_only_returns_fallback(self):
        code = "def test_foo():\n    assert True"
        raw = json.dumps({"test_name": "test_foo", "test_code": code})
        with warnings.catch_warnings(record=True):
            result = self._parse(raw)
        self.assertIn("pytest.skip", result["test_code"])

    def test_assert_true_with_other_logic_is_accepted(self):
        code = "def test_foo():\n    x = 1 + 1\n    assert x == 2\n    assert True"
        raw = json.dumps({"test_name": "test_foo", "test_code": code})
        result = self._parse(raw)
        # Real assertion present alongside assert True → accepted
        self.assertNotIn("pytest.skip", result["test_code"])

    def test_test_name_taken_from_response(self):
        name = "test_custom_name_repomind"
        raw = _good_ai_response(name)
        result = self._parse(raw)
        self.assertEqual(result["test_name"], name)

    def test_missing_test_name_uses_fallback_name(self):
        code = _good_test_code()
        raw = json.dumps({"test_code": code})
        result = self._parse(raw)
        self.assertEqual(result["test_name"], self.FALLBACK_NAME)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for generate_tests() with a mocked AIClient
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateTests(unittest.TestCase):

    def _run_with_mock(self, ai_response, findings=None, context=None):
        if findings is None:
            findings = {"findings": [_minimal_finding()]}
        if context is None:
            context = _make_context(files=[
                {
                    "path": "app/calc.py",
                    "source_code": "def divide(a, b):\n    return a / b\n",
                    "analysis": {},
                }
            ])

        num_findings = len(findings.get("findings", []))

        with patch("app.agents.test_generator.AIClient") as MockClient:
            instance = MagicMock()
            instance.generate.return_value = ai_response
            MockClient.return_value = instance

            result = generate_tests(context, findings)

            MockClient.assert_called_once()
            if num_findings > 0:
                instance.generate.assert_called_once()
            else:
                instance.generate.assert_not_called()

        return result, instance

    def test_client_is_called_once_per_finding(self):
        findings = {"findings": [_minimal_finding(), _minimal_finding(title="Bug B")]}
        context = _make_context()
        ai_resp = _good_ai_response()

        with patch("app.agents.test_generator.AIClient") as MockClient:
            instance = MagicMock()
            instance.generate.return_value = ai_resp
            MockClient.return_value = instance

            generate_tests(context, findings)

            self.assertEqual(instance.generate.call_count, 2)

    def test_output_has_tests_and_test_count(self):
        result, _ = self._run_with_mock(_good_ai_response())
        self.assertIn("tests", result)
        self.assertIn("test_count", result)
        self.assertEqual(result["test_count"], 1)

    def test_each_test_has_required_keys(self):
        result, _ = self._run_with_mock(_good_ai_response())
        test = result["tests"][0]
        for key in ("finding_title", "file", "function", "hypothesis",
                    "test_name", "test_code", "status"):
            self.assertIn(key, test, f"Missing key: {key}")

    def test_valid_ai_response_produces_real_test_code(self):
        result, _ = self._run_with_mock(_good_ai_response())
        test_code = result["tests"][0]["test_code"]
        self.assertIn("def test_", test_code)
        self.assertNotIn("pytest.skip", test_code)

    def test_bad_ai_response_produces_fallback(self):
        result, _ = self._run_with_mock("broken response {{{")
        test_code = result["tests"][0]["test_code"]
        self.assertIn("pytest.skip", test_code)

    def test_empty_findings_produces_empty_tests(self):
        result, _ = self._run_with_mock(_good_ai_response(), findings={"findings": []})
        self.assertEqual(result["tests"], [])
        self.assertEqual(result["test_count"], 0)

    def test_prompt_contains_finding_details(self):
        """The prompt passed to the AI must include key finding fields."""
        finding = _minimal_finding()
        context = _make_context(files=[
            {
                "path": "app/calc.py",
                "source_code": "def divide(a, b):\n    return a / b\n",
                "analysis": {},
            }
        ])

        with patch("app.agents.test_generator.AIClient") as MockClient:
            instance = MagicMock()
            instance.generate.return_value = _good_ai_response()
            MockClient.return_value = instance

            generate_tests(context, {"findings": [finding]})

            call_args = instance.generate.call_args[0][0]

        self.assertIn(finding["title"], call_args)
        self.assertIn(finding["hypothesis"], call_args)
        self.assertIn("def divide", call_args)   # source code included

    def test_prompt_contains_source_code(self):
        context = _make_context(files=[
            {
                "path": "app/calc.py",
                "source_code": "def divide(a, b):\n    return a / b\n",
                "analysis": {},
            }
        ])

        prompt = build_test_generation_prompt(_minimal_finding(), "def divide(a, b):\n    return a / b\n")
        self.assertIn("def divide", prompt)
        self.assertIn("app/calc.py", prompt)

    def test_status_field_is_generated(self):
        result, _ = self._run_with_mock(_good_ai_response())
        self.assertEqual(result["tests"][0]["status"], "generated")


# ─────────────────────────────────────────────────────────────────────────────
# Integration smoke test — real Ollama model
# ─────────────────────────────────────────────────────────────────────────────

class TestTestGeneratorIntegration(unittest.TestCase):

    def test_real_ai_generates_test_for_simple_finding(self):
        """
        Uses the real Ollama model with a small, self-contained finding.
        Verifies that a non-empty, executable test function is returned.
        Skipped when AI_PROVIDER != 'ollama'.
        """
        provider = os.getenv("AI_PROVIDER", "placeholder")
        if provider != "ollama":
            print("\n[integration] SKIPPED — set AI_PROVIDER=ollama to run.")
            return

        finding = {
            "title": "Off-by-one in paginate()",
            "file": "app/pagination.py",
            "function": "paginate",
            "severity": "high",
            "confidence": 0.95,
            "reason": "start = page * limit skips the first item on page 1.",
            "hypothesis": (
                "Calling paginate(items, page=1, limit=5) skips index 0, "
                "so page_1[0] != items[0]."
            ),
        }

        source_code = (
            "def paginate(items, page, limit):\n"
            "    start = page * limit\n"
            "    return items[start:start + limit]\n"
        )

        context = _make_context(files=[
            {"path": "app/pagination.py", "source_code": source_code, "analysis": {}}
        ])

        try:
            result = generate_tests(context, {"findings": [finding]})
        except RuntimeError as err:
            print(f"\n[integration] SKIPPED — Ollama unavailable: {err}")
            return

        self.assertEqual(result["test_count"], 1)
        test = result["tests"][0]
        test_code = test["test_code"]

        print(f"\n[integration] PASSED")
        print(f"  test_name: {test['test_name']}")
        print(f"  test_code:\n{test_code}")

        # Must be a real test function (not just a skip stub).
        self.assertIn("def test_", test_code)

        # Must contain a real assertion.
        self.assertRegex(test_code, r"assert\s+.+")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
