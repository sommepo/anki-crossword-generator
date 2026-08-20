# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt file-dialog bridge for the standalone PDF renderer."""

from __future__ import annotations

from pathlib import Path

from aqt.qt import QFileDialog
from aqt.utils import showInfo

from ..crossword.puzzle import Puzzle
from ..export.pdf import ExportError, export_answer_pdf, export_puzzle_pdf


def save_pdf(parent, puzzle: Puzzle, title: str, *, answer_key: bool) -> Path | None:
    """Ask for a destination and write either a puzzle or answer-key PDF."""
    kind = "answer key" if answer_key else "puzzle"
    stem = "answer-key" if answer_key else "puzzle"
    path_text, _selected = QFileDialog.getSaveFileName(
        parent,
        f"Save {kind.title()} PDF",
        f"{stem}.pdf",
        "PDF files (*.pdf)",
    )
    if not path_text:
        return None
    path = Path(path_text)
    if path.suffix.casefold() != ".pdf":
        path = path.with_suffix(".pdf")
    try:
        if answer_key:
            export_answer_pdf(path, puzzle, title=title)
        else:
            export_puzzle_pdf(path, puzzle, title=title)
    except ExportError as exc:
        showInfo(str(exc), parent=parent)
        return None
    except Exception as exc:  # defensive: no traceback in normal Anki use
        showInfo(f"Could not save the PDF: {exc}", parent=parent)
        return None
    return path
