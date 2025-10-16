# tools/git_inspect.py

import pathlib
import shlex
import subprocess
from typing import Any, Dict, List

from generative_ai_toolkit.agent import registry

from tools.local_files import _resolve_path
from tools.registries import local_files

BASE_DIR = pathlib.Path.cwd().resolve()


@registry.tool(tool_registry=local_files)
def get_git_tracked_tree(path: str) -> List[Dict[str, Any]]:
    """
    Return a full tree of git-tracked files under the given local path,
    including file sizes in KB.

    Parameters
    -----
    path : str
        The path to the directory, relative to the current working directory
    """
    abs_path = _resolve_path(path)
    rel_root = abs_path.relative_to(BASE_DIR)

    result = subprocess.run(
        ["git", "ls-files", str(rel_root)],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    files = result.stdout.strip().splitlines()
    tree = {}

    for file in files:
        parts = pathlib.Path(file).parts
        cursor = tree
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor.setdefault("__files__", []).append(parts[-1])

    def build_tree(d, base=""):
        items = []
        for k, v in d.items():
            if k == "__files__":
                for f in v:
                    file_path = BASE_DIR / base / f
                    if not file_path.exists():
                        continue
                    items.append(
                        {
                            "path": str(pathlib.Path(base) / f),
                            "type": "file",
                            "size_kb": file_path.stat().st_size / 1024,
                        }
                    )
            else:
                children = build_tree(v, pathlib.Path(base) / k)
                items.append(
                    {
                        "path": str(pathlib.Path(base) / k) + "/",
                        "type": "dir",
                        "children": children,
                    }
                )
        return items

    return build_tree(tree, str(rel_root))


@registry.tool(tool_registry=local_files)
def inspect_git_changes(
    include_staged: bool = True,
    include_unstaged: bool = True,
    show_diff: bool = True,
    include_commits: int | None = None,
):
    """
    Inspect all code changes on the current local git branch.

    Returns committed changes (recent commits), staged changes, and unstaged changes
    with optional diff content for comprehensive code review.

    Parameters
    ----------
    include_commits : int, optional
        Number of recent commits to include. If None (default), shows all commits
        on current branch that are not yet on main. Set to 0 to skip commits entirely.
        When on the main branch itself, no commits are shown by default.
    include_staged : bool
        Whether to include staged changes (default: True)
    include_unstaged : bool
        Whether to include unstaged changes (default: True)
    show_diff : bool
        Whether to include actual diff content (default: True)
    """
    result = {
        "branch_info": {},
        "committed_changes": [],
        "staged_changes": {},
        "unstaged_changes": {},
        "summary": {},
    }

    # Get current branch info
    branch_name = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True, stderr=subprocess.PIPE
    ).strip()

    # Get branch status
    status_output = subprocess.check_output(
        ["git", "status", "--porcelain", "--branch"], text=True, stderr=subprocess.PIPE
    ).strip()

    result["branch_info"] = {
        "name": branch_name,
        "status": status_output.split("\n")[0] if status_output else "",
    }

    # Get commits
    if include_commits != 0:
        # Determine which commits to show
        if include_commits is None:
            # Default: show all commits on current branch not on main
            if branch_name == "main":
                # If we're on main, don't show any commits by default
                # Users only want to see staged/unstaged changes when on main
                commit_range = None
                commit_description = "no commits (on main branch)"
            else:
                # Check if main branch exists
                subprocess.check_output(
                    ["git", "rev-parse", "--verify", "main"], stderr=subprocess.PIPE
                )
                commit_range = "main..HEAD"
                commit_description = "commits on current branch not yet on main"
        else:
            # Specific number requested
            commit_range = f"-{include_commits}"
            commit_description = f"last {include_commits} commits"

        # Only fetch commits if we have a valid commit_range
        if commit_range is not None:
            if show_diff:
                commit_cmd = [
                    "git",
                    "log",
                    commit_range,
                    "--pretty=format:COMMIT_START%nHash: %H%nAuthor: %an <%ae>%nDate: %ad%nSubject: %s%nCOMMIT_DIFF_START",
                    "--date=iso",
                    "-p",  # Include patch/diff
                ]
            else:
                commit_cmd = [
                    "git",
                    "log",
                    commit_range,
                    "--pretty=format:Hash: %H%nAuthor: %an <%ae>%nDate: %ad%nSubject: %s%n---",
                ]

            commits_output = subprocess.check_output(
                commit_cmd, text=True, stderr=subprocess.PIPE
            )

            if show_diff:
                # Parse commits with diffs
                commits = commits_output.split("COMMIT_START\n")[
                    1:
                ]  # Skip first empty split
                for commit in commits:
                    if "COMMIT_DIFF_START\n" in commit:
                        header, diff = commit.split("COMMIT_DIFF_START\n", 1)
                        commit_info = {}
                        for line in header.strip().split("\n"):
                            if ": " in line:
                                key, value = line.split(": ", 1)
                                commit_info[key.lower()] = value
                        commit_info["diff"] = diff.strip()
                        result["committed_changes"].append(commit_info)
            else:
                # Parse simple commit list
                for commit_block in commits_output.split("---\n"):
                    if commit_block.strip():
                        commit_info = {}
                        for line in commit_block.strip().split("\n"):
                            if ": " in line:
                                key, value = line.split(": ", 1)
                                commit_info[key.lower()] = value
                        if commit_info:
                            result["committed_changes"].append(commit_info)

        # Add metadata about what commits were shown
        result["branch_info"]["commits_shown"] = commit_description

    # Get staged changes
    if include_staged:
        if show_diff:
            staged_diff = subprocess.check_output(
                ["git", "diff", "--cached"], text=True, stderr=subprocess.PIPE
            )
            staged_files = subprocess.check_output(
                ["git", "diff", "--cached", "--name-status"],
                text=True,
                stderr=subprocess.PIPE,
            ).strip()
        else:
            staged_diff = ""
            staged_files = subprocess.check_output(
                ["git", "diff", "--cached", "--name-only"],
                text=True,
                stderr=subprocess.PIPE,
            ).strip()

        result["staged_changes"] = {
            "files": staged_files.split("\n") if staged_files else [],
            "diff": staged_diff if show_diff else "Diff not requested",
        }

    # Get unstaged changes
    if include_unstaged:
        # Get modified tracked files
        if show_diff:
            unstaged_diff = subprocess.check_output(
                ["git", "diff"], text=True, stderr=subprocess.PIPE
            )
            unstaged_files = subprocess.check_output(
                ["git", "diff", "--name-status"], text=True, stderr=subprocess.PIPE
            ).strip()
        else:
            unstaged_diff = ""
            unstaged_files = subprocess.check_output(
                ["git", "diff", "--name-only"], text=True, stderr=subprocess.PIPE
            ).strip()

        # Get untracked files (new files not yet added to git)
        untracked_files = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()

        # Combine modified and untracked files
        all_files = []
        if unstaged_files:
            all_files.extend(unstaged_files.split("\n"))
        if untracked_files:
            # Add untracked files with "??" prefix to match git status format
            for f in untracked_files.split("\n"):
                all_files.append(f"??\t{f}")

        result["unstaged_changes"] = {
            "files": all_files,
            "diff": unstaged_diff if show_diff else "Diff not requested",
            "note": "Includes both modified tracked files and untracked files (marked with ??)",
        }

    # Generate summary
    committed_count = len(result["committed_changes"])
    staged_count = len(result["staged_changes"].get("files", []))
    unstaged_count = len(result["unstaged_changes"].get("files", []))

    result["summary"] = {
        "total_commits_shown": committed_count,
        "staged_files_count": staged_count,
        "unstaged_files_count": unstaged_count,
        "has_changes": staged_count > 0 or unstaged_count > 0,
    }

    return result


