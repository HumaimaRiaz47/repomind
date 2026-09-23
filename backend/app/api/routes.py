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