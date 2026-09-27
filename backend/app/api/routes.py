import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ingestion.github import clone_repository
from app.ingestion.scanner import scan_repository
from app.ingestion.ast_analyzer import analyze_python_file
from app.ingestion.context_builder import build_repository_context
from app.agents.bug_hunter import generate_bug_hypotheses
from app.agents.validation_agent import validate_finding
from app.agents.fix_agent import generate_fix
from app.executor.regression_runner import run_regression_tests
from app.agents.test_generator import generate_tests
from app.executor.test_runner import run_test
from app.agents.validation_agent import validate_finding
from app.agents.fix_agent import generate_fix
from app.executor.regression_runner import run_regression_tests

from app.orchestrator.workflow import (
    run_repomind_workflow
)



router = APIRouter(
    prefix="/api/repositories",
    tags=["Repositories"]
)


class RepositoryRequest(BaseModel):
    repo_url: str


@router.post("/clone")
def clone_repo(request: RepositoryRequest):

    try:
        result = clone_repository(request.repo_url)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/scan")
def scan_repo(request: RepositoryRequest):

    try:
        result = clone_repository(request.repo_url)

        repository_path = result["repository_path"]

        scan_result = scan_repository(repository_path)

        return {
            "repository": result,
            "scan": scan_result
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
@router.post("/analyze-file")
def analyze_file(request: RepositoryRequest):

    try:
        result = clone_repository(request.repo_url)

        repository_path = result["repository_path"]

        scan_result = scan_repository(repository_path)

        source_files = scan_result["source_files"]

        if not source_files:
            raise ValueError(
                "No Python source files found."
            )

        first_file = source_files[0]

        file_path = os.path.join(
            repository_path,
            first_file
        )

        analysis = analyze_python_file(
            file_path
        )

        return analysis

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/context")
def build_context(request: RepositoryRequest):

    try:
        result = clone_repository(request.repo_url)

        repository_path = result["repository_path"]

        context = build_repository_context(
            repository_path
        )

        return context

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
@router.post("/bugs")
def find_bugs(request: RepositoryRequest):

    try:
        result = clone_repository(request.repo_url)

        repository_path = result["repository_path"]

        context = build_repository_context(
            repository_path
        )

        findings = generate_bug_hypotheses(
            context
        )

        return findings

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    
@router.post("/tests")
def generate_repository_tests(request: RepositoryRequest):

    try:
        result = clone_repository(request.repo_url)

        repository_path = result["repository_path"]

        context = build_repository_context(
            repository_path
        )

        findings = generate_bug_hypotheses(
            context
        )

        tests = generate_tests(
            context,
            findings
        )

        return tests

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/execute-test")
def execute_generated_test(
    request: RepositoryRequest
):
    try:
        result = clone_repository(request.repo_url)

        repository_path = result["repository_path"]

        context = build_repository_context(
            repository_path
        )

        findings = generate_bug_hypotheses(
            context
        )

        tests = generate_tests(
            context,
            findings
        )

        execution_results = []

        for test in tests["tests"]:

            execution = run_test(
                test["test_code"],
                repository_path
            )

            execution_results.append({
                "test_name": test["test_name"],
                "file": test["file"],
                "function": test["function"],
                "hypothesis": test["hypothesis"],
                "execution": execution
            })

        return {
            "results": execution_results,
            "result_count": len(execution_results)
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    
@router.post("/validate")
def validate_repository_findings(
    request: RepositoryRequest
):

    try:

        result = clone_repository(
            request.repo_url
        )

        repository_path = result["repository_path"]

        # Build repository context
        context = build_repository_context(
            repository_path
        )

        # Generate bug hypotheses
        findings = generate_bug_hypotheses(
            context
        )

        # Generate tests
        tests = generate_tests(
            context,
            findings
        )

        validation_results = []

        for finding, test in zip(
            findings["findings"],
            tests["tests"]
        ):

            # Execute generated test
            execution = run_test(
                test["test_code"],
                repository_path
            )

            # Validate hypothesis
            validation = validate_finding(
                finding,
                execution
            )

            validation_results.append({

                "finding": finding,

                "test": {
                    "name": test["test_name"],
                    "code": test["test_code"]
                },

                "execution": execution,

                "validation": validation
            })

        return {
            "results": validation_results,
            "result_count": len(validation_results)
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/fix")
def generate_repository_fix(
    request: RepositoryRequest
):

    try:

        result = clone_repository(
            request.repo_url
        )

        repository_path = result["repository_path"]

        context = build_repository_context(
            repository_path
        )

        findings = generate_bug_hypotheses(
            context
        )

        tests = generate_tests(
            context,
            findings
        )

        results = []

        for finding, test in zip(
            findings["findings"],
            tests["tests"]
        ):

            execution = run_test(
                test["test_code"],
                repository_path
            )

            validation = validate_finding(
                finding,
                execution
            )

            fix = generate_fix(
                finding,
                validation,
                context
            )

            results.append({
                "finding": finding,
                "test": test,
                "execution": execution,
                "validation": validation,
                "fix": fix
            })

        return {
            "results": results,
            "result_count": len(results)
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/tests/regression")
def regression_test(request: dict):

    try:

        repository_path = request.get(
            "repository_path"
        )

        if not repository_path:
            raise HTTPException(
                status_code=400,
                detail="repository_path is required"
            )

        return run_regression_tests(
            repository_path
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/analyze")
def analyze_repository(request: RepositoryRequest):

    try:

        result = clone_repository(
            request.repo_url
        )

        repository_path = result[
            "repository_path"
        ]

        workflow_result = run_repomind_workflow(
            repository_path
        )

        return workflow_result

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/regression")
def run_repository_regression(
    request: RepositoryRequest
):

    try:

        result = clone_repository(
            request.repo_url
        )

        repository_path = result["repository_path"]

        regression = run_regression_tests(
            repository_path
        )

        return {
            "repository": request.repo_url,
            "regression": regression
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

# ---------------------------------------------------------------------------
# /report — frontend-aligned analysis endpoint
# ---------------------------------------------------------------------------

@router.post("/report")
def get_analysis_report(request: RepositoryRequest):
    """
    Run the full RepoMind workflow and return a response shaped to match
    the frontend AnalysisReport type exactly.

    Request:  { "repo_url": "https://github.com/owner/repo" }
    Response: see AnalysisReport in frontend/src/types/index.ts
    """

    try:
        # 1. Clone (or reuse) the repository
        clone_result = clone_repository(request.repo_url)
        repository_path = clone_result["repository_path"]

        # 2. Run the full pipeline
        workflow = run_repomind_workflow(repository_path)

        # 3. Extract repo metadata from the workflow context
        repo_meta_raw = workflow.get("repository_context", {}).get("repository", {})
        repo_url = request.repo_url.rstrip("/")
        url_parts = repo_url.split("/")
        repo_name = url_parts[-1] if url_parts else "repository"
        repo_owner = url_parts[-2] if len(url_parts) >= 2 else "unknown"

        repo_meta = {
            "url": request.repo_url,
            "owner": repo_owner,
            "name": repo_name,
            "language": "Python",
            "filesScanned": repo_meta_raw.get("source_file_count", 0),
            "dependencies": len(repo_meta_raw.get("config_files", [])),
        }

        # 4. Map pipeline results → frontend Finding objects
        findings_out = []
        issues_validated = 0
        issues_fixed = 0

        for i, result_item in enumerate(workflow.get("results", [])):
            finding = result_item.get("finding", {})
            validation = result_item.get("validation", {})
            fix = result_item.get("fix", {})

            val_status = validation.get("status", "needs_review")
            fix_status = fix.get("status", "not_applicable")

            # Map validation status to frontend finding status
            if fix_status == "fix_verified":
                f_status = "fixed"
                issues_fixed += 1
                issues_validated += 1
            elif val_status == "validated":
                f_status = "validated"
                issues_validated += 1
            elif val_status == "rejected":
                f_status = "rejected"
            else:
                f_status = "pending"

            findings_out.append({
                "id": f"finding_{i}",
                "title": finding.get("title", "Untitled finding"),
                "description": finding.get("reason", finding.get("hypothesis", "")),
                "severity": finding.get("severity", "low"),
                "file": finding.get("file") or "",
                "line": 0,
                "agent": "Bug Hunter Agent",
                "status": f_status,
                # Carry backend detail for evidence/fix views (not part of
                # the core Finding interface but safely ignored by components
                # that don't use it)
                "_result": result_item,
            })

        tests_generated = workflow.get("tests", {}).get("test_count", 0)

        import datetime
        report = {
            "repo": repo_meta,
            "findings": findings_out,
            "issuesFound": len(findings_out),
            "issuesValidated": issues_validated,
            "issuesFixed": issues_fixed,
            "testsGenerated": tests_generated,
            "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        return report

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
