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


def patch_file(path: str, patches: list[dict]) -> None:
    """
    Apply a list of line-based in-place edits to a text file.
    Prefer this tool for doing updates to files. For example, to change lines in source code files.

    Each patch must specify:
    - 'start_line': the starting line number (1-based, inclusive) of the current content to replace
    - 'end_line': the ending line number (1-based, inclusive) of the current content to replace
    - 'replacement': the string to replace the specified lines with (can contain any number of lines)

    Note that the replacement text can contain a different number of lines than the original range,
    which will cause the file to expand or contract accordingly.

    Parameters
    -----
    path : str
        Path to the file, relative to working directory
    patches : list of dict
        List of patches to apply

    Raises
    -----
    ValueError
        If patch format is invalid, or if line numbers are out of range
    FileNotFoundError
        If the specified file doesn't exist

    Example
    -------
    patch_file("example.py", [
        {
            "start_line": 5,
            "end_line": 7,
            "replacement": "    # The 3 original lines were replaced with 2 new lines\n    return 'Hello, patched world!'\n"
        },
        {
            "start_line": 10,
            "end_line": 10,
            "replacement": "# One line expanded to multiple lines\ndef new_function():\n    pass\n"
        }
    ])

    Notes
    -----
    - Line numbers are 1-based (same as most editors).
    - The replacement string can contain multiple lines.
    - Patches are applied from bottom to top of the file to avoid affecting line numbers of pending patches.
    - Line endings will be preserved according to the replacement text provided.
    """
    abs_path = _resolve_path(path)

    # Check if file exists
    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Read the file content
    lines = abs_path.read_text().splitlines(keepends=True)

    # Validate patches before applying
    for patch in patches:
        # Validate required keys
        required_keys = ["start_line", "end_line", "replacement"]
        if not all(key in patch for key in required_keys):
            raise ValueError(f"Patch missing required keys. Required: {required_keys}")

        start = patch["start_line"]
        end = patch["end_line"]

        # Validate line numbers
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError("Line numbers must be integers")

        if start < 1 or end < 1:
            raise ValueError("Line numbers must be positive (1-based indexing)")

        if start > len(lines) + 1 or (end > len(lines) and start <= len(lines)):
            raise ValueError(f"Line numbers out of range. File has {len(lines)} lines.")

        if start > end:
            raise ValueError(
                f"start_line ({start}) cannot be greater than end_line ({end})"
            )

    # Sort patches in reverse order of start_line to avoid affecting subsequent patches
    for patch in sorted(patches, key=lambda p: p["start_line"], reverse=True):
        start = patch["start_line"] - 1  # Convert to 0-based indexing
        end = patch["end_line"]  # This is the inclusive end line (1-based)

        # Convert to 0-based indexing for slicing
        end_0_based = (
            end - 1 + 1
        )  # -1 to convert to 0-based, +1 because slices are exclusive at the end

        replacement_text = patch["replacement"]
        replacement_lines = replacement_text.splitlines(keepends=True)

        # Make sure the replacement has proper line endings if not empty
        if replacement_lines and not replacement_text.endswith(("\n", "\r")):
            # Only add a newline if the original last line had one
            if end_0_based <= len(lines) and lines[end_0_based - 1].endswith(
                ("\n", "\r")
            ):
                replacement_lines[-1] += "\n"

        # Apply the patch
        lines[start:end_0_based] = replacement_lines

    # Write the changes back to the file
    abs_path.write_text("".join(lines))
