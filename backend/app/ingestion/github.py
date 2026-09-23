import os
import re

from git import Repo


REPOSITORY_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "repositories"
)


def get_repository_name(repo_url: str) -> str:
    """
    Extract repository name from a GitHub URL.
    """

    repo_url = repo_url.rstrip("/")

    name = repo_url.split("/")[-1]

    if name.endswith(".git"):
        name = name[:-4]

    if not re.match(r"^[a-zA-Z0-9_.-]+$", name):
        raise ValueError("Invalid repository name.")

    return name


def clone_repository(repo_url: str) -> dict:
    """
    Clone a GitHub repository into the local repositories directory.
    """

    repository_name = get_repository_name(repo_url)

    os.makedirs(REPOSITORY_ROOT, exist_ok=True)

    repository_path = os.path.join(
        REPOSITORY_ROOT,
        repository_name
    )

    if os.path.exists(repository_path):
        return {
            "status": "already_exists",
            "repository_name": repository_name,
            "repository_path": repository_path
        }

    Repo.clone_from(
        repo_url,
        repository_path
    )

    return {
        "status": "cloned",
        "repository_name": repository_name,
        "repository_path": repository_path
    }