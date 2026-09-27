"""
Backend API tests for the /report endpoint and supporting routes.

Uses FastAPI's TestClient (via httpx) so no real server is needed.
The analysis pipeline (workflow) is mocked to avoid AI calls and
subprocess execution during unit tests.

Run from the backend/ directory:
    python test_api_report.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app, raise_server_exceptions=False)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mock_clone(url):
    return {
        "status": "cloned",
        "repository_name": "testrepo",
        "repository_path": "/fake/repo/testrepo",
    }


def _mock_workflow_empty(_path):
    """Workflow that returns no findings."""
    return {
        "repository": "/fake/repo/testrepo",
        "repository_context": {
            "repository": {
                "source_file_count": 3,
                "test_file_count": 1,
                "has_tests": True,
                "config_files": ["requirements.txt"],
                "directory_count": 2,
            },
            "files": [],
        },
        "findings": {"findings": []},
        "tests": {"tests": [], "test_count": 0},
        "results": [],
        "regression": {"status": "passed", "return_code": 0, "stdout": "", "stderr": ""},
    }


def _mock_workflow_with_findings(_path):
    """Workflow that returns one validated finding with a fix."""
    finding = {
        "title": "Division by zero",
        "file": "calc.py",
        "function": "divide",
        "severity": "high",
        "confidence": 0.95,
        "reason": "No zero guard.",
        "hypothesis": "divide(1, 0) raises ZeroDivisionError.",
    }
    return {
        "repository": "/fake/repo/testrepo",
        "repository_context": {
            "repository": {
                "source_file_count": 2,
                "test_file_count": 0,
                "has_tests": False,
                "config_files": [],
                "directory_count": 1,
            },
            "files": [],
        },
        "findings": {"findings": [finding]},
        "tests": {
            "tests": [
                {
                    "test_name": "test_divide_repomind",
                    "test_code": "def test_divide_repomind():\n    assert 1 == 1\n",
                    "finding_title": finding["title"],
                    "file": "calc.py",
                    "function": "divide",
                    "hypothesis": finding["hypothesis"],
                    "status": "generated",
                }
            ],
            "test_count": 1,
        },
        "results": [
            {
                "finding": finding,
                "test": {
                    "test_name": "test_divide_repomind",
                    "test_code": "def test_divide_repomind():\n    assert 1 == 1\n",
                },
                "execution": {
                    "status": "failed",
                    "return_code": 1,
                    "stdout": "FAILED",
                    "stderr": "ZeroDivisionError",
                },
                "validation": {
                    "status": "validated",
                    "confidence": 0.95,
                    "reason": "Test failed.",
                },
                "fix": {
                    "status": "fix_verified",
                    "explanation": "Added zero guard.",
                    "original_code": "    return a / b",
                    "fixed_code": "    if b == 0: return None\n    return a / b",
                    "diff": "",
                    "requires_review": False,
                },
            }
        ],
        "regression": {"status": "passed", "return_code": 0, "stdout": "1 passed", "stderr": ""},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Health / root
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthEndpoints(unittest.TestCase):

    def test_root_returns_200(self):
        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("RepoMind", res.json()["message"])

    def test_health_returns_healthy(self):
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")


# ─────────────────────────────────────────────────────────────────────────────
# /api/repositories/report
# ─────────────────────────────────────────────────────────────────────────────

class TestReportEndpoint(unittest.TestCase):

    @patch("app.api.routes.clone_repository", side_effect=_mock_clone)
    @patch("app.api.routes.run_repomind_workflow", side_effect=_mock_workflow_empty)
    def test_report_returns_200(self, _mock_wf, _mock_clone_fn):
        res = client.post(
            "/api/repositories/report",
            json={"repo_url": "https://github.com/owner/testrepo"},
        )
        self.assertEqual(res.status_code, 200)

    @patch("app.api.routes.clone_repository", side_effect=_mock_clone)
    @patch("app.api.routes.run_repomind_workflow", side_effect=_mock_workflow_empty)
    def test_report_has_required_top_level_keys(self, _mock_wf, _mock_clone_fn):
        res = client.post(
            "/api/repositories/report",
            json={"repo_url": "https://github.com/owner/testrepo"},
        )
        data = res.json()
        for key in ("repo", "findings", "issuesFound", "issuesValidated",
                    "issuesFixed", "testsGenerated", "generatedAt"):
            self.assertIn(key, data, f"Missing key: {key}")

    @patch("app.api.routes.clone_repository", side_effect=_mock_clone)
    @patch("app.api.routes.run_repomind_workflow", side_effect=_mock_workflow_empty)
    def test_repo_meta_fields(self, _mock_wf, _mock_clone_fn):
        res = client.post(
            "/api/repositories/report",
            json={"repo_url": "https://github.com/myowner/myrepo"},
        )
        repo = res.json()["repo"]
        self.assertEqual(repo["owner"], "myowner")
        self.assertEqual(repo["name"], "myrepo")
        self.assertEqual(repo["language"], "Python")
        self.assertIn("filesScanned", repo)
        self.assertIn("dependencies", repo)

    @patch("app.api.routes.clone_repository", side_effect=_mock_clone)
    @patch("app.api.routes.run_repomind_workflow", side_effect=_mock_workflow_empty)
    def test_empty_findings(self, _mock_wf, _mock_clone_fn):
        res = client.post(
            "/api/repositories/report",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        data = res.json()
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["issuesFound"], 0)
        self.assertEqual(data["issuesValidated"], 0)

    @patch("app.api.routes.clone_repository", side_effect=_mock_clone)
    @patch("app.api.routes.run_repomind_workflow", side_effect=_mock_workflow_with_findings)
    def test_findings_have_required_fields(self, _mock_wf, _mock_clone_fn):
        res = client.post(
            "/api/repositories/report",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        data = res.json()
        self.assertEqual(len(data["findings"]), 1)
        f = data["findings"][0]
        for key in ("id", "title", "description", "severity", "file", "line",
                    "agent", "status"):
            self.assertIn(key, f, f"Missing finding key: {key}")

    @patch("app.api.routes.clone_repository", side_effect=_mock_clone)
    @patch("app.api.routes.run_repomind_workflow", side_effect=_mock_workflow_with_findings)
    def test_validated_finding_counted(self, _mock_wf, _mock_clone_fn):
        res = client.post(
            "/api/repositories/report",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        data = res.json()
        self.assertGreater(data["issuesValidated"], 0)

    @patch("app.api.routes.clone_repository", side_effect=_mock_clone)
    @patch("app.api.routes.run_repomind_workflow", side_effect=_mock_workflow_with_findings)
    def test_fix_verified_counted_as_fixed(self, _mock_wf, _mock_clone_fn):
        res = client.post(
            "/api/repositories/report",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        data = res.json()
        # The mocked result has fix_verified → issuesFixed > 0
        self.assertGreater(data["issuesFixed"], 0)

    @patch("app.api.routes.clone_repository", side_effect=_mock_clone)
    @patch("app.api.routes.run_repomind_workflow", side_effect=_mock_workflow_with_findings)
    def test_result_detail_attached(self, _mock_wf, _mock_clone_fn):
        """Findings must carry _result for the evidence/fix views."""
        res = client.post(
            "/api/repositories/report",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        data = res.json()
        f = data["findings"][0]
        self.assertIn("_result", f)
        result = f["_result"]
        self.assertIn("execution", result)
        self.assertIn("validation", result)
        self.assertIn("fix", result)

    @patch("app.api.routes.clone_repository", side_effect=_mock_clone)
    @patch("app.api.routes.run_repomind_workflow", side_effect=_mock_workflow_with_findings)
    def test_tests_generated_count(self, _mock_wf, _mock_clone_fn):
        res = client.post(
            "/api/repositories/report",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        self.assertEqual(res.json()["testsGenerated"], 1)

    def test_missing_repo_url_returns_422(self):
        res = client.post("/api/repositories/report", json={})
        self.assertEqual(res.status_code, 422)

    def test_clone_failure_returns_400(self):
        with patch(
            "app.api.routes.clone_repository",
            side_effect=ValueError("Invalid repository name."),
        ):
            res = client.post(
                "/api/repositories/report",
                json={"repo_url": "https://github.com/owner/repo"},
            )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid repository name", res.json()["detail"])

    def test_workflow_error_returns_400(self):
        with patch("app.api.routes.clone_repository", side_effect=_mock_clone), \
             patch(
                 "app.api.routes.run_repomind_workflow",
                 side_effect=RuntimeError("AI model unavailable."),
             ):
            res = client.post(
                "/api/repositories/report",
                json={"repo_url": "https://github.com/owner/repo"},
            )
        self.assertEqual(res.status_code, 400)
        self.assertIn("AI model unavailable", res.json()["detail"])

    @patch("app.api.routes.clone_repository", side_effect=_mock_clone)
    @patch("app.api.routes.run_repomind_workflow", side_effect=_mock_workflow_empty)
    def test_generated_at_is_iso_string(self, _mock_wf, _mock_clone_fn):
        res = client.post(
            "/api/repositories/report",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        generated_at = res.json()["generatedAt"]
        self.assertIsInstance(generated_at, str)
        self.assertGreater(len(generated_at), 10)


# ─────────────────────────────────────────────────────────────────────────────
# CORS headers
# ─────────────────────────────────────────────────────────────────────────────

class TestCORS(unittest.TestCase):

    def test_cors_header_present_for_allowed_origin(self):
        res = client.options(
            "/api/repositories/report",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertIn(
            "access-control-allow-origin",
            {k.lower() for k in res.headers},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
