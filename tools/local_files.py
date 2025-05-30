import pathlib
import subprocess
from typing import Any, Dict, List, Optional

BASE_DIR = pathlib.Path.cwd().resolve()


def _resolve_path(path: str) -> pathlib.Path:
    """
    Resolve a path safely relative to the base directory and prevent path traversal.

    Parameters
    -----
    path : str
        The relative or absolute path to resolve
    """
    abs_path = (BASE_DIR / path).resolve()
    if not str(abs_path).startswith(str(BASE_DIR)):
        raise PermissionError("Access outside of the working directory is not allowed")
    return abs_path


def write_file(path: str, content: str) -> None:
    """
    Write a (text-based) file to the filesystem, restricted to current working directory and below.

    NOTE: The agent MUST ask for and receive user consent before creating or modifying files.
    Before using this tool, you should ensure that you do not inadvertently provide a path that already exists, as it will be overwritten.

    Parameters
    -----
    path : str
        The path to the file, relative to the current working directory
    content : str
        The content to write to the file
    """
    if not path:
        raise ValueError("File path cannot be empty")

    abs_path = _resolve_path(path)

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    with abs_path.open("w") as f:
        f.write(content)


def list_dir(path: str) -> List[Dict[str, Any]]:
    """
    List the files and directories in the specified directory, restricted to current working directory and below.

    Parameters
    -----
    path : str
        The path to the directory, relative to the current working directory
    """
    abs_path = _resolve_path(path)

    return [
        {
            "path": str(p),
            "type": "dir" if p.is_dir() else "file",
            "size_kb": None if p.is_dir() else p.stat().st_size / 1024,
        }
        for p in abs_path.glob("*")
    ]


def get_git_tracked_tree(path: str) -> List[Dict[str, Any]]:
    """
    Return a full tree of git-tracked files under the given path,
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


def preview_patch(
    path: str,
    start_line: int,
    end_line: int,
    replacement: str,
) -> Dict[str, Any]:
    """
    Show a preview of the changes that would be made by patch_file without
    actually modifying the file.

    Parameters
    ----------
    path : str
        Path to the file, relative to working directory.
    start_line : int
        1-based starting line number to replace (inclusive).
    end_line : int
        1-based ending line number to replace (inclusive).
    replacement : str
        Replacement text. Can be empty (for deletion). Can span multiple lines.

    Returns
    -------
    Dict[str, Any]
        A dictionary with preview information including:
        - original_lines: The lines that would be replaced
        - replacement_lines: The lines that would be inserted
        - diff: A unified diff-style representation of the changes
    """
    abs_path = _resolve_path(path)
    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    original_content = abs_path.read_text(encoding="utf-8")
    lines = original_content.splitlines() if original_content else []
    line_count = len(lines)

    if not isinstance(start_line, int) or not isinstance(end_line, int):
        raise ValueError("Line numbers must be integers")
    if start_line < 1 or end_line < 1:
        raise ValueError("Line numbers must be positive")
    if start_line > end_line:
        raise ValueError(
            f"start_line ({start_line}) cannot be greater than end_line ({end_line})"
        )

    is_append = start_line == line_count + 1 and end_line == line_count + 1
    if not is_append and end_line > line_count:
        raise ValueError(f"End line {end_line} exceeds file length ({line_count})")

    # Get lines being replaced
    original_lines = lines[start_line - 1 : end_line] if not is_append else []

    # Get replacement lines
    replacement_lines = replacement.splitlines()

    # Create a simple diff
    diff = []

    # Show some context before
    context_before_start = max(1, start_line - 3)
    if context_before_start < start_line:
        diff.append("... Context before:")
        for i in range(context_before_start, start_line):
            diff.append(f"  {i}: {lines[i-1]}")

    # Show lines being removed
    if original_lines:
        diff.append("--- Lines to remove:")
        for i, line in enumerate(original_lines, start=start_line):
            diff.append(f"- {i}: {line}")

    # Show lines being added
    if replacement_lines:
        diff.append("+++ Lines to add:")
        for i, line in enumerate(replacement_lines):
            diff.append(f"+ {start_line + i}: {line}")

    # Show some context after
    context_after_end = min(line_count, end_line + 3)
    if context_after_end > end_line and not is_append:
        diff.append("... Context after:")
        for i in range(end_line + 1, context_after_end + 1):
            diff.append(f"  {i}: {lines[i-1]}")

    return {
        "original_lines": original_lines,
        "replacement_lines": replacement_lines,
        "line_count_before": line_count,
        "line_count_after": line_count - len(original_lines) + len(replacement_lines),
        "diff": "\n".join(diff),
    }


def patch_by_pattern(
    path: str,
    pattern: str,
    replacement: str,
    occurrence: int = 1,
) -> Dict[str, Any]:
    """
    Apply a patch by matching a regex pattern rather than using line numbers.

    This is useful when the exact line numbers might change but a unique
    pattern in the text can be identified.

    NOTE: The agent MUST ask for and receive user consent before applying changes to files.

    Parameters
    ----------
    path : str
        Path to the file, relative to working directory.
    pattern : str
        A regex pattern to match text to be replaced.
    replacement : str
        Replacement text. Can be empty (for deletion). Can span multiple lines.
    occurrence : int, optional
        Which occurrence of the pattern to replace (1-based), by default 1.

    Returns
    -------
    Dict[str, Any]
        A dictionary with information about the applied patch.
    """
    import re

    abs_path = _resolve_path(path)
    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    original_content = abs_path.read_text(encoding="utf-8")

    # Find all occurrences of the pattern
    matches = list(re.finditer(pattern, original_content, re.MULTILINE))

    if not matches:
        return {
            "status": "error",
            "message": f"Pattern '{pattern}' not found in {path}",
        }

    if occurrence < 1 or occurrence > len(matches):
        return {
            "status": "error",
            "message": f"Occurrence {occurrence} is invalid. Found {len(matches)} matches.",
        }

    # Get the selected match
    match = matches[occurrence - 1]

    # Determine line numbers for the match
    lines_before = original_content[: match.start()].count("\n") + 1
    lines_span = original_content[match.start() : match.end()].count("\n")
    start_line = lines_before
    end_line = start_line + lines_span

    # Apply the patch if confirmed
    modified_content = (
        original_content[: match.start()]
        + replacement
        + original_content[match.end() :]
    )
    abs_path.write_text(modified_content, encoding="utf-8")

    return {
        "status": "complete",
        "message": f"Pattern replaced at lines {start_line}-{end_line} in {path}",
        "summary": {
            "lines_removed": lines_span + 1,
            "lines_added": len(replacement.splitlines()),
            "current_line_count": modified_content.count("\n") + 1,
        },
    }


def show_line_numbers(
    path: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Display file content with line numbers for easier reference.

    Parameters
    ----------
    path : str
        Path to the file, relative to working directory.
    start_line : int, optional
        1-based starting line number to display (inclusive), by default 1.
    end_line : Optional[int], optional
        1-based ending line number to display (inclusive), by default None (show all lines).

    Returns
    -------
    Dict[str, Any]
        A dictionary with the formatted file content including line numbers.
    """
    abs_path = _resolve_path(path)
    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    original_content = abs_path.read_text(encoding="utf-8")
    lines = original_content.splitlines()
    line_count = len(lines)

    if end_line is None:
        end_line = line_count

    if start_line < 1:
        raise ValueError("Start line must be a positive integer")
    if end_line > line_count:
        end_line = line_count

    formatted_lines = []
    for i in range(start_line - 1, min(end_line, line_count)):
        formatted_lines.append(f"{i + 1}: {lines[i]}")

    return {
        "formatted_content": "\n".join(formatted_lines),
        "line_count": line_count,
        "displayed_lines": len(formatted_lines),
    }


