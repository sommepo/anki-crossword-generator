# SPDX-License-Identifier: GPL-3.0-or-later
"""Phase 4 configuration window: dual profiles, preview, and crossword generation."""

from __future__ import annotations

from typing import Any

from aqt.qt import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    QVBoxLayout,
    QWidget,
    qconnect,
)
from aqt.utils import showInfo, tooltip

from ..anki.browser import browse_note, parse_note_id
from ..anki.errors import SearchQueryError
from ..crossword.errors import GenerationError
from ..session import CrosswordSession
from .windowing import (
    anki_window_parent,
    bring_crossword_window_to_front,
    crossword_window_flags,
    prepare_crossword_window,
    restore_anki,
)
from ..settings import (
    CLUE_MARK_COLOR_LABELS,
    CLUE_MARK_COLORS,
    CLUE_MARK_STYLE_LABELS,
    CLUE_MARK_STYLES,
    CLUE_MARK_TEXT_COLORS,
    CLUE_MARK_TEXT_LABELS,
    SELECTION_MODES,
)
from ..version import ADDON_NAME
from ..normalization.base import language_label
from ..vocabulary.text import anki_html_for_preview

MODE_LABELS = {
    "search": "Listed order",
    "random": "Random",
    "due": "Prefer due",
    "selected": "Selected in Browse",
}

SELECT_DECK = "Select a deck…"
VALID_COLUMNS = ("Answer", "Language", "Cells", "Clue")
SKIPPED_COLUMNS = ("Include", "Answer", "Language", "Cells", "Clue", "Status")


