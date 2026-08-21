"""Optional JMdict-backed preparation of Native crossword answer fields."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from aqt.qt import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    qconnect,
)
from aqt.utils import askUser, showInfo, showWarning, tooltip

from ..answers.jmdict import JmdictIndex, download_jmdict, find_local_json
from ..vocabulary.query import build_search_query
from ..vocabulary.text import strip_anki_html


class JmdictBackfillDialog(QDialog):
    """Fill blank Native-answer fields from a locally downloaded JMdict index."""

    def __init__(self, session: Any, parent: QWidget, *, word: str, reading: str, target: str) -> None:
        super().__init__(parent)
        self._session = session
        self._index = JmdictIndex()
        self.setWindowTitle("Backfill Native answers from JMdict")
        self.resize(600, 410)
        root = QVBoxLayout(self)
        intro = QLabel(
            "Look up the Japanese word in JMdict and write its English gloss list into "
            "the selected Native answer field. Dictionary data is downloaded only if you request it, "
            "then used locally. Blank targets are filled; existing values are kept."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        form = QFormLayout()
        self.word = QLineEdit(word)
        self.reading = QLineEdit(reading)
        self.target = QLineEdit(target)
        self.maximum = QSpinBox()
        self.maximum.setRange(1, 20)
        self.maximum.setValue(8)
        self.common = QCheckBox("Prefer common dictionary entries")
        form.addRow("Japanese word field", self.word)
        form.addRow("Reading field", self.reading)
        form.addRow("Native answer field", self.target)
        form.addRow("Maximum glosses", self.maximum)
        form.addRow("", self.common)
        root.addLayout(form)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        actions = QHBoxLayout()
        download = QPushButton("Download / update JMdict…")
        qconnect(download.clicked, self._download)
        actions.addWidget(download)
        fill = QPushButton("Fill blank fields")
        qconnect(fill.clicked, self._fill)
        actions.addWidget(fill)
        actions.addStretch(1)
        root.addLayout(actions)
        attribution = QLabel("Dictionary: jmdict-simplified / JMdict (downloaded separately)")
        attribution.setStyleSheet("color: palette(placeholder-text);")
        root.addWidget(attribution)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        qconnect(buttons.rejected, self.close)
        root.addWidget(buttons)
        self._load_local()

    def _addon_dir(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def _load_local(self) -> bool:
        path = find_local_json(self._addon_dir())
        if path is None:
            self.status.setText("JMdict is not downloaded yet.")
            return False
        try:
            self._index.load_json_file(path)
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"Could not load the local dictionary: {exc}")
            return False
        self.status.setText(f"JMdict ready: {self._index.word_count:,} entries.")
        return True

    def _download(self) -> None:
        if not askUser("Download or update the English JMdict data now?\n\nThis uses the internet once and stores the dictionary locally."):
            return
        try:
            from aqt import mw

            mw.progress.start(label="Downloading JMdict…", immediate=True)
            path = download_jmdict(self._addon_dir(), lambda text: mw.progress.update(label=text))
            self._index.load_json_file(path)
        except Exception as exc:  # noqa: BLE001
            showWarning(f"Dictionary download failed:\n\n{exc}")
            return
        finally:
            try:
                mw.progress.finish()
            except Exception:
                pass
        self.status.setText(f"JMdict ready: {self._index.word_count:,} entries.")

    def _fill(self) -> None:
        word_field, reading_field, target_field = (self.word.text().strip(), self.reading.text().strip(), self.target.text().strip())
        if not word_field or not target_field:
            tooltip("Choose a Japanese word field and a Native answer field.")
            return
        if word_field == target_field:
            tooltip("The Japanese word field and Native answer field must be different.")
            return
        if not self._index.ready and not self._load_local():
            tooltip("Download JMdict first.")
            return
        col = getattr(self._session.collection, "_col", None)
        if col is None:
            return
        settings = replace(self._session.settings, answer_field="", clue_field="")
        try:
            note_ids = [int(note_id) for note_id in col.find_notes(build_search_query(settings))]
        except Exception as exc:  # noqa: BLE001
            showWarning(f"Could not read matching notes:\n\n{exc}")
            return
        if not askUser(f"Look up and fill blank {target_field} values for {len(note_ids):,} matching notes?"):
            return
        updated = missing = skipped = 0
        try:
            from aqt import mw

            mw.checkpoint("Anki Crossword Generator: JMdict backfill")
            mw.progress.start(max=len(note_ids), label="Looking up JMdict…", immediate=True)
            for position, note_id in enumerate(note_ids, 1):
                mw.progress.update(value=position, max=len(note_ids), label=f"Looking up JMdict… {position:,}/{len(note_ids):,}")
                note = col.get_note(note_id)
                if word_field not in note or target_field not in note or str(note[target_field] or "").strip():
                    skipped += 1
                    continue
                word = strip_anki_html(str(note[word_field] or ""))
                reading = strip_anki_html(str(note[reading_field] or "")) if reading_field and reading_field in note else ""
                glosses = self._index.lookup_glosses(word, reading, max_glosses=self.maximum.value(), prefer_common=self.common.isChecked())
                if not glosses:
                    missing += 1
                    continue
                note[target_field] = glosses
                col.update_note(note)
                updated += 1
        except Exception as exc:  # noqa: BLE001
            showWarning(f"JMdict backfill stopped:\n\n{exc}")
            return
        finally:
            try:
                mw.progress.finish()
                mw.reset()
            except Exception:
                pass
        self._session.set_profile_answer_field("native", target_field)
        self.status.setText(f"Updated {updated:,}; no dictionary match {missing:,}; kept / skipped {skipped:,}.")
        showInfo(self.status.text())
