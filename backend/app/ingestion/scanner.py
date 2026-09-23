import os


IMPORTANT_FILES = {
    "README.md",
    "README.rst",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "package.json",
    "package-lock.json",
    "Dockerfile",
    "docker-compose.yml",
    ".gitignore",
}


def scan_repository(repository_path: str) -> dict:
    """
    Scan a cloned repository and collect basic structural information.
    """

    source_files = []
    test_files = []
    directories = []
    config_files = []

    for root, dirs, files in os.walk(repository_path):

        # Ignore Git metadata
        dirs[:] = [
            directory
            for directory in dirs
            if directory != ".git"
        ]

        # Store directory paths
        for directory in dirs:
            directory_path = os.path.join(
                root,
                directory
            )

            directories.append(
                os.path.relpath(
                    directory_path,
                    repository_path
                )
            )

        for file in files:

            file_path = os.path.join(
                root,
                file
            )

            relative_path = os.path.relpath(
                file_path,
                repository_path
            )

            # Python source files
            if file.endswith(".py"):
                source_files.append(relative_path)

            # Test files
            if (
                file.startswith("test_")
                or file.endswith("_test.py")
            ):
                test_files.append(relative_path)

            # Important project files
            if file in IMPORTANT_FILES:
                config_files.append(relative_path)

    return {
        "repository_path": repository_path,
        "source_files": source_files,
        "test_files": test_files,
        "directories": directories,
        "config_files": config_files,
        "source_file_count": len(source_files),
        "test_file_count": len(test_files),
        "directory_count": len(directories),
        "has_tests": len(test_files) > 0,
    }