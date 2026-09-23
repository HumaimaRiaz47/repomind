import os

from app.ingestion.scanner import scan_repository
from app.ingestion.ast_analyzer import analyze_python_file


def build_repository_context(repository_path: str) -> dict:
    """
    Build a structured context of the repository.

    The context contains:
    - Repository metadata
    - Source files
    - Test files
    - AST information for Python source files
    """

    scan_result = scan_repository(repository_path)

    files_context = []

    for relative_path in scan_result["source_files"]:

        # Skip test files for now.
        # Tests will be handled separately.
        if (
            relative_path.startswith("tests\\")
            or "\\tests\\" in relative_path
            or relative_path.startswith("test_")
            or relative_path.endswith("_test.py")
        ):
            continue

        file_path = os.path.join(
            repository_path,
            relative_path
        )

        try:
            ast_data = analyze_python_file(file_path)

            files_context.append({
                "path": relative_path,
                "type": "python_source",
                "analysis": ast_data
            })

        except (SyntaxError, UnicodeDecodeError) as error:

            files_context.append({
                "path": relative_path,
                "type": "python_source",
                "analysis_error": str(error)
            })

    return {
        "repository": {
            "path": repository_path,
            "source_file_count": scan_result["source_file_count"],
            "test_file_count": scan_result["test_file_count"],
            "directory_count": scan_result["directory_count"],
            "has_tests": scan_result["has_tests"],
            "config_files": scan_result["config_files"],
        },
        "files": files_context
    }