@registry.tool(tool_registry=local_files)
def execute_git_command(command: str) -> Dict[str, Any]:
    """
    Execute an arbitrary git command safely and return the output.

    This tool allows you to run any git command that might not be covered by
    the other specialized git tools. The command is executed in the current
    working directory with proper error handling.

    **Command Parsing**
    
    This tool uses shell-style parsing (`shlex.split()`) to properly handle:
    - Quoted arguments with spaces
    - Escaped characters
    - Complex format strings
    - Search patterns with spaces
    
    This means you can use standard shell quoting conventions in your commands.

    **Supported Commands - Simple:**
    
    Basic git operations work as expected:
        - "git status"
        - "git branch"
        - "git log --oneline -5"
        - "git diff --stat"
        - "git log --all --oneline --graph -5"

    **Supported Commands - With Quotes:**
    
    Commands with quoted arguments now work correctly:
        - 'git log --pretty=format:"%H %s" -1'
          (Shows commit hash and subject with space separator)
        
        - 'git log --grep="Initial commit" --oneline'
          (Search for commits with "Initial commit" in message)
        
        - 'git log --pretty=format:"%an <%ae>" -3'
          (Shows author name and email in specific format)
        
        - 'git commit -m "Fix bug in parser"'
          (Commit with message containing spaces)
    
    **Quoting Guidelines:**
    
    1. Use double quotes for arguments containing spaces:
       - 'git log --pretty=format:"%H %s"'
       - 'git log --grep="bug fix"'
    
    2. You can use single quotes in the outer command string:
       - 'git log --pretty=format:"%H"' (outer single, inner double)
    
    3. Escape special characters if needed:
       - 'git log --pretty=format:"%H\\"'  (include literal quote)
    
    4. Arguments without spaces don't need quotes:
       - "git log --format=%h -3"
       - "git log --author=John"

    **Edge Cases:**
    
    - Empty arguments: Use empty quotes if needed: 'git commit --allow-empty -m ""'
    - Special characters: Shell-style escaping works: 'git log --grep="fix\\(bug\\)"'
    - Multiple spaces: Preserved inside quotes: 'git commit -m "Fix  double  spaces"'

    Parameters
    ----------
    command : str
        The full git command to execute, including "git" prefix.
        Supports shell-style quoting for complex arguments.
        
        Examples:
            - "git log --oneline -5"
            - 'git log --pretty=format:"%H %s" -1'
            - 'git log --grep="Initial commit"'
            - "git diff HEAD~1 HEAD"
            - 'git commit -m "My commit message"'
    
    Returns
    -------
    Dict[str, Any]
        A dictionary containing:
        - success (bool): True if returncode was 0
        - stdout (str): Standard output from the command
        - stderr (str): Standard error from the command
        - returncode (int): The command's return code
    
    Examples
    --------
    >>> execute_git_command("git status")
    {'success': True, 'stdout': 'On branch main...', 'stderr': '', 'returncode': 0}
    
    >>> execute_git_command('git log --pretty=format:"%H %s" -1')
    {'success': True, 'stdout': 'abc123 Fixed parser bug', 'stderr': '', 'returncode': 0}
    
    >>> execute_git_command('git log --grep="Initial commit" --oneline')
    {'success': True, 'stdout': 'abc123 Initial commit', 'stderr': '', 'returncode': 0}
    """
    # Use shlex.split() for proper shell-style parsing
    try:
        cmd_parts = shlex.split(command)
    except ValueError as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Failed to parse command: {str(e)}",
            "returncode": -1,
        }

    # Validate command starts with "git"
    if not cmd_parts or cmd_parts[0] != "git":
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command must start with 'git'",
            "returncode": -1,
        }

    # Execute the command
    try:
        result = subprocess.run(
            cmd_parts,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Exception occurred: {str(e)}",
            "returncode": -1,
        }
