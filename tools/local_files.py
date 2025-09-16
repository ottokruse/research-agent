import pathlib
import re
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
def write_file(path: str, content: str, overwrite: bool = False) -> None:
    """
    Write a (text-based) file to the local filesystem, restricted to current working directory and below.

    ALWAYS ask the user for consent, before writing a file.

    Parameters
    -----
    path : str
        The path to the file, relative to the current working directory
    content : str
        The content to write to the file
    overwrite : bool
        Should the file be overwritten in case it already exists? (optional, default False)
    """
    if not path:
        raise ValueError("File path cannot be empty")

    abs_path = _resolve_path(path)

    if abs_path.exists() and not overwrite:
        raise FileExistsError(f"File {path} already exists")

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    with abs_path.open("w") as f:
        f.write(content)


LLM_SUPPORTED_DOC_EXTENSIONS: set[
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

LLM_SUPPORTED_IMAGE_EXTENSIONS: set[Literal["gif", "jpeg", "png", "webp"]] = set(
    ["gif", "jpeg", "png", "webp"]
)


@registry.tool(tool_registry=local_files)
def read_file(
    path: str, force_as_text: bool = False
) -> str | list[ToolResultContentBlockUnionTypeDef]:
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
    - .gif
    - .jpg
    - .jpeg
    - .png
    - .webp

    Parameters
    -----
    path : str
        The path to the file, relative to the current working directory
    force_as_text : bool
        Force reading the file as text, not as document
    """
    if not path:
        raise ValueError("File path cannot be empty")

    abs_path = _resolve_path(path)
    ext = abs_path.suffix.lower().lstrip(".").replace("jpg", "jpeg")
    filename = abs_path.name.strip()

    # Replace any character that's NOT alphanumeric, space, hyphen, parentheses, or square brackets
    # with an underscore
    filename = re.sub(r"[^a-zA-Z0-9 \-\(\)\[\]]", "_", filename)

    if not force_as_text:
        if ext in LLM_SUPPORTED_DOC_EXTENSIONS:
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
        elif ext in LLM_SUPPORTED_IMAGE_EXTENSIONS:
            with abs_path.open("rb") as f:
                return [
                    {
                        "image": {
                            "format": ext,
                            "source": {"bytes": f.read()},
                        }
                    }
                ]
    with abs_path.open("r") as f:
        return f.read()


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
