from typing import Dict, Any

from app.ingestion.context_builder import build_repository_context
from app.agents.bug_hunter import generate_bug_hypotheses
from app.agents.test_generator import generate_tests
from app.executor.test_runner import run_test
from app.agents.validation_agent import validate_finding
from app.agents.fix_agent import generate_fix
from app.executor.regression_runner import run_regression_tests


def run_repomind_workflow(
    repository_path: str
) -> Dict[str, Any]:
    """
    Run the complete RepoMind analysis workflow.
    """

    # --------------------------------------------------
    # 1. Build repository context
    # --------------------------------------------------

    context = build_repository_context(
        repository_path
    )

    # --------------------------------------------------
    # 2. Find bug hypotheses
    # --------------------------------------------------

    findings = generate_bug_hypotheses(
        context
    )

    # --------------------------------------------------
    # 3. Generate tests
    # --------------------------------------------------

    tests = generate_tests(
        context,
        findings
    )

    results = []

    # --------------------------------------------------
    # 4. Execute + validate each finding
    # --------------------------------------------------

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

        # --------------------------------------------------
        # 5. Generate fix proposal
        # --------------------------------------------------

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

    # --------------------------------------------------
    # 6. Regression testing
    # --------------------------------------------------

    regression = run_regression_tests(
        repository_path
    )

    # --------------------------------------------------
    # 7. Final workflow result
    # --------------------------------------------------

    return {
        "repository": repository_path,
        "repository_context": context,
        "findings": findings,
        "tests": tests,
        "results": results,
        "regression": regression
    }