def apply_multiple_patches(
    path: str,
    patch1_start_line: Optional[int] = None,
    patch1_end_line: Optional[int] = None,
    patch1_replacement: Optional[str] = None,
    patch2_start_line: Optional[int] = None,
    patch2_end_line: Optional[int] = None,
    patch2_replacement: Optional[str] = None,
    patch3_start_line: Optional[int] = None,
    patch3_end_line: Optional[int] = None,
    patch3_replacement: Optional[str] = None,
    patch4_start_line: Optional[int] = None,
    patch4_end_line: Optional[int] = None,
    patch4_replacement: Optional[str] = None,
    patch5_start_line: Optional[int] = None,
    patch5_end_line: Optional[int] = None,
    patch5_replacement: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply up to 5 patches to a file. Each patch replaces a specified line range
    with new content. Patches are applied in reverse line order to avoid
    line shifting issues.

    NOTE: The agent MUST ask for and receive user consent before applying changes to files.

    Parameters
    ----------
    path : str
        Path to the file to be patched, relative to the working directory.

    patch1_start_line : Optional[int], optional
        Start line (1-based, inclusive) of patch 1.
    patch1_end_line : Optional[int], optional
        End line (1-based, inclusive) of patch 1.
    patch1_replacement : Optional[str], optional
        Replacement text for patch 1.

    patch2_start_line : Optional[int], optional
        Start line of patch 2.
    patch2_end_line : Optional[int], optional
        End line of patch 2.
    patch2_replacement : Optional[str], optional
        Replacement text for patch 2.

    patch3_start_line : Optional[int], optional
        Start line of patch 3.
    patch3_end_line : Optional[int], optional
        End line of patch 3.
    patch3_replacement : Optional[str], optional
        Replacement text for patch 3.

    patch4_start_line : Optional[int], optional
        Start line of patch 4.
    patch4_end_line : Optional[int], optional
        End line of patch 4.
    patch4_replacement : Optional[str], optional
        Replacement text for patch 4.

    patch5_start_line : Optional[int], optional
        Start line of patch 5.
    patch5_end_line : Optional[int], optional
        End line of patch 5.
    patch5_replacement : Optional[str], optional
        Replacement text for patch 5.

    Returns
    -------
    Dict[str, Any]
        A result dictionary containing:
        - status (str): One of "complete", "cancelled", or "no-op".
        - message (str): A description of the outcome.
        - patches (List): Info about each applied patch (index, line numbers, etc).
        - lines_before (int): Number of lines before applying patches.
        - lines_after (int): Number of lines after applying patches.

    Raises
    ------
    FileNotFoundError
        If the target file does not exist.
    """

    def make_patch(start, end, replacement):
        if start is not None and end is not None and replacement is not None:
            return {"start_line": start, "end_line": end, "replacement": replacement}
        return None

    patches = list(
        filter(
            None,
            [
                make_patch(patch1_start_line, patch1_end_line, patch1_replacement),
                make_patch(patch2_start_line, patch2_end_line, patch2_replacement),
                make_patch(patch3_start_line, patch3_end_line, patch3_replacement),
                make_patch(patch4_start_line, patch4_end_line, patch4_replacement),
                make_patch(patch5_start_line, patch5_end_line, patch5_replacement),
            ],
        )
    )

    if not patches:
        return {"status": "no-op", "message": "No patches provided."}

    abs_path = _resolve_path(path)
    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    sorted_patches = sorted(patches, key=lambda p: p["start_line"], reverse=True)

    all_previews = []
    all_previews = []
    for i, patch in enumerate(sorted_patches):
        preview = preview_patch(
            path, patch["start_line"], patch["end_line"], patch["replacement"]
        )
        all_previews.append({"patch_index": i + 1, "preview": preview})

    results = []
    original_content = abs_path.read_text(encoding="utf-8")
    lines = original_content.splitlines()

    for i, patch in enumerate(sorted_patches):
        start_line = patch["start_line"]
        end_line = patch["end_line"]
        replacement = patch["replacement"]

        replacement_lines = replacement.splitlines()
        lines[start_line - 1 : end_line] = replacement_lines

        result = {
            "patch_index": i + 1,
            "start_line": start_line,
            "end_line": end_line,
            "lines_removed": end_line - start_line + 1,
            "lines_added": len(replacement_lines),
        }
        results.append(result)

    final_content = "\n".join(lines)
    abs_path.write_text(final_content, encoding="utf-8")

    return {
        "status": "complete",
        "message": f"Applied {len(sorted_patches)} patches to {path}",
        "patches": results,
        "lines_before": original_content.count("\n") + 1,
        "lines_after": final_content.count("\n") + 1,
    }


def patch_file(
    path: str,
    start_line: int,
    end_line: int,
    replacement: str,
) -> Dict[str, Any]:
    """
    Apply a line-based edit to a text file. Replaces the specified 1-based inclusive line range
    with the given replacement text. Supports appending, modifying, or deleting content.

    NOTE: The agent MUST ask for and receive user consent before applying changes to files.

    Examples
    --------
    # Replace lines 5–7
    patch_file("main.py", 5, 7, "def new_logic():\\n    return True\\n")

    # Append after last line (file has 42 lines)
    patch_file("main.py", 43, 43, "# new function\\ndef f():\\n    pass\\n")

    # Delete line 10
    patch_file("main.py", 10, 10, "")

    Parameters
    ----------
    path : str
        Path to the file, relative to working directory.
    start_line : int
        1-based starting line number to replace (inclusive).
    end_line : int
        1-based ending line number to replace (inclusive).
    replacement : str
        Replacement text. Can be empty (for deletion). Can span multiple lines.
    """
    abs_path = _resolve_path(path)
    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Original patching logic
    original_content = abs_path.read_text(encoding="utf-8")
    line_ending = "\r\n" if "\r\n" in original_content else "\n"
    lines = original_content.splitlines(keepends=True) if original_content else []
    line_count = len(lines)

    is_append = start_line == line_count + 1 and end_line == line_count + 1

    # Normalize replacement and split
    normalized = replacement.replace("\r\n", "\n").replace("\n", line_ending)
    replacement_lines = normalized.splitlines(keepends=True) if normalized else []

    # Ensure last replacement line has line ending if needed
    if replacement_lines:
        # Match the line ending of the file at end_line, or use file's default
        if not replacement_lines[-1].endswith(("\n", "\r")):
            if is_append:
                replacement_lines[-1] += line_ending
            elif end_line <= line_count:
                ending = "\r\n" if lines[end_line - 1].endswith("\r\n") else "\n"
                replacement_lines[-1] += ending
            else:
                replacement_lines[-1] += line_ending

    # If appending to non-empty file, ensure previous last line ends cleanly
    if is_append and lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += line_ending

    # Apply patch
    start_idx = start_line - 1
    end_idx = end_line - 1
    lines[start_idx : end_idx + 1] = replacement_lines

    modified_content = "".join(lines)

    abs_path.write_text(modified_content, encoding="utf-8")

    return {
        "status": "complete",
        "message": f"Changes applied to {path}.",
        "summary": {
            "lines_removed": end_line - start_line + 1,
            "lines_added": len(replacement.splitlines()),
            "current_line_count": len(modified_content.splitlines()),
            "note": "Use show_line_numbers or preview_patch to inspect the file.",
        },
    }
