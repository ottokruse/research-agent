import json
import os
import re

import requests
import yaml
from generative_ai_toolkit.agent import registry

from tools.registries import web_research


@registry.tool(tool_registry=web_research)
def fetch_github_file(repo_url: str, file_path: str, branch: str | None = None) -> str:
    """
    Fetches the content of a specified file from a repository on GitHub.

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


@registry.tool(tool_registry=web_research)
def list_github_folder(
    repo_url: str, folder_path: str = "", branch: str | None = None
) -> list[dict]:
    """
    Lists the contents of a folder in a repository on GitHub.

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


@registry.tool(tool_registry=web_research)
def fetch_github_notebook(
    repo_url: str, file_path: str, branch: str | None = None
) -> str:
    """
    Fetches a Jupyter notebook (.ipynb) from a repository on GitHub.
    and returns its content with all outputs removed.

    For downloading Jupyter notebooks (.ipynb), favor this tool!

    Parameters
    ----------
    repo_url : str
        The URL of the GitHub repository (e.g., https://github.com/user/repo).
    file_path : str
        The relative path to the notebook within the repo (e.g., notebooks/example.ipynb).
    branch : str, optional
        The branch name to use. If None, will use the default branch.
    """
    # Normalize and validate repo URL
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if not match:
        raise ValueError(f"Invalid GitHub repo URL: {repo_url}")

    # Validate file extension
    if not file_path.endswith(".ipynb"):
        raise ValueError(f"File must be a Jupyter notebook (.ipynb): {file_path}")

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
            f"Unable to fetch notebook '{file_path}' on branch '{branch}': "
            f"HTTP {resp.status_code}, {resp.text}"
        )

    try:
        # Parse the notebook JSON
        notebook = json.loads(resp.text)

        # Remove outputs from all cells
        if "cells" in notebook:
            for cell in notebook["cells"]:
                if "outputs" in cell:
                    cell["outputs"] = []
                if "execution_count" in cell:
                    cell["execution_count"] = None

        # Return the cleaned notebook as formatted JSON
        return json.dumps(notebook, indent=2)

    except json.JSONDecodeError:
        raise ValueError(f"The file '{file_path}' is not a valid Jupyter notebook.")


