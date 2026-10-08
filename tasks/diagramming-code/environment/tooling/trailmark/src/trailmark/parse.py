"""Language detection used by the bundled diagramming workflow."""

from pathlib import Path
from typing import Union


def supported_languages() -> list[str]:
    return ["python"]


def detect_languages(target: Union[str, Path]) -> list[str]:
    root = Path(target)
    return ["python"] if any(root.rglob("*.py")) else []
