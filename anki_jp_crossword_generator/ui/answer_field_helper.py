"""Small, opt-in UI for preparing a clean Native crossword-answer field."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from aqt.qt import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    qconnect,
)
from aqt.utils import showInfo, tooltip

from ..answers.backfill import BackfillPreview, preview_backfill
from ..vocabulary.query import build_search_query


class AnswerFieldHelperDialog(QDialog):
    """Preview and fill blank target fields from one selected source field."""

    def __init__(
        self,
        session: Any,
        fields: tuple[str, ...],
        parent: QWidget,
        *,
        default_source: str = "",
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._rows: tuple[BackfillPreview, ...] = ()
        self.setWindowTitle("Prepare Native crossword answers")
        self.resize(760, 520)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Create a dedicated answer field and fill blank values only. "
            "The first usable headword is taken from the source field; existing "
            "answers are never changed."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        self.source = QLineEdit()
        self.source.setPlaceholderText("Source field, e.g. englishWord or Meaning")
        self.source.setText(default_source or (fields[0] if fields else ""))
        self.target = QLineEdit("Crossword Answer")
        self.target.setToolTip("This field is added to relevant note types if needed.")
        form.addRow("Source field", self.source)
        form.addRow("New / target field", self.target)
        root.addLayout(form)

        controls = QHBoxLayout()
        preview = QPushButton("Preview changes")
        qconnect(preview.clicked, self._preview)
        controls.addWidget(preview)
        self.apply_button = QPushButton("Fill blank fields")
        self.apply_button.setEnabled(False)
        qconnect(self.apply_button.clicked, self._apply)
        controls.addWidget(self.apply_button)
        controls.addStretch(1)
        root.addLayout(controls)

        self.summary = QLabel("Choose a source field, then preview the changes.")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(("Note type", "Source", "Answer"))
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 380)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        qconnect(buttons.rejected, self.close)
        root.addWidget(buttons)

    def _preview(self) -> None:
        source = self.source.text().strip()
        target = self.target.text().strip()
        if not source or not target:
            tooltip("Enter both a source field and a target field name.")
            return
        col = getattr(self._session.collection, "_col", None)
        if col is None:
            tooltip("This helper is available only inside Anki.")
            return
        settings = replace(self._session.settings, answer_field="", clue_field="")
        query = build_search_query(settings)
        try:
            note_ids = [int(note_id) for note_id in col.find_notes(query)]
            notes = [_snapshot(col.get_note(note_id), note_id) for note_id in note_ids]
        except Exception as exc:  # noqa: BLE001 - present an actionable Anki error
            showInfo(f"Could not read the selected notes:\n\n{exc}")
            return
        self._rows = preview_backfill(notes, source_field=source, target_field=target)
        usable = [row for row in self._rows if row.can_fill]
        self.summary.setText(
            f"{len(usable):,} blank fields can be filled from {len(note_ids):,} matching notes. "
            "Existing target values are skipped."
        )
        self.table.setRowCount(len(usable))
        for index, row in enumerate(usable[:500]):
            self.table.setItem(index, 0, QTableWidgetItem(row.note_type))
            self.table.setItem(index, 1, QTableWidgetItem(row.source_text))
            self.table.setItem(index, 2, QTableWidgetItem(row.answer))
        if len(usable) > 500:
            self.table.setRowCount(500)
            self.summary.setText(self.summary.text() + " Showing the first 500.")
        self.apply_button.setEnabled(bool(usable))

    def _apply(self) -> None:
        if not self._rows:
            return
        source = self.source.text().strip()
        target = self.target.text().strip()
        col = getattr(self._session.collection, "_col", None)
        if col is None:
            return
        wanted = {row.note_id: row.answer for row in self._rows if row.can_fill}
        if not wanted:
            return
        try:
            models: dict[int, Any] = {}
            for note_id in wanted:
                note = col.get_note(note_id)
                model = note.note_type() if hasattr(note, "note_type") else note.model()
                models[int(model["id"])] = model
            for model in models.values():
                _ensure_field(col, model, target)
            updated = 0
            for note_id, answer in wanted.items():
                note = col.get_note(note_id)
                if str(note[target] or "").strip():
                    continue
                note[target] = answer
                col.update_note(note)
                updated += 1
        except Exception as exc:  # noqa: BLE001
            showInfo(f"Could not update the answer field:\n\n{exc}")
            return
        self.summary.setText(f"Filled {updated:,} blank {target} fields. Existing values were left unchanged.")
        self.apply_button.setEnabled(False)
        try:
            self._session.set_profile_answer_field("native", target)
        except Exception:
            pass
        showInfo(f"Filled {updated:,} blank fields. You can now choose {target} as the Native answer field.")


def _snapshot(note: Any, note_id: int) -> dict[str, object]:
    model = note.note_type() if hasattr(note, "note_type") else note.model()
    fields = {str(name): str(note[name] or "") for name in note.keys()}
    return {"note_id": note_id, "note_type": str(model.get("name", "")), "fields": fields}


def _ensure_field(col: Any, model: Any, field_name: str) -> None:
    names = {str(field.get("name", "")) for field in model.get("flds", [])}
    if field_name in names:
        return
    manager = col.models
    if hasattr(manager, "new_field") and hasattr(manager, "add_field"):
        manager.add_field(model, manager.new_field(field_name))
        return
    field = {"name": field_name, "ord": len(model.get("flds", [])), "sticky": False, "rtl": False, "font": "Arial", "size": 20, "description": ""}
    model["flds"].append(field)
    if hasattr(manager, "update_dict"):
        manager.update_dict(model)
    else:
        manager.save(model)
