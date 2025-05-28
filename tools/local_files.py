import pathlib

SESSION_FILES = set()

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


def read_file(path: str, seek: int = 0) -> str:
    """
    Read a (text-based) file from the filesystem, restricted to current working directory and below.

    Parameters
    -----
    path : str
        The path to the file, relative to the current working directory
    seek : int
        The number of bytes to seek from the beginning of the file (by default: 0)
    """
    if not path:
        raise ValueError("File path cannot be empty")

    abs_path = _resolve_path(path)

    with abs_path.open("r") as f:
        f.seek(seek)
        return f.read()


def write_file(path: str, content: str) -> None:
    """
    Write a (text-based) file to the filesystem, restricted to current working directory and below.
    Will not overwrite an existing file unless it was created in the current session.

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

    if abs_path.exists() and str(abs_path) not in SESSION_FILES:
        raise FileExistsError("Cannot overwrite existing file outside of session")

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    with abs_path.open("w") as f:
        f.write(content)

    SESSION_FILES.add(str(abs_path))


def list_dir(path: str) -> list:
    """
    List the files and directories in the specified directory, restricted to current working directory and below.

    Parameters
    -----
    path : str
        The path to the directory, relative to the current working directory
    """
    abs_path = _resolve_path(path)

    return [{"path": str(p), "type": "dir" if p.is_dir() else "file"} for p in abs_path.glob("*")]