class MainDialog(QWidget):
    """Primary Tools → Anki Crossword Generator window."""

    def __init__(
        self,
        session: CrosswordSession,
        parent: QWidget | None = None,
        on_close=None,
        on_settings_changed=None,
    ) -> None:
        super().__init__(anki_window_parent(parent), crossword_window_flags())
        self.session = session
        self._on_close = on_close
        self._on_settings_changed = on_settings_changed
        self._busy = False
        self._preview_language: str | None = None
        self._preview_note_ids: list[int] = []
        self._puzzle_dialog = None
        self._pdf_preview_dialog = None
        self._history_dialog = None
        self.setWindowTitle(ADDON_NAME)
        prepare_crossword_window(self)
        self.resize(1280, 1000)
        self.setMinimumSize(1000, 900)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        intro = QLabel(
            "Choose a deck, then set Native → Japanese and Japanese → Native fields "
            "independently. Preview one language at a time, then generate a grid. "
            "Click a cell or clue and type to fill the grid. Check marks "
            "correct and incorrect cells. Choose whether to open the puzzle here "
            "or preview a printable PDF."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        controls = self._build_controls()
        controls.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        root.addWidget(controls)
        root.addWidget(self._build_preview_box(), 1)

        self.status = QLabel(
            "Choose a deck, then click Preview Native → Japanese or Preview Japanese → Native."
        )
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        buttons = QHBoxLayout()
        self.generate_japanese_btn = QPushButton("Generate Native → Japanese")
        self.generate_japanese_btn.setEnabled(False)
        qconnect(
            self.generate_japanese_btn.clicked,
            lambda _checked=False: self._on_generate("japanese"),
        )
        buttons.addWidget(self.generate_japanese_btn)

        self.generate_native_btn = QPushButton("Generate Japanese → Native")
        self.generate_native_btn.setEnabled(False)
        qconnect(
            self.generate_native_btn.clicked,
            lambda _checked=False: self._on_generate("native"),
        )
        buttons.addWidget(self.generate_native_btn)
        buttons.addSpacing(12)
        buttons.addWidget(QLabel("Open in"))
        self.output = QComboBox()
        self.output.addItem("Within Anki", "interactive")
        self.output.addItem("PDF preview", "pdf_preview")
        self.output.setToolTip(
            "Within Anki opens the interactive solver. PDF preview lets you inspect "
            "the printable puzzle or answer key before saving it."
        )
        qconnect(self.output.currentIndexChanged, self._on_output_changed)
        buttons.addWidget(self.output)
        self.history_btn = QPushButton("History")
        self.history_btn.setToolTip("Open a previously generated crossword.")
        qconnect(self.history_btn.clicked, self._open_history)
        buttons.addWidget(self.history_btn)
        buttons.addStretch(1)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        qconnect(box.rejected, self.close)
        qconnect(box.accepted, self.close)
        buttons.addWidget(box)
        root.addLayout(buttons)

        self._load_from_settings()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        puzzle = self._puzzle_dialog
        if puzzle is not None:
            try:
                puzzle.close()
            except Exception:
                pass
            self._puzzle_dialog = None
        pdf_preview = self._pdf_preview_dialog
        if pdf_preview is not None:
            try:
                pdf_preview.close()
            except Exception:
                pass
            self._pdf_preview_dialog = None
        history = self._history_dialog
        if history is not None:
            try:
                history.close()
            except Exception:
                pass
            self._history_dialog = None
        callback = self._on_close
        self._on_close = None
        if callback is not None:
            try:
                callback()
            except Exception:
                pass
        restore_anki()
        super().closeEvent(event)

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        shared = QHBoxLayout()
        shared.setSpacing(12)
        shared.addWidget(self._build_deck_box(), 1)
        shared.addWidget(self._build_state_box(), 1)
        shared.addWidget(self._build_pick_box(), 1)
        layout.addLayout(shared)

        profiles = QHBoxLayout()
        profiles.setSpacing(12)
        profiles.setAlignment(Qt.AlignmentFlag.AlignTop)
        profiles.addWidget(self._build_profile_box("japanese"), 1)
        profiles.addWidget(self._build_profile_box("native"), 1)
        layout.addLayout(profiles)
        return panel

    def _build_deck_box(self) -> QGroupBox:
        deck_box = QGroupBox("Collection")
        deck_form = _form_layout(deck_box)
        self.deck = QComboBox()
        self.deck.setMaxVisibleItems(24)
        _fit_combo(self.deck)
        qconnect(self.deck.currentIndexChanged, self._on_deck_changed)
        deck_form.addRow("Deck", self.deck)

        self.extra_query = QLineEdit()
        self.extra_query.setPlaceholderText("Optional extra filter, e.g. tag::N2")
        self.extra_query.setClearButtonEnabled(True)
        _fit_line(self.extra_query)
        qconnect(self.extra_query.returnPressed, self._on_extra_return)
        deck_form.addRow("Extra search", self.extra_query)
        return deck_box

    def _build_profile_box(self, language: str) -> QGroupBox:
        japanese = language == "japanese"
        box = QGroupBox("Native → Japanese" if japanese else "Japanese → Native")
        # Keep the action controls visible even when Qt initially distributes
        # space to the preview table before the window has been resized once.
        # Both profiles must always show their checkbox and Preview button.
        # The table below is deliberately allowed to shrink before this panel.
        box.setFixedHeight(300 if not japanese else 260)
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        form = _form_layout(box)

        answer = QComboBox()
        answer.setEditable(True)
        answer.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        clue = QComboBox()
        clue.setEditable(True)
        clue.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        _fit_combo(answer)
        _fit_combo(clue)
        qconnect(answer.currentIndexChanged, lambda _i, lang=language: self._on_answer_changed(lang))
        qconnect(clue.currentIndexChanged, lambda _i, lang=language: self._on_clue_changed(lang))
        if japanese:
            answer_tip = "(e.g. Japanese reading)"
            clue_tip = "(e.g. Native word or sentence)"
        else:
            answer_tip = "(e.g. Native word)"
            clue_tip = "(e.g. Japanese word or sentence)"
        form.addRow("Answer field", _combo_with_tip(answer, answer_tip))
        form.addRow("Clue field", _combo_with_tip(clue, clue_tip))

        template = QLineEdit()
        template.setPlaceholderText("{{Meaning}} — {{Example}}")
        template.setToolTip(
            "Build the clue from note fields. Pick a field to insert {{FieldName}}, "
            "or type placeholders. Leave blank to use the Clue field only."
        )
        _fit_line(template)
        qconnect(template.editingFinished, lambda lang=language: self._on_template_changed(lang))

        picker = QComboBox()
        picker.setMaxVisibleItems(24)
        picker.setToolTip("Insert a note field into the clue template.")
        _fit_combo(picker)
        picker.setMinimumContentsLength(12)
        picker.addItem("Insert field…", "")
        picker.setEnabled(False)
        qconnect(
            picker.activated,
            lambda index, lang=language: self._on_template_field_picked(lang, index),
        )

        builder = QWidget()
        builder_row = QHBoxLayout(builder)
        builder_row.setContentsMargins(0, 0, 0, 0)
        builder_row.setSpacing(8)
        builder_row.addWidget(template, 1)
        builder_row.addWidget(picker, 0)
        form.addRow("Clue template builder", builder)

        if not japanese:
            self.na_max_words = QComboBox()
            self.na_max_words.addItem("None", 0)
            self.na_max_words.addItem("1 word", 1)
            self.na_max_words.addItem("2 words", 2)
            self.na_max_words.addItem("3 words", 3)
            self.na_max_words.setToolTip(
                "Limit Native answers to this many words. "
                "None keeps one-word answers and longer phrases."
            )
            _fit_combo(self.na_max_words)
            qconnect(
                self.na_max_words.currentIndexChanged,
                self._on_native_max_words_changed,
            )
            form.addRow("Maximum answer words", self.na_max_words)
            prepare_answers = QPushButton("Backfill Native answers from JMdict…")
            prepare_answers.setToolTip(
                "Look up Japanese words in the optional, locally stored JMdict "
                "data and fill blank values in the selected Native answer field."
            )
            qconnect(prepare_answers.clicked, self._open_jmdict_backfill)
            form.addRow("", prepare_answers)

        preview = QPushButton(
            "Preview Native → Japanese" if japanese else "Preview Japanese → Native"
        )
        preview.setMinimumHeight(32)
        if japanese:
            preview.setDefault(True)
        qconnect(
            preview.clicked,
            lambda _checked=False, lang=language: self._on_preview(lang),
        )
        form.addRow("", preview)

        if japanese:
            self.ja_answer = answer
            self.ja_clue = clue
            self.ja_template = template
            self.ja_field_picker = picker
            self.preview_japanese_btn = preview
        else:
            self.na_answer = answer
            self.na_clue = clue
            self.na_template = template
            self.na_field_picker = picker
            self.preview_native_btn = preview
        return box

    def _open_jmdict_backfill(self) -> None:
        """Open the optional JMdict-backed Native answer-field backfill."""
        if not self.deck.currentData():
            tooltip("Choose a deck first.")
            return
        from .jmdict_backfill import JmdictBackfillDialog

        helper = getattr(self, "_jmdict_backfill", None)
        if helper is not None:
            try:
                if helper.isVisible():
                    helper.raise_()
                    helper.activateWindow()
                    return
            except RuntimeError:
                pass
        self._sync_shared_from_widgets()
        helper = JmdictBackfillDialog(
            self.session,
            self,
            word="wordDictionaryForm",
            reading=self.ja_answer.currentText(),
            target=self.na_answer.currentText().strip() or "englishWord",
        )
        helper.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        helper.destroyed.connect(lambda *_args: setattr(self, "_jmdict_backfill", None))
        self._jmdict_backfill = helper
        helper.show()

    def _build_state_box(self) -> QGroupBox:
        state_box = QGroupBox("Card states")
        grid = QGridLayout(state_box)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        self.include_due = QCheckBox("Due now")
        self.include_learn = QCheckBox("Learning")
        self.include_review = QCheckBox("Review")
        self.include_new = QCheckBox("New / unreviewed")
        self.include_suspended = QCheckBox("Suspended")
        self.include_solved = QCheckBox("Solved crosswords")
        boxes = (
            self.include_due,
            self.include_learn,
            self.include_review,
            self.include_new,
            self.include_suspended,
            self.include_solved,
        )
        for index, box_w in enumerate(boxes):
            qconnect(box_w.toggled, self._on_state_toggled)
            grid.addWidget(box_w, index // 3, index % 3)
        return state_box

    def _build_pick_box(self) -> QGroupBox:
        pick_box = QGroupBox("How to pick words")
        pick_form = _form_layout(pick_box)
        self.mode = QComboBox()
        for key in SELECTION_MODES:
            self.mode.addItem(MODE_LABELS[key], key)
        _fit_combo(self.mode)
        qconnect(self.mode.currentIndexChanged, self._on_mode_changed)
        pick_form.addRow("Pick", self.mode)

        self.word_count = QSpinBox()
        self.word_count.setRange(1, 80)
        _fit_spin(self.word_count)
        qconnect(self.word_count.valueChanged, self._on_count_changed)
        pick_form.addRow("Number of words", self.word_count)

        self.min_length = QSpinBox()
        self.min_length.setRange(1, 10)
        _fit_spin(self.min_length)
        qconnect(self.min_length.valueChanged, self._on_min_length_changed)
        pick_form.addRow("Minimum cells", self.min_length)

        anki_only = QLabel("In-Anki clue styling")
        anki_only.setToolTip("PDF clues use bold underlining for marked words.")
        pick_form.addRow("", anki_only)

        self.mark_style = QComboBox()
        for key in CLUE_MARK_STYLES:
            self.mark_style.addItem(CLUE_MARK_STYLE_LABELS[key], key)
        _fit_combo(self.mark_style)
        self.mark_style.setToolTip(
            "How words that are bold or highlighted on the card appear in clues."
        )
        qconnect(self.mark_style.currentIndexChanged, self._on_mark_style_changed)
        pick_form.addRow("Marked words", self.mark_style)

        self.mark_color = QComboBox()
        for key in CLUE_MARK_COLORS:
            self.mark_color.addItem(CLUE_MARK_COLOR_LABELS[key], key)
        _fit_combo(self.mark_color)
        self.mark_color.setToolTip("Background colour behind marked words.")
        qconnect(self.mark_color.currentIndexChanged, self._on_mark_color_changed)
        pick_form.addRow("Highlight", self.mark_color)

        self.mark_text = QComboBox()
        for key in CLUE_MARK_TEXT_COLORS:
            self.mark_text.addItem(CLUE_MARK_TEXT_LABELS[key], key)
        _fit_combo(self.mark_text)
        self.mark_text.setToolTip("Text colour of marked words.")
        qconnect(self.mark_text.currentIndexChanged, self._on_mark_text_changed)
        pick_form.addRow("Text colour", self.mark_text)

        self.seed_label = QLabel("")
        pick_form.addRow("Seed", self.seed_label)
        return pick_box

    def _build_preview_box(self) -> QGroupBox:
        box = QGroupBox("Preview")
        box.setMinimumHeight(190)
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(box)
        self.counts = QLabel("No preview yet.")
        self.counts.setWordWrap(True)
        layout.addWidget(self.counts)

        self.show_skipped = QCheckBox("Show skipped notes")
        qconnect(self.show_skipped.toggled, self._on_show_skipped_toggled)
        layout.addWidget(self.show_skipped)

        self.table = QTableWidget(0, len(VALID_COLUMNS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        self.table.setMinimumHeight(110)
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored
        )
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setToolTip(
            "Double-click a row, right-click, or use Open in Browse to show the note in the Browser."
        )
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        qconnect(self.table.cellDoubleClicked, self._on_preview_double_clicked)
        qconnect(self.table.customContextMenuRequested, self._on_preview_menu)
        self._apply_table_headers(show_skipped=False)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.browse_btn = QPushButton("Open in Browse")
        self.browse_btn.setEnabled(False)
        self.browse_btn.setToolTip(
            "Open the selected note in Anki's Browse window."
        )
        qconnect(self.browse_btn.clicked, self._on_browse_clicked)
        qconnect(self.table.itemSelectionChanged, self._update_browse_button)
        actions.addWidget(self.browse_btn)
        actions.addStretch(1)
        layout.addLayout(actions)
        return box

    def _load_from_settings(self) -> None:
        settings = self.session.settings
        self._fill_decks(settings.deck_name)
        self.extra_query.setText(settings.extra_query)
        self._set_checkbox(self.include_due, settings.include_due)
        self._set_checkbox(self.include_learn, settings.include_learn)
        self._set_checkbox(self.include_review, settings.include_review)
        self._set_checkbox(self.include_new, settings.include_new)
        self._set_checkbox(self.include_suspended, settings.include_suspended)
        self._set_checkbox(self.include_solved, settings.include_solved)
        index = self.mode.findData(settings.selection_mode)
        self.mode.blockSignals(True)
        self.mode.setCurrentIndex(index if index >= 0 else 0)
        self.mode.blockSignals(False)
        self.word_count.blockSignals(True)
        self.word_count.setValue(settings.target_word_count)
        self.word_count.blockSignals(False)
        output_index = self.output.findData(settings.generation_output)
        self.output.blockSignals(True)
        self.output.setCurrentIndex(output_index if output_index >= 0 else 0)
        self.output.blockSignals(False)
        self.min_length.blockSignals(True)
        self.min_length.setValue(settings.minimum_answer_length)
        self.min_length.blockSignals(False)
        style_index = self.mark_style.findData(settings.clue_mark_style)
        self.mark_style.blockSignals(True)
        self.mark_style.setCurrentIndex(style_index if style_index >= 0 else 0)
        self.mark_style.blockSignals(False)
        color_index = self.mark_color.findData(settings.clue_mark_color)
        self.mark_color.blockSignals(True)
        self.mark_color.setCurrentIndex(color_index if color_index >= 0 else 0)
        self.mark_color.blockSignals(False)
        text_index = self.mark_text.findData(settings.clue_mark_text)
        self.mark_text.blockSignals(True)
        self.mark_text.setCurrentIndex(text_index if text_index >= 0 else 0)
        self.mark_text.blockSignals(False)
        self._update_mark_color_enabled()
        self._set_checkbox(self.show_skipped, settings.show_excluded_preview)
        self._apply_table_headers(show_skipped=settings.show_excluded_preview)
        if settings.deck_name:
            self._load_fields_for_deck()
        else:
            self._fill_profile_widgets()
        self._update_seed_label()

    def _fill_profile_widgets(self) -> None:
        settings = self.session.settings
        self._set_combo_text(self.ja_answer, settings.japanese_answer_field)
        self._set_combo_text(self.ja_clue, settings.japanese_clue_field)
        self.ja_template.blockSignals(True)
        self.ja_template.setText(settings.japanese_clue_template)
        self.ja_template.blockSignals(False)
        self._set_combo_text(self.na_answer, settings.native_answer_field)
        self._set_combo_text(self.na_clue, settings.native_clue_field)
        self.na_template.blockSignals(True)
        self.na_template.setText(settings.native_clue_template)
        self.na_template.blockSignals(False)
        max_index = self.na_max_words.findData(settings.native_max_answer_words)
        self.na_max_words.blockSignals(True)
        self.na_max_words.setCurrentIndex(max_index if max_index >= 0 else 0)
        self.na_max_words.blockSignals(False)

    def _fill_decks(self, selected: str) -> None:
        self.deck.blockSignals(True)
        self.deck.clear()
        self.deck.addItem(SELECT_DECK, "")
        for name in self.session.list_decks():
            self.deck.addItem(name, name)
        if selected:
            index = self.deck.findData(selected)
            if index < 0:
                index = self.deck.findText(selected)
            if index >= 0:
                self.deck.setCurrentIndex(index)
            else:
                self.deck.addItem(selected, selected)
                self.deck.setCurrentIndex(self.deck.count() - 1)
        else:
            self.deck.setCurrentIndex(0)
        self.deck.blockSignals(False)

    def _load_fields_for_deck(self) -> None:
        discovered = self.session.fields_for_current_deck()
        names = list(discovered)
        self.session.apply_field_suggestions(discovered)
        settings = self.session.settings
        self._replace_combo_items(self.ja_answer, names, settings.japanese_answer_field)
        self._replace_combo_items(self.ja_clue, names, settings.japanese_clue_field)
        self._replace_combo_items(self.na_answer, names, settings.native_answer_field)
        self._replace_combo_items(self.na_clue, names, settings.native_clue_field)
        self._fill_template_pickers(names)
        self._fill_profile_widgets()

    def _sync_shared_from_widgets(self) -> None:
        self.session.set_deck_name(str(self.deck.currentData() or ""))
        self.session.set_extra_query(self.extra_query.text())
        self.session.set_card_state(
            include_due=self.include_due.isChecked(),
            include_learn=self.include_learn.isChecked(),
            include_review=self.include_review.isChecked(),
            include_new=self.include_new.isChecked(),
            include_suspended=self.include_suspended.isChecked(),
            include_solved=self.include_solved.isChecked(),
        )
        self.session.set_selection_mode(str(self.mode.currentData() or "random"))
        self.session.set_target_word_count(self.word_count.value())
        self.session.set_minimum_answer_length(self.min_length.value())

    def _sync_profiles_from_widgets(self) -> None:
        self.session.set_profile_answer_field("japanese", self.ja_answer.currentText())
        self.session.set_profile_clue_field("japanese", self.ja_clue.currentText())
        self.session.set_profile_clue_template("japanese", self.ja_template.text())
        self.session.set_profile_hide_target("japanese", False)
        self.session.set_profile_answer_field("native", self.na_answer.currentText())
        self.session.set_profile_clue_field("native", self.na_clue.currentText())
        self.session.set_profile_clue_template("native", self.na_template.text())
        self.session.set_profile_hide_target("native", False)
        self.session.set_native_max_answer_words(_combo_int(self.na_max_words))

    def _on_extra_return(self) -> None:
        self._on_preview(self._preview_language or "japanese")

    def _on_preview(self, language: str) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_preview_enabled(False)
        self.status.setText("Searching…")
        progress = _progress()
        try:
            self._sync_shared_from_widgets()
            self._sync_profiles_from_widgets()
            if str(self.mode.currentData() or "random") == "random":
                self.session.new_random_seed()
            if progress is not None:
                progress.start(label="Searching collection…")
            result = self.session.search(force_reload=True, language=language)
            self._preview_language = language
            self._apply_result(result)
        except SearchQueryError as exc:
            self._show_search_error(str(exc))
        except Exception as exc:  # noqa: BLE001 - user-facing, no traceback
            self._show_search_error(
                "Something went wrong while searching the collection.\n\n"
                f"{exc}"
            )
        finally:
            if progress is not None:
                try:
                    progress.finish()
                except Exception:
                    pass
            self._busy = False
            self._set_preview_enabled(True)

    def _on_generate(self, language: str) -> None:
        if self._preview_language != language or self.session.last_result is None:
            label = "Japanese" if language == "japanese" else "Native"
            showInfo(f"Preview the {label} crossword first.")
            return
        blocked = self.session.generate_blocked_reason()
        if blocked:
            showInfo(blocked)
            return
        if self._busy:
            return
        self._busy = True
        self.generate_japanese_btn.setEnabled(False)
        self.generate_native_btn.setEnabled(False)
        progress = _progress()
        total = max(1, int(self.session.settings.candidate_count))
        try:
            if progress is not None:
                try:
                    progress.start(
                        label="Generating crossword…",
                        max=total,
                        immediate=True,
                    )
                except TypeError:
                    progress.start(label="Generating crossword…")

            def cb(done: int, count: int) -> None:
                if progress is None:
                    return
                try:
                    progress.update(
                        value=done,
                        label=f"Generating crossword… {done} / {count}",
                    )
                except TypeError:
                    progress.update(label=f"Generating crossword… {done} / {count}")

            puzzle = self.session.generate(language, progress=cb, new_seed=True)
        except GenerationError as exc:
            showInfo(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - user-facing, no traceback
            showInfo(f"Crossword generation failed.\n\n{exc}")
            return
        finally:
            if progress is not None:
                try:
                    progress.finish()
                except Exception:
                    pass
            self._busy = False
            if self.session.last_result is not None:
                self._apply_result(self.session.last_result)

        self._save_history_snapshot(puzzle)
        self._show_puzzle(puzzle, self.session.settings.generation_output)

    def _show_puzzle(self, puzzle, output: str) -> None:
        """Open a current or saved puzzle in the requested presentation."""
        language = puzzle.language
        if output == "pdf_preview":
            from .pdf_preview import PdfPreviewDialog

            if self._pdf_preview_dialog is not None:
                try:
                    self._pdf_preview_dialog.close()
                except Exception:
                    pass
            dialog = PdfPreviewDialog(
                self.session, puzzle, self._export_title(language), parent=self
            )
            self._pdf_preview_dialog = dialog
            bring_crossword_window_to_front(dialog)
            return

        from .puzzle_dialog import PuzzleDialog

        if self._puzzle_dialog is not None:
            try:
                self._puzzle_dialog.close()
            except Exception:
                pass
        dialog = PuzzleDialog(
            self.session,
            language,
            puzzle,
            parent=self,
            on_settings_changed=self._on_settings_changed,
        )
        self._puzzle_dialog = dialog
        bring_crossword_window_to_front(dialog)

    def _save_history_snapshot(self, puzzle) -> None:
        """Save generated grids independently from future Anki card edits."""
        try:
            from aqt import mw
            from ..history import history_path, save_history_record

            save_history_record(
                history_path(mw), puzzle, title=self._export_title(puzzle.language)
            )
        except Exception:
            # History is an enhancement; a write failure must not lose a puzzle.
            pass

    def _open_history(self) -> None:
        try:
            from aqt import mw
            from .history_dialog import HistoryDialog
        except Exception as exc:
            showInfo(f"Could not open crossword history: {exc}", parent=self)
            return
        if self._history_dialog is not None:
            try:
                if self._history_dialog.isVisible():
                    bring_crossword_window_to_front(self._history_dialog)
                    return
            except Exception:
                pass
        dialog = HistoryDialog(mw, self._open_history_record, parent=self)
        self._history_dialog = dialog
        bring_crossword_window_to_front(dialog)

    def _open_history_record(self, record, output: str) -> None:
        self._show_puzzle(record.puzzle, output)

    def _on_output_changed(self, _index: int) -> None:
        self.session.settings.generation_output = str(
            self.output.currentData() or "interactive"
        )

    def _export_title(self, language: str) -> str:
        del language
        return "Anki Crossword"

    def _on_deck_changed(self, _index: int) -> None:
        if self._busy:
            return
        self.session.set_deck_name(str(self.deck.currentData() or ""))
        self._load_fields_for_deck()

    def _on_state_toggled(self, _checked: bool) -> None:
        if self._busy:
            return
        self.session.set_card_state(
            include_due=self.include_due.isChecked(),
            include_learn=self.include_learn.isChecked(),
            include_review=self.include_review.isChecked(),
            include_new=self.include_new.isChecked(),
            include_suspended=self.include_suspended.isChecked(),
            include_solved=self.include_solved.isChecked(),
        )

    def _on_mode_changed(self, _index: int) -> None:
        if self._busy:
            return
        self.session.set_selection_mode(str(self.mode.currentData() or "random"))
        self._update_seed_label()

    def _on_count_changed(self, value: int) -> None:
        if self._busy:
            return
        self.session.set_target_word_count(value)
        if self.session.last_result is not None:
            self._rerun_preview()

    def _on_min_length_changed(self, value: int) -> None:
        if self._busy:
            return
        self.session.set_minimum_answer_length(value)
        if self.session.last_result is not None:
            self._rerun_preview()

    def _on_mark_style_changed(self, _index: int) -> None:
        if self._busy:
            return
        self.session.set_clue_mark_style(str(self.mark_style.currentData() or "highlight"))
        self._update_mark_color_enabled()
        self._refresh_clue_markup()

    def _on_mark_color_changed(self, _index: int) -> None:
        if self._busy:
            return
        self.session.set_clue_mark_color(str(self.mark_color.currentData() or "black"))
        self._refresh_clue_markup()

    def _on_mark_text_changed(self, _index: int) -> None:
        if self._busy:
            return
        self.session.set_clue_mark_text(str(self.mark_text.currentData() or "red"))
        self._refresh_clue_markup()

    def _update_mark_color_enabled(self) -> None:
        style = str(self.mark_style.currentData() or "highlight")
        self.mark_color.setEnabled(style in {"highlight", "highlight_bold"})

    def _refresh_clue_markup(self) -> None:
        if self.session.last_result is not None:
            self._fill_table(self.session.last_result)
        if self._puzzle_dialog is not None:
            try:
                self._puzzle_dialog.refresh_marks()
            except Exception:
                pass

    def _on_answer_changed(self, language: str) -> None:
        if self._busy:
            return
        combo = self.ja_answer if language == "japanese" else self.na_answer
        self.session.set_profile_answer_field(language, combo.currentText())
        if self._preview_language == language and self.session.last_result is not None:
            self._rerun_preview()

    def _on_clue_changed(self, language: str) -> None:
        if self._busy:
            return
        combo = self.ja_clue if language == "japanese" else self.na_clue
        template = self.ja_template if language == "japanese" else self.na_template
        self.session.set_profile_clue_field(language, combo.currentText())
        template.blockSignals(True)
        if language == "japanese":
            template.setText(self.session.settings.japanese_clue_template)
        else:
            template.setText(self.session.settings.native_clue_template)
        template.blockSignals(False)
        if self._preview_language == language and self.session.last_result is not None:
            self._rerun_preview()

    def _on_template_changed(self, language: str) -> None:
        if self._busy:
            return
        template = self.ja_template if language == "japanese" else self.na_template
        self.session.set_profile_clue_template(language, template.text())
        if self._preview_language == language and self.session.last_result is not None:
            self._rerun_preview()

    def _on_template_field_picked(self, language: str, index: int) -> None:
        picker = self.ja_field_picker if language == "japanese" else self.na_field_picker
        if index <= 0:
            return
        name = str(picker.itemData(index) or picker.itemText(index) or "").strip()
        picker.blockSignals(True)
        picker.setCurrentIndex(0)
        picker.blockSignals(False)
        if not name or self._busy:
            return
        self._insert_template_placeholder(language, name)

    def _insert_template_placeholder(self, language: str, field_name: str) -> None:
        edit = self.ja_template if language == "japanese" else self.na_template
        token = "{{" + field_name + "}}"
        text = edit.text()
        cursor = edit.cursorPosition()
        if not text.strip():
            inserted = token
            new_pos = len(token)
        elif cursor >= len(text):
            gap = "" if text.endswith((" ", "\t", "\n", "—")) else " — "
            inserted = text + gap + token
            new_pos = len(inserted)
        else:
            inserted = text[:cursor] + token + text[cursor:]
            new_pos = cursor + len(token)
        edit.setText(inserted)
        edit.setCursorPosition(new_pos)
        edit.setFocus()
        self._on_template_changed(language)

    def _fill_template_pickers(self, names: list[str]) -> None:
        for picker in (self.ja_field_picker, self.na_field_picker):
            picker.blockSignals(True)
            picker.clear()
            picker.addItem("Insert field…", "")
            for name in names:
                picker.addItem(name, name)
            picker.setCurrentIndex(0)
            picker.setEnabled(bool(names))
            picker.blockSignals(False)

    def _on_hide_toggled(self, language: str, checked: bool) -> None:
        if self._busy:
            return
        self.session.set_profile_hide_target(language, checked)
        if self._preview_language == language and self.session.last_result is not None:
            self._rerun_preview()

    def _on_native_max_words_changed(self, _index: int) -> None:
        if self._busy:
            return
        self.session.set_native_max_answer_words(_combo_int(self.na_max_words))
        if self._preview_language == "native" and self.session.last_result is not None:
            self._rerun_preview()

    def _on_show_skipped_toggled(self, checked: bool) -> None:
        self.session.settings.show_excluded_preview = bool(checked)
        self._apply_table_headers(show_skipped=bool(checked))
        if self.session.last_result is not None:
            self._fill_table(self.session.last_result)
            self.counts.setText(self._counts_text(self.session.last_result))

    def _rerun_preview(self) -> None:
        if self._busy:
            return
        language = self._preview_language
        if not language:
            return
        self._busy = True
        try:
            result = self.session.search(force_reload=True, language=language)
            self._apply_result(result)
        except SearchQueryError as exc:
            self._show_search_error(str(exc))
        finally:
            self._busy = False

    def _apply_result(self, result: Any) -> None:
        self._fill_table(result)
        self.counts.setText(self._counts_text(result))
        self._update_seed_label()
        enabled = self.session.can_generate()
        japanese = self._preview_language == "japanese"
        native = self._preview_language == "native"
        self.generate_japanese_btn.setEnabled(enabled and japanese)
        self.generate_native_btn.setEnabled(enabled and native)
        reason = self.session.generate_blocked_reason()
        ready_tip = "Build a crossword from the previewed vocabulary."
        if enabled and japanese:
            self.generate_japanese_btn.setToolTip(ready_tip)
            self.status.setText(
                f"{result.selected_count} Japanese words selected."
            )
        elif enabled and native:
            self.generate_native_btn.setToolTip(ready_tip)
            self.status.setText(f"{result.selected_count} Native words selected.")
        else:
            tip = reason or "Preview first."
            self.generate_japanese_btn.setToolTip(
                tip if japanese else "Preview Native → Japanese first."
            )
            self.generate_native_btn.setToolTip(
                tip if native else "Preview Japanese → Native first."
            )
            self.status.setText(reason or "Preview vocabulary first.")

    def _counts_text(self, result: Any) -> str:
        bits = [f"{result.selected_count:,} words"]
        query = getattr(result, "query", "") or ""
        if not self.show_skipped.isChecked():
            if query:
                return f"{bits[0]}\n{query}"
            return bits[0]

        bits = [
            f"{result.matching_notes:,} matching notes",
            f"{result.matching_cards:,} matching cards",
        ]
        scanned = getattr(result, "scanned_notes", 0)
        if scanned and (
            getattr(result, "truncated", False) or scanned != result.matching_notes
        ):
            bits.append(f"{scanned:,} looked at")
        bits.append(
            f"{result.selected_count:,} selected · {result.unique_valid:,} valid"
        )
        excluded = getattr(result, "excluded_count", 0)
        if excluded:
            bits.append(f"{excluded:,} excluded")
        if result.skipped_duplicate:
            bits.append(f"{result.skipped_duplicate} duplicates removed")
        if result.skipped_short:
            bits.append(f"{result.skipped_short} too short")
        if result.skipped_empty:
            bits.append(f"{result.skipped_empty} empty answers")
        if getattr(result, "skipped_empty_clue", 0):
            bits.append(f"{result.skipped_empty_clue} blank clues skipped")
        summary = " · ".join(bits)
        extras = list(getattr(result, "warnings", ()) or ())
        if query:
            extras.append(query)
        if extras:
            return summary + "\n" + "\n".join(extras)
        return summary

    def _fill_table(self, result: Any) -> None:
        show_skipped = self.show_skipped.isChecked()
        self._apply_table_headers(show_skipped=show_skipped)
        if show_skipped:
            rows = getattr(result, "preview", None) or (
                tuple(result.selected) + tuple(getattr(result, "excluded", ()) or ())
            )
        else:
            rows = result.selected
        self._preview_note_ids = [int(getattr(entry, "note_id", 0) or 0) for entry in rows]
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        for row, entry in enumerate(rows):
            answer = _answer_display(entry)
            language = language_label(getattr(entry, "answer_language", "japanese"))
            cells = str(getattr(entry, "cell_count", 0) or 0)
            clue = _clue_preview_label(
                entry.clue_raw,
                on_browse=lambda r=row: self._open_preview_note(r),
                dark=_widget_is_dark(self.table),
                mark_style=self.session.settings.clue_mark_style,
                mark_color=self.session.settings.clue_mark_color,
                mark_text=self.session.settings.clue_mark_text,
            )
            if show_skipped:
                included = "✓" if getattr(entry, "included", True) else "✗"
                status = QTableWidgetItem(getattr(entry, "status", "Valid"))
                items = (
                    QTableWidgetItem(included),
                    QTableWidgetItem(answer),
                    QTableWidgetItem(language),
                    QTableWidgetItem(cells),
                    status,
                )
                for item in items:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 0, items[0])
                self.table.setItem(row, 1, items[1])
                self.table.setItem(row, 2, items[2])
                self.table.setItem(row, 3, items[3])
                self.table.setCellWidget(row, 4, clue)
                self.table.setItem(row, 5, status)
                reason = getattr(entry, "status_reason", "") or ""
                if reason:
                    status.setToolTip(reason)
            else:
                items = (
                    QTableWidgetItem(answer),
                    QTableWidgetItem(language),
                    QTableWidgetItem(cells),
                )
                for item in items:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 0, items[0])
                self.table.setItem(row, 1, items[1])
                self.table.setItem(row, 2, items[2])
                self.table.setCellWidget(row, 3, clue)
        self.table.resizeRowsToContents()
        self._update_browse_button()

    def _on_preview_double_clicked(self, row: int, _column: int) -> None:
        self._open_preview_note(row)

    def _on_preview_menu(self, pos) -> None:
        row = self.table.indexAt(pos).row()
        if row < 0:
            return
        menu = QMenu(self)
        action = menu.addAction("Open in Browse")
        qconnect(action.triggered, lambda _checked=False, r=row: self._open_preview_note(r))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_browse_clicked(self) -> None:
        self._open_preview_note(self.table.currentRow())

    def _update_browse_button(self) -> None:
        row = self.table.currentRow()
        enabled = 0 <= row < len(self._preview_note_ids) and bool(
            self._preview_note_ids[row]
        )
        self.browse_btn.setEnabled(enabled)

    def _open_preview_note(self, row: int) -> None:
        if row < 0 or row >= len(self._preview_note_ids):
            return
        note_id = parse_note_id(self._preview_note_ids[row])
        if note_id is None:
            tooltip("This row has no note to open.")
            return
        if not browse_note(note_id):
            tooltip("Could not open that note in Browse.")

    def _apply_table_headers(self, *, show_skipped: bool) -> None:
        labels = SKIPPED_COLUMNS if show_skipped else VALID_COLUMNS
        self.table.setColumnCount(len(labels))
        self.table.setHorizontalHeaderLabels(list(labels))
        header = self.table.horizontalHeader()
        stretch = 4 if show_skipped else 3
        for index in range(len(labels)):
            mode = (
                QHeaderView.ResizeMode.Stretch
                if index == stretch
                else QHeaderView.ResizeMode.ResizeToContents
            )
            header.setSectionResizeMode(index, mode)

    def _replace_combo_items(self, combo: QComboBox, names: list[str], current: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        for name in names:
            combo.addItem(name)
        self._set_combo_text(combo, current)
        combo.blockSignals(False)

    def _set_combo_text(self, combo: QComboBox, text: str) -> None:
        if not text:
            if combo.count():
                combo.setCurrentIndex(0)
            return
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)
            return
        lowered = text.casefold()
        for i in range(combo.count()):
            if combo.itemText(i).casefold() == lowered:
                combo.setCurrentIndex(i)
                return
        combo.setEditText(text)

    def _set_checkbox(self, box: QCheckBox, checked: bool) -> None:
        box.blockSignals(True)
        box.setChecked(checked)
        box.blockSignals(False)

    def _set_preview_enabled(self, enabled: bool) -> None:
        self.preview_japanese_btn.setEnabled(enabled)
        self.preview_native_btn.setEnabled(enabled)

    def _update_seed_label(self) -> None:
        if self.session.settings.selection_mode != "random":
            self.seed_label.setText("—")
            return
        seed = self.session.settings.last_seed or self.session.settings.random_seed
        self.seed_label.setText(str(seed) if seed is not None else "(set after Preview)")

    def _show_search_error(self, message: str) -> None:
        self.generate_japanese_btn.setEnabled(False)
        self.generate_native_btn.setEnabled(False)
        self._preview_note_ids = []
        self.table.setRowCount(0)
        self._update_browse_button()
        self.counts.setText("Search failed.")
        self.status.setText(message)


def _combo_int(combo: QComboBox, default: int = 0) -> int:
    data = combo.itemData(combo.currentIndex())
    try:
        return int(data)
    except (TypeError, ValueError):
        return default


def _progress() -> Any | None:
    try:
        from aqt import mw

        return getattr(mw, "progress", None)
    except Exception:
        return None


def _form_layout(box: QGroupBox) -> QFormLayout:
    form = QFormLayout(box)
    form.setContentsMargins(12, 12, 12, 12)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(10)
    form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    return form


def _combo_with_tip(combo: QComboBox, tip: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(combo, 1)
    label = QLabel(tip)
    label.setWordWrap(False)
    label.setStyleSheet("color: palette(placeholder-text);")
    layout.addWidget(label, 0)
    return row


def _control_height(widget: QWidget) -> int:
    return max(28, widget.fontMetrics().height() + 12)


def _fit_combo(combo: QComboBox) -> None:
    height = _control_height(combo)
    combo.setMinimumHeight(height)
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(8)
    edit = combo.lineEdit()
    if edit is not None:
        edit.setMinimumHeight(max(22, height - 6))


def _fit_line(edit: QLineEdit) -> None:
    edit.setMinimumHeight(_control_height(edit))


def _fit_spin(spin: QSpinBox) -> None:
    spin.setMinimumHeight(_control_height(spin))


def _answer_display(entry: Any) -> str:
    normalized = getattr(entry, "normalized", None)
    text = ""
    if normalized is not None:
        text = str(getattr(normalized, "display_text", "") or "").strip()
    if not text:
        text = str(getattr(entry, "answer_text", "") or "").strip()
    return text or "—"


def _widget_is_dark(widget: QWidget) -> bool:
    return widget.palette().window().color().lightness() < 128


def _clue_preview_label(
    raw: str,
    on_browse=None,
    *,
    dark: bool = False,
    mark_style: str = "highlight",
    mark_color: str = "black",
    mark_text: str = "red",
) -> QLabel:
    label = _PreviewClueLabel(on_browse)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setWordWrap(True)
    label.setText(
        anki_html_for_preview(
            raw,
            dark=dark,
            mark_style=mark_style,
            mark_color=mark_color,
            mark_text=mark_text,
        )
    )
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setStyleSheet("QLabel { background: transparent; padding: 4px; }")
    return label


class _PreviewClueLabel(QLabel):
    """Clue cell widget that still opens Browse on double-click or right-click."""

    def __init__(self, on_browse) -> None:
        super().__init__()
        self._on_browse = on_browse
        if on_browse is not None:
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            qconnect(self.customContextMenuRequested, self._show_menu)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._on_browse is not None:
            self._on_browse()
        super().mouseDoubleClickEvent(event)

    def _show_menu(self, pos) -> None:
        menu = QMenu(self)
        action = menu.addAction("Open in Browse")
        qconnect(action.triggered, lambda _checked=False: self._on_browse())
        menu.exec(self.mapToGlobal(pos))
