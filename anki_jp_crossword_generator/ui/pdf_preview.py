# SPDX-License-Identifier: GPL-3.0-or-later
"""In-Anki print preview for the newspaper-style PDF renderer."""

from __future__ import annotations

from aqt.qt import (
    QComboBox,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    qconnect,
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrintPreviewWidget, QPrinter
from aqt.utils import tooltip

from ..crossword.puzzle import Puzzle
from ..export.pdf import configure_a4_device, render_to_device
from ..session import CrosswordSession
from .image_export import save_image
from .pdf_export import save_pdf
from .windowing import anki_window_parent, crossword_window_flags, prepare_crossword_window


class PdfPreviewDialog(QWidget):
    """Preview an empty puzzle or answer key before choosing a file path."""

    def __init__(self, session: CrosswordSession, puzzle: Puzzle, title: str, parent=None) -> None:
        super().__init__(anki_window_parent(parent), crossword_window_flags())
        self.session = session
        self.puzzle = puzzle
        self.title = title
        self._answer_key = False
        self.setWindowTitle(f"PDF preview - {title}")
        prepare_crossword_window(self)
        self.resize(1120, 850)
        self.setMinimumSize(760, 600)

        self._printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self._printer.setResolution(300)
        self._printer.setDocName(title)
        configure_a4_device(self._printer, puzzle)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Preview"))
        self.kind = QComboBox()
        self.kind.addItem("Puzzle", False)
        self.kind.addItem("Answer key", True)
        qconnect(self.kind.currentIndexChanged, self._on_kind_changed)
        controls.addWidget(self.kind)
        controls.addStretch(1)
        root.addLayout(controls)

        self.preview = QPrintPreviewWidget(self._printer, self)
        self.preview.setZoomMode(QPrintPreviewWidget.ZoomMode.FitInView)
        qconnect(self.preview.paintRequested, self._paint_requested)
        root.addWidget(self.preview, 1)

        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton(
            "Save PDF", QDialogButtonBox.ButtonRole.ActionRole
        )
        qconnect(self.save_button.clicked, self._save)
        self.png_button = buttons.addButton(
            "Save PNG", QDialogButtonBox.ButtonRole.ActionRole
        )
        qconnect(self.png_button.clicked, lambda _checked=False: self._save_image("png"))
        self.svg_button = buttons.addButton(
            "Save SVG", QDialogButtonBox.ButtonRole.ActionRole
        )
        qconnect(self.svg_button.clicked, lambda _checked=False: self._save_image("svg"))
        self.print_button = buttons.addButton(
            "Print", QDialogButtonBox.ButtonRole.ActionRole
        )
        qconnect(self.print_button.clicked, self._print)
        self.mark_solved_button = buttons.addButton(
            "Mark puzzle solved", QDialogButtonBox.ButtonRole.ActionRole
        )
        qconnect(self.mark_solved_button.clicked, self._mark_solved)
        close = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        qconnect(close.clicked, self.close)
        root.addWidget(buttons)
        self.preview.updatePreview()

    def _on_kind_changed(self, _index: int) -> None:
        self._answer_key = bool(self.kind.currentData())
        self.preview.updatePreview()

    def _paint_requested(self, printer) -> None:
        render_to_device(
            printer,
            self.puzzle,
            title=self.title,
            include_answers=self._answer_key,
        )

    def _save(self) -> None:
        path = save_pdf(self, self.puzzle, self.title, answer_key=self._answer_key)
        if path is not None:
            tooltip(f"Saved PDF: {path.name}")

    def _save_image(self, format_name: str) -> None:
        save_image(
            self,
            self.puzzle,
            self.title,
            answer_key=self._answer_key,
            format_name=format_name,
        )

    def _print(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setResolution(300)
        printer.setDocName(self.title)
        configure_a4_device(printer, self.puzzle)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Anki Crossword")
        if not dialog.exec():
            return
        try:
            render_to_device(
                printer,
                self.puzzle,
                title=self.title,
                include_answers=self._answer_key,
            )
            tooltip("Sent crossword to printer")
        except Exception as exc:
            from aqt.utils import showInfo

            showInfo(f"Could not print the crossword: {exc}", parent=self)

    def _mark_solved(self) -> None:
        updated, _tag = self.session.mark_puzzle_solved(self.puzzle)
        self.mark_solved_button.setEnabled(False)
        self.mark_solved_button.setText(
            "Marked solved" if updated else "Already marked solved"
        )
