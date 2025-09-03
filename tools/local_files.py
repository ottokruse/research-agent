import pathlib
import re
import subprocess
from typing import Any, Dict, List, Literal

from generative_ai_toolkit.agent import registry
from mypy_boto3_bedrock_runtime.type_defs import ToolResultContentBlockUnionTypeDef

from tools.registries import local_files

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


@registry.tool(tool_registry=local_files)
def write_file(path: str, content: str) -> None:
    """
    Write a (text-based) file to the local filesystem, restricted to current working directory and below.

    ALWAYS ask the user for consent, before writing a file.

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


LLM_SUPPORTED_FILE_EXTENSIONS: set[
    Literal[
        "csv",
        "doc",
        "docx",
        "html",
        "md",
        "pdf",
        "txt",
        "xls",
        "xlsx",
    ]
] = set(["csv", "doc", "docx", "html", "md", "pdf", "txt", "xls", "xlsx"])


@registry.tool(tool_registry=local_files)
def read_file(path: str) -> str | list[ToolResultContentBlockUnionTypeDef]:
    """
    Read a file from the local filesystem, restricted to current working directory and below.

    Only textual files (e.g. source code) or files with one of the following extensions are supported:

    - .csv
    - .doc
    - .docx
    - .html
    - .md
    - .pdf
    - .txt
    - .xls
    - .xlsx

    Parameters
    -----
    path : str
        The path to the file, relative to the current working directory
    """
    if not path:
        raise ValueError("File path cannot be empty")

    abs_path = _resolve_path(path)
    ext = abs_path.suffix.lower().lstrip(".")
    filename = abs_path.name.strip()

    # Replace any character that's NOT alphanumeric, space, hyphen, parentheses, or square brackets
    # with an underscore
    filename = re.sub(r"[^a-zA-Z0-9 \-\(\)\[\]]", "_", filename)

    if ext not in LLM_SUPPORTED_FILE_EXTENSIONS:
        with abs_path.open("r") as f:
            return f.read()

    with abs_path.open("rb") as f:
        return [
            {
                "document": {
                    "format": ext,
                    "source": {"bytes": f.read()},
                    "name": filename,
                }
            }
        ]


@registry.tool(tool_registry=local_files)
def list_dir(path: str) -> List[Dict[str, Any]]:
    """
    List the files and directories in the specified local directory, restricted to current working directory and below.

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
            "size_kb": None if p.is_dir() else int(p.stat().st_size / 1024),
        }
        for p in abs_path.glob("*")
    ]


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
