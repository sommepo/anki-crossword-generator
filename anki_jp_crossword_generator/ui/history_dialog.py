# SPDX-License-Identifier: GPL-3.0-or-later
"""Small modeless browser for saved crossword snapshots."""

from __future__ import annotations

from typing import Callable

from aqt.qt import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    Qt,
    QVBoxLayout,
    QWidget,
    qconnect,
)

from ..history import HistoryRecord, delete_history_record, history_path, load_history
from .windowing import anki_window_parent, crossword_window_flags, prepare_crossword_window


class HistoryDialog(QWidget):
    """Open or remove profile-local crossword snapshots."""

    def __init__(
        self,
        mw,
        on_open: Callable[[HistoryRecord, str], None],
        parent=None,
    ) -> None:
        super().__init__(anki_window_parent(parent), crossword_window_flags())
        self._path = history_path(mw)
        self._on_open = on_open
        self._records: list[HistoryRecord] = []
        self.setWindowTitle("Crossword history")
        prepare_crossword_window(self)
        self.resize(620, 460)
        self.setMinimumSize(460, 300)

        root = QVBoxLayout(self)
        self.summary = QLabel("")
        root.addWidget(self.summary)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        qconnect(self.list.itemDoubleClicked, lambda _item: self._open("interactive"))
        root.addWidget(self.list, 1)

        actions = QHBoxLayout()
        self.open_anki = QPushButton("Open in Anki")
        qconnect(self.open_anki.clicked, lambda: self._open("interactive"))
        actions.addWidget(self.open_anki)
        self.open_pdf = QPushButton("Open PDF preview")
        qconnect(self.open_pdf.clicked, lambda: self._open("pdf_preview"))
        actions.addWidget(self.open_pdf)
        self.delete = QPushButton("Remove")
        qconnect(self.delete.clicked, self._delete)
        actions.addWidget(self.delete)
        actions.addStretch(1)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        qconnect(buttons.rejected, self.close)
        qconnect(buttons.accepted, self.close)
        root.addWidget(buttons)
        self._reload()

    def _reload(self) -> None:
        self._records = load_history(self._path)
        self.list.clear()
        for record in self._records:
            puzzle = record.puzzle
            label = (
                f"{_display_time(record.created_at)} - {puzzle.placed_count} clues - "
                f"{puzzle.language.title()} - seed {puzzle.seed}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, record.id)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
            self.summary.setText(
                f"{len(self._records)} saved puzzle"
                f"{'s' if len(self._records) != 1 else ''} in this Anki profile."
            )
        else:
            self.summary.setText("No saved puzzles yet. Generate a crossword to add one here.")
        self._set_actions_enabled(bool(self._records))

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.open_anki.setEnabled(enabled)
        self.open_pdf.setEnabled(enabled)
        self.delete.setEnabled(enabled)

    def _current(self) -> HistoryRecord | None:
        row = self.list.currentRow()
        return self._records[row] if 0 <= row < len(self._records) else None

    def _open(self, output: str) -> None:
        record = self._current()
        if record is not None:
            self._on_open(record, output)

    def _delete(self) -> None:
        record = self._current()
        if record is None:
            return
        delete_history_record(self._path, record.id)
        self._reload()


def _display_time(value: str) -> str:
    """Turn a UTC ISO timestamp into a compact, readable history label."""
    try:
        from datetime import datetime

        return datetime.fromisoformat(value).astimezone().strftime("%d %b %Y, %H:%M")
    except ValueError:
        return value
