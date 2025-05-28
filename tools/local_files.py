import pathlib
import subprocess

BASE_DIR = pathlib.Path.cwd().resolve()


def _resolve_path(path: str) -> pathlib.Path:
    """
    Resolve a path safely relative to the base directory and prevent path traversal.

    Parameters
    -----
    path : str
        The relative or absolute path to resolve

    Returns
    -----
    pathlib.Path
        The resolved absolute path within BASE_DIR

    Raises
    -----
    PermissionError
        If the resolved path is outside of BASE_DIR
    """
    abs_path = (BASE_DIR / path).resolve()
    if not str(abs_path).startswith(str(BASE_DIR)):
        raise PermissionError("Access outside of the working directory is not allowed")
    return abs_path


def read_file(path: str, seek: int = 0, max_characters: int | None = None) -> str:
    """
    Read a (text-based) file from the filesystem, restricted to current working directory and below.

    Parameters
    -----
    path : str
        The path to the file, relative to the current working directory
    seek : int
        The number of bytes to seek from the beginning of the file (by default: 0)
    max_characters : int
        Read at most this nr of characters from the file (or until EOF). Use this to peek into, but not reed the whole file.
    """
    if not path:
        raise ValueError("File path cannot be empty")

    abs_path = _resolve_path(path)

    with abs_path.open("r") as f:
        f.seek(seek)
        return f.read(max_characters)


def write_file(path: str, content: str) -> None:
    """
    Write a (text-based) file to the filesystem, restricted to current working directory and below.
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


def list_dir(path: str) -> list:
    """
    List the files and directories in the specified directory, restricted to current working directory and below.

    Parameters
    -----
    path : str
        The path to the directory, relative to the current working directory
    """
    abs_path = _resolve_path(path)

    return [
        {"path": str(p), "type": "dir" if p.is_dir() else "file"}
        for p in abs_path.glob("*")
    ]


def get_git_tracked_tree(path: str) -> list:
    """
    Return a structured directory tree of git-tracked files under the given path,
    including file sizes.

    Parameters
    -----
    path : str
        The path to the directory, relative to the current working directory

    Returns
    -----
    list
        List of dictionaries representing files and directories with 'path', 'type',
        and optional 'children' or 'size' (in bytes)
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
                            "size": file_path.stat().st_size,
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

def patch_file(
    path: str,
    start_line: int,
    end_line: int,
    replacement: str,
    backup: bool = False,
    dry_run: bool = False
) -> dict | None:
    """
    Apply a line-based edit to a text file. Replaces the specified 1-based inclusive line range
    with the given replacement text. Supports appending, modifying, or deleting content.

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
    backup : bool, optional
        If True, creates a backup with `.bak` suffix before modifying.
    dry_run : bool, optional
        If True, does not write to disk. Returns both original and modified content.

    Returns
    -------
    dict | None
        If dry_run is True, returns {'original': str, 'modified': str}.
        Otherwise returns None.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If line numbers are invalid or out of bounds.

    Examples
    --------
    # Replace lines 5–7
    patch_file("main.py", 5, 7, "def new_logic():\n    return True\n")

    # Append after last line (file has 42 lines)
    patch_file("main.py", 43, 43, "# new function\ndef f():\n    pass\n")

    # Delete line 10
    patch_file("main.py", 10, 10, "")
    """
    abs_path = _resolve_path(path)
    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    original_content = abs_path.read_text(encoding="utf-8")
    line_ending = "\r\n" if "\r\n" in original_content else "\n"
    lines = original_content.splitlines(keepends=True) if original_content else []
    line_count = len(lines)

    if not isinstance(start_line, int) or not isinstance(end_line, int):
        raise ValueError("Line numbers must be integers")
    if start_line < 1 or end_line < 1:
        raise ValueError("Line numbers must be positive")
    if start_line > end_line:
        raise ValueError(f"start_line ({start_line}) cannot be greater than end_line ({end_line})")

    is_append = start_line == line_count + 1 and end_line == line_count + 1
    if is_append and start_line != end_line:
        raise ValueError("When appending, start_line and end_line must be equal")

    if not is_append:
        if start_line > line_count + 1:
            raise ValueError(f"Start line {start_line} exceeds file length ({line_count})")
        if end_line > line_count:
            raise ValueError(f"End line {end_line} exceeds file length ({line_count})")

    if backup and not dry_run:
        backup_path = abs_path.with_suffix(abs_path.suffix + ".bak")
        backup_path.write_text(original_content, encoding="utf-8")

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
    lines[start_idx:end_idx + 1] = replacement_lines

    modified_content = "".join(lines)

    if dry_run:
        return {"original": original_content, "modified": modified_content}

    abs_path.write_text(modified_content, encoding="utf-8")
    return None