@registry.tool(tool_registry=web_research)
def fetch_pr_data_yaml(pr_url: str) -> str:
    """
    Given a GitHub pull request URL, returns a YAML string with:
      comments: list of all issue & review comments
      diff: the raw unified diff string
      status: PR status information (state, merged, etc.)
      workflows: CI/CD workflow runs and their status/logs

    Parameters
    ---
    pr_url : str
      The PR URL
    """
    m = re.match(
        r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)",
        pr_url,
    )
    if not m:
        raise ValueError(f"Invalid GitHub PR URL: {pr_url}")
    owner, repo, number = m.group("owner"), m.group("repo"), m.group("number")

    headers = {"Accept": "application/vnd.github.v3+json"}
    if "GITHUB_TOKEN" in os.environ:
        headers["Authorization"] = f'token {os.environ["GITHUB_TOKEN"]}'

    # 1) Fetch PR metadata (title, description, and status info)
    meta_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    resp = requests.get(meta_url, headers=headers)
    resp.raise_for_status()
    pr_meta = resp.json()

    title = pr_meta.get("title", "")
    description = pr_meta.get("body", "")
    head_sha = pr_meta.get("head", {}).get("sha", "")

    # Extract status information
    status_info = {
        "state": pr_meta.get("state", ""),  # open, closed
        "merged": pr_meta.get("merged", False),
        "mergeable": pr_meta.get("mergeable"),
        "mergeable_state": pr_meta.get("mergeable_state", ""),
        "draft": pr_meta.get("draft", False),
        "created_at": pr_meta.get("created_at", ""),
        "updated_at": pr_meta.get("updated_at", ""),
        "merged_at": pr_meta.get("merged_at"),
        "closed_at": pr_meta.get("closed_at"),
    }

    # helper to simplify comments
    def simplify(comments):
        return [
            {
                "who": c.get("user", {}).get("login", ""),
                "when": c.get("created_at", ""),
                "body": c.get("body", ""),
            }
            for c in comments
        ]

    # 2) Fetch issue comments
    issue_comments_url = (
        f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments"
    )
    resp = requests.get(issue_comments_url, headers=headers)
    resp.raise_for_status()
    issue_comments = resp.json()

    # 3) Fetch review comments
    review_comments_url = (
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/comments"
    )
    resp = requests.get(review_comments_url, headers=headers)
    resp.raise_for_status()
    review_comments = resp.json()

    # 4) Fetch diff
    diff_headers = headers.copy()
    diff_headers["Accept"] = "application/vnd.github.v3.diff"
    resp = requests.get(meta_url, headers=diff_headers)
    resp.raise_for_status()
    diff_text = resp.text

    # 5) Fetch workflow runs for the PR's head commit
    workflows_info = []
    if head_sha:
        try:
            # Get workflow runs for the head commit
            runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
            params = {"head_sha": head_sha, "per_page": 100}
            resp = requests.get(runs_url, headers=headers, params=params)
            resp.raise_for_status()
            runs_data = resp.json()

            for run in runs_data.get("workflow_runs", []):
                workflow_info = {
                    "id": run.get("id"),
                    "name": run.get("name"),
                    "status": run.get("status"),  # queued, in_progress, completed
                    "conclusion": run.get(
                        "conclusion"
                    ),  # success, failure, cancelled, etc.
                    "workflow_file": run.get("path", "").replace(
                        ".github/workflows/", ""
                    ),
                    "created_at": run.get("created_at"),
                    "updated_at": run.get("updated_at"),
                    "run_number": run.get("run_number"),
                    "html_url": run.get("html_url"),
                }

                # Fetch jobs for this workflow run to get more detailed status
                jobs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run.get('id')}/jobs"
                try:
                    jobs_resp = requests.get(jobs_url, headers=headers)
                    jobs_resp.raise_for_status()
                    jobs_data = jobs_resp.json()

                    workflow_info["jobs"] = []
                    for job in jobs_data.get("jobs", []):
                        job_info = {
                            "name": job.get("name"),
                            "status": job.get("status"),
                            "conclusion": job.get("conclusion"),
                            "started_at": job.get("started_at"),
                            "completed_at": job.get("completed_at"),
                        }

                        # Get job steps for more detail
                        steps = []
                        for step in job.get("steps", []):
                            steps.append(
                                {
                                    "name": step.get("name"),
                                    "status": step.get("status"),
                                    "conclusion": step.get("conclusion"),
                                    "number": step.get("number"),
                                }
                            )
                        job_info["steps"] = steps
                        workflow_info["jobs"].append(job_info)

                except requests.RequestException:
                    # If we can't fetch jobs, continue without them
                    workflow_info["jobs"] = []

                # Try to fetch logs summary (first few lines) for failed runs
                if run.get("conclusion") in ["failure", "cancelled"]:
                    try:
                        logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run.get('id')}/logs"
                        logs_resp = requests.get(logs_url, headers=headers)
                        if logs_resp.status_code == 200:
                            # Note: This returns a ZIP file, so we just note that logs are available
                            workflow_info["logs_available"] = True
                        else:
                            workflow_info["logs_available"] = False
                    except requests.RequestException:
                        workflow_info["logs_available"] = False
                else:
                    workflow_info["logs_available"] = False

                workflows_info.append(workflow_info)

        except requests.RequestException as e:
            # If workflow fetching fails, continue without workflows
            workflows_info = [{"error": f"Failed to fetch workflows: {str(e)}"}]

    # 6) Fetch status checks for the commit
    status_checks = []
    if head_sha:
        try:
            # Get status checks
            status_url = (
                f"https://api.github.com/repos/{owner}/{repo}/commits/{head_sha}/status"
            )
            resp = requests.get(status_url, headers=headers)
            resp.raise_for_status()
            status_data = resp.json()

            overall_status = {
                "state": status_data.get("state"),  # pending, success, error, failure
                "total_count": status_data.get("total_count"),
            }

            status_checks.append({"overall": overall_status})

            # Get individual status checks
            for status in status_data.get("statuses", []):
                status_checks.append(
                    {
                        "context": status.get("context"),
                        "state": status.get("state"),
                        "description": status.get("description"),
                        "target_url": status.get("target_url"),
                        "created_at": status.get("created_at"),
                    }
                )

            # Get check runs (newer status checks API)
            check_runs_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{head_sha}/check-runs"
            resp = requests.get(check_runs_url, headers=headers)
            resp.raise_for_status()
            check_runs_data = resp.json()

            for check in check_runs_data.get("check_runs", []):
                status_checks.append(
                    {
                        "name": check.get("name"),
                        "status": check.get("status"),
                        "conclusion": check.get("conclusion"),
                        "started_at": check.get("started_at"),
                        "completed_at": check.get("completed_at"),
                        "html_url": check.get("html_url"),
                    }
                )

        except requests.RequestException:
            # If status checks fail, continue without them
            status_checks = [{"error": "Failed to fetch status checks"}]

    payload = {
        "title": title,
        "description": description,
        "status": status_info,
        "comments": simplify(issue_comments) + simplify(review_comments),
        "diff": diff_text,
        "workflows": workflows_info,
        "status_checks": status_checks,
    }
    return yaml.safe_dump(payload, sort_keys=False)
