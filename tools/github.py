import re

import requests


def fetch_github_file(repo_url: str, file_path: str, branch: str | None = None) -> str:
    """
    Fetches the content of a specified file from a GitHub repository.

    Parameters
    ----------
    repo_url : str
        The URL of the GitHub repository (e.g., https://github.com/user/repo).
    file_path : str
        The relative path to the file within the repo (e.g., README.md, src/main.py).
    branch : str, optional
        The branch name to use. If None, will use the default branch.
    """
    # Normalize and validate repo URL
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if not match:
        raise ValueError(f"Invalid GitHub repo URL: {repo_url}")

    user, repo = match.groups()
    api_url = f"https://api.github.com/repos/{user}/{repo}"

    if branch is None:
        resp = requests.get(api_url)
        if resp.status_code != 200:
            raise ValueError(
                f"Unable to fetch repo metadata: HTTP {resp.status_code}, {resp.text}"
            )
        branch = resp.json().get("default_branch", "main")

    raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{file_path}"
    resp = requests.get(raw_url)

    if resp.status_code != 200:
        raise ValueError(
            f"Unable to fetch file '{file_path}' on branch '{branch}': "
            f"HTTP {resp.status_code}, {resp.text}"
        )

    return resp.text


def list_github_folder(
    repo_url: str, folder_path: str = "", branch: str | None = None
) -> list[dict]:
    """
    Lists the contents of a folder in a GitHub repository.

    Parameters
    ----------
    repo_url : str
        The URL of the GitHub repository.
    folder_path : str
        Path to the folder inside the repo (e.g., "src", or "" for root).
    branch : str, optional
        Specific branch to use; defaults to the repo's default branch.
    """
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if not match:
        raise ValueError(f"Invalid GitHub repo URL: {repo_url}")

    user, repo = match.groups()
    if branch is None:
        meta_resp = requests.get(f"https://api.github.com/repos/{user}/{repo}")
        if meta_resp.status_code != 200:
            raise ValueError(
                f"Unable to fetch repo metadata: {meta_resp.status_code}, {meta_resp.text}"
            )
        branch = meta_resp.json().get("default_branch", "main")

    api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{folder_path}?ref={branch}"
    resp = requests.get(api_url)

    if resp.status_code != 200:
        raise ValueError(
            f"Unable to list folder '{folder_path}' on branch '{branch}': "
            f"HTTP {resp.status_code}, {resp.text}"
        )

    return resp.json()
