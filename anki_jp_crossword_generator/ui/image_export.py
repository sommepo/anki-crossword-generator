# SPDX-License-Identifier: GPL-3.0-or-later
"""File-dialog bridge for PNG and SVG crossword exports."""

from __future__ import annotations

from pathlib import Path

from aqt.qt import QFileDialog
from aqt.utils import showInfo

from ..crossword.puzzle import Puzzle
from ..export import (
    ExportError,
    export_answer_png,
    export_answer_svg,
    export_puzzle_png,
    export_puzzle_svg,
)


def save_image(
    parent, puzzle: Puzzle, title: str, *, answer_key: bool, format_name: str
) -> Path | None:
    """Ask for an image destination and export the current preview variant."""
    format_key = format_name.casefold()
    if format_key not in {"png", "svg"}:
        raise ValueError(f"Unsupported image format: {format_name}")
    kind = "answer key" if answer_key else "puzzle"
    stem = "answer-key" if answer_key else "puzzle"
    upper = format_key.upper()
    path_text, _selected = QFileDialog.getSaveFileName(
        parent,
        f"Save {kind.title()} {upper}",
        f"{stem}.{format_key}",
        f"{upper} files (*.{format_key})",
    )
    if not path_text:
        return None
    path = Path(path_text)
    if path.suffix.casefold() != f".{format_key}":
        path = path.with_suffix(f".{format_key}")
    try:
        if format_key == "png":
            (export_answer_png if answer_key else export_puzzle_png)(
                path, puzzle, title=title
            )
        else:
            (export_answer_svg if answer_key else export_puzzle_svg)(
                path, puzzle, title=title
            )
    except ExportError as exc:
        showInfo(str(exc), parent=parent)
        return None
    except Exception as exc:  # defensive: no traceback in normal Anki use
        showInfo(f"Could not save the {upper}: {exc}", parent=parent)
        return None
    return path
