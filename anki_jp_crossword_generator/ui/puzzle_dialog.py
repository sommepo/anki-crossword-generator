# SPDX-License-Identifier: GPL-3.0-or-later
"""Phase 4 puzzle window: interactive solver, clues, regenerate."""

from __future__ import annotations

from typing import Any

from aqt.qt import (
    QColor,
    QFont,
    QFrame,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QMenu,
    QPainter,
    QPalette,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    Qt,
    QVBoxLayout,
    QWidget,
    QPushButton,
    qconnect,
)
from aqt.utils import showInfo, tooltip

from ..anki.browser import browse_note, parse_note_id
from ..crossword.errors import GenerationError
from ..crossword.puzzle import Puzzle
from ..crossword.solver import PlayState
from ..session import CrosswordSession
from ..version import ADDON_NAME
from ..vocabulary.text import anki_html_for_preview
from .play_board import PlayBoard
from .windowing import (
    anki_window_parent,
    crossword_window_flags,
    prepare_crossword_window,
    restore_anki,
)


class PuzzleDialog(QWidget):
    """Interactive crossword: type into cells, check, reveal, regenerate."""

    def __init__(
        self,
        session: CrosswordSession,
        language: str,
        puzzle: Puzzle,
        parent: QWidget | None = None,
        on_settings_changed=None,
    ) -> None:
        super().__init__(anki_window_parent(parent), crossword_window_flags())
        self.session = session
        self.language = language
        self.puzzle = puzzle
        self.play = PlayState(puzzle)
        self._busy = False
        self._on_settings_changed = on_settings_changed
        self._scale = _normalise_scale(getattr(session.settings, "puzzle_scale", 80))
        title = "Native → Japanese" if language == "japanese" else "Japanese → Native"
        self.setWindowTitle(f"{ADDON_NAME} — {title}")
        prepare_crossword_window(self)
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Crossword scale"))
        self.scale_combo = QComboBox()
        for value in _SCALE_OPTIONS:
            self.scale_combo.addItem(f"{value}%", value)
        self.scale_combo.setCurrentIndex(_SCALE_OPTIONS.index(self._scale))
        self.scale_combo.setToolTip(
            "Resize the grid, clues, and controls. Your choice is saved for future puzzles."
        )
        qconnect(self.scale_combo.currentIndexChanged, self._on_scale_changed)
        scale_row.addWidget(self.scale_combo)
        scale_row.addStretch(1)
        root.addLayout(scale_row)

        self.hint = QLabel(
            "Click a cell or clue · Type to fill · Space to switch across/down · "
            "Tab to move to next clue · Backspace to delete"
        )
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        body = QHBoxLayout()
        body.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(10)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.board = PlayBoard(
            self.play, on_change=self._on_play_changed, scale=self._scale
        )
        self.scroll.setWidget(self.board)
        left.addWidget(self.scroll, 1)

        word_row = QHBoxLayout()
        word_row.setSpacing(8)
        self.check_word_btn = _pill("Check word", accent=True, scale=self._scale)
        self.check_word_btn.setToolTip("Check the currently selected clue.")
        qconnect(self.check_word_btn.clicked, self._on_check_word)
        word_row.addWidget(self.check_word_btn)
        self.reveal_word_btn = _pill("Reveal word", accent=True, scale=self._scale)
        self.reveal_word_btn.setToolTip("Fill the currently selected clue.")
        qconnect(self.reveal_word_btn.clicked, self._on_reveal_word)
        word_row.addWidget(self.reveal_word_btn)
        self.clear_word_btn = _pill("Clear word", accent=True, scale=self._scale)
        self.clear_word_btn.setToolTip("Erase guesses for the currently selected clue.")
        qconnect(self.clear_word_btn.clicked, self._on_clear_word)
        word_row.addWidget(self.clear_word_btn)
        word_row.addStretch(1)
        left.addLayout(word_row)

        all_row = QHBoxLayout()
        all_row.setSpacing(8)
        self.check_btn = _pill("Check all", scale=self._scale)
        self.check_btn.setToolTip("Mark correct and incorrect cells.")
        qconnect(self.check_btn.clicked, self._on_check)
        all_row.addWidget(self.check_btn)
        self.show_answers = _pill("Show answers", checkable=True, scale=self._scale)
        self.show_answers.setToolTip("Reveal the solution without wiping your guesses.")
        qconnect(self.show_answers.toggled, self._on_show_answers)
        all_row.addWidget(self.show_answers)
        self.clear_btn = _pill("Clear all", scale=self._scale)
        self.clear_btn.setToolTip("Erase your guesses. The layout stays.")
        qconnect(self.clear_btn.clicked, self._on_clear)
        all_row.addWidget(self.clear_btn)
        all_row.addStretch(1)
        self.play_status = QLabel("")
        all_row.addWidget(self.play_status)
        left.addLayout(all_row)
        body.addLayout(left, 3)

        clues = QHBoxLayout()
        clues.setSpacing(16)
        across_col = QVBoxLayout()
        across_col.setSpacing(6)
        self.across_heading = _clue_heading("Across", self._scale)
        across_col.addWidget(self.across_heading)
        self.across_list = _CluePane(
            self._browse_placed, self.session, on_select=self._select_entry, scale=self._scale
        )
        across_col.addWidget(self.across_list, 1)
        clues.addLayout(across_col, 1)
        down_col = QVBoxLayout()
        down_col.setSpacing(6)
        self.down_heading = _clue_heading("Down", self._scale)
        down_col.addWidget(self.down_heading)
        self.down_list = _CluePane(
            self._browse_placed, self.session, on_select=self._select_entry, scale=self._scale
        )
        down_col.addWidget(self.down_list, 1)
        clues.addLayout(down_col, 1)
        body.addLayout(clues, 3)
        root.addLayout(body, 1)

        buttons = QHBoxLayout()
        self.mark_solved_btn = _pill("Mark puzzle solved", scale=self._scale)
        self.mark_solved_btn.setToolTip(
            "Tag all notes used in this puzzle as solved so they are skipped next time."
        )
        qconnect(self.mark_solved_btn.clicked, self._on_mark_solved)
        buttons.addWidget(self.mark_solved_btn)
        self.again_btn = _pill("Try another", accent=True, scale=self._scale)
        qconnect(self.again_btn.clicked, self._on_try_another)
        buttons.addWidget(self.again_btn)
        buttons.addStretch(1)
        self.close_btn = _pill("Close", scale=self._scale)
        qconnect(self.close_btn.clicked, self.close)
        buttons.addWidget(self.close_btn)
        root.addLayout(buttons)

        self._render()
        self._style_text_labels()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        restore_anki()
        super().closeEvent(event)

    def _render(self) -> None:
        puzzle = self.puzzle
        self.summary.setText(
            f"{puzzle.rows}×{puzzle.cols} · {puzzle.placed_count} words · "
            f"{len(puzzle.across())} across · {len(puzzle.down())} down · "
            f"score {puzzle.score:.0f} · {puzzle.elapsed_ms} ms · seed {puzzle.seed}."
        )
        self.play = PlayState(puzzle)
        self.board.set_play(self.play)
        self.board.set_show_answers(self.show_answers.isChecked())
        self._refresh_clues()
        self._update_play_status()

    def refresh_marks(self) -> None:
        self._refresh_clues()

    def _on_scale_changed(self, _index: int) -> None:
        value = self.scale_combo.currentData()
        self._scale = _normalise_scale(value)
        self.session.settings.puzzle_scale = self._scale
        if self._on_settings_changed is not None:
            self._on_settings_changed()
        self._rebuild_scaled_widgets()

    def _rebuild_scaled_widgets(self) -> None:
        """Apply the selected presentation scale without changing the puzzle."""
        self.board = PlayBoard(
            self.play, on_change=self._on_play_changed, scale=self._scale
        )
        self.board.set_show_answers(self.show_answers.isChecked())
        self.scroll.setWidget(self.board)
        for button, accent in (
            (self.check_word_btn, True),
            (self.reveal_word_btn, True),
            (self.clear_word_btn, True),
            (self.check_btn, False),
            (self.show_answers, False),
            (self.clear_btn, False),
            (self.mark_solved_btn, False),
            (self.again_btn, True),
            (self.close_btn, False),
        ):
            _style_pill(button, accent=accent, scale=self._scale)
        _style_heading(self.across_heading, self._scale)
        _style_heading(self.down_heading, self._scale)
        self.across_list.set_scale(self._scale)
        self.down_list.set_scale(self._scale)
        self._style_text_labels()
        self._refresh_clues()

    def _style_text_labels(self) -> None:
        for label in (self.summary, self.hint, self.play_status):
            font = QFont(label.font())
            font.setPointSize(max(9, round(11 * self._scale / 100)))
            label.setFont(font)

    def _refresh_clues(self) -> None:
        selected = self._selected_clue_key()
        self.across_list.set_entries(self.puzzle.across(), selected_key=selected)
        self.down_list.set_entries(self.puzzle.down(), selected_key=selected)

    def _selected_clue_key(self) -> str:
        entry = self.play.active_entry()
        if entry is None:
            return ""
        return f"{entry.direction}:{entry.id}"

    def _on_play_changed(self) -> None:
        key = self._selected_clue_key()
        self.across_list.set_selected_key(key)
        self.down_list.set_selected_key(key)
        self._update_play_status()

    def _update_play_status(self) -> None:
        play = self.play
        text = f"Clues completed {play.completed_clues} / {play.total_clues}"
        result = play.check_result
        if result is not None and result.wrong:
            text = f"{text} · {len(result.wrong)} incorrect"
        self.play_status.setText(text)

    def _select_entry(self, entry: Any) -> None:
        self.play.select_entry(entry)
        self.board.refresh()
        self._on_play_changed()

    def _on_show_answers(self, _checked: bool) -> None:
        showing = self.show_answers.isChecked()
        self.board.set_show_answers(showing)
        for button in (
            self.check_word_btn,
            self.reveal_word_btn,
            self.clear_word_btn,
            self.check_btn,
            self.clear_btn,
        ):
            button.setEnabled(not showing)

    def _on_check_word(self) -> None:
        result = self.play.check_word()
        self.board.refresh()
        self._update_play_status()
        if result.wrong:
            tooltip(f"{len(result.wrong)} incorrect in this clue.")
        elif result.correct and not result.empty:
            tooltip("This clue is correct.")
        else:
            tooltip("No incorrect cells in this clue yet.")

    def _on_reveal_word(self) -> None:
        self.play.reveal_word()
        self.board.refresh()
        self._update_play_status()

    def _on_clear_word(self) -> None:
        self.play.clear_word()
        self.board.refresh()
        self._update_play_status()

    def _on_check(self) -> None:
        result = self.play.check()
        self.board.refresh()
        self._update_play_status()
        if result.solved:
            tooltip("All cells are correct.")
        elif result.wrong:
            tooltip(f"{len(result.wrong)} incorrect.")
        else:
            tooltip("No incorrect cells yet.")

    def _on_clear(self) -> None:
        self.play.clear_guesses()
        self.board.refresh()
        self._update_play_status()

    def _on_mark_solved(self) -> None:
        updated, _tag = self.session.mark_puzzle_solved(self.puzzle)
        self.mark_solved_btn.setEnabled(False)
        if updated:
            tooltip(f"Marked {updated} notes as solved.")
        else:
            tooltip("These notes are already marked solved.")

    def _browse_placed(self, entry_id: str) -> None:
        note_id = parse_note_id(entry_id)
        if note_id is None or not browse_note(note_id):
            tooltip("Could not open that note in Browse.")

    def _on_try_another(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.again_btn.setEnabled(False)
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

            self.puzzle = self.session.generate(
                self.language, progress=cb, new_seed=True
            )
            self._render()
            tooltip("Generated another layout.")
        except GenerationError as exc:
            showInfo(str(exc))
        finally:
            if progress is not None:
                try:
                    progress.finish()
                except Exception:
                    pass
            self._busy = False
            self.again_btn.setEnabled(True)


def _clue_heading(text: str, scale: int) -> QLabel:
    label = QLabel(text)
    _style_heading(label, scale)
    return label


def _style_heading(label: QLabel, scale: int) -> None:
    font = QFont(label.font())
    font.setFamily("Georgia")
    font.setPointSize(max(14, round(18 * scale / 100)))
    font.setBold(True)
    label.setFont(font)


def _pill(
    text: str,
    *,
    accent: bool = False,
    checkable: bool = False,
    scale: int = 100,
) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setCheckable(checkable)
    _style_pill(button, accent=accent, scale=scale)
    return button


def _style_pill(button: QPushButton, *, accent: bool, scale: int) -> None:
    font = QFont(button.font())
    font.setPointSize(max(11, round(_CLUE_PT * scale / 100)))
    font.setBold(True)
    button.setFont(font)
    padding_v = max(5, round(8 * scale / 100))
    padding_h = max(10, round(16 * scale / 100))
    radius = max(10, round(16 * scale / 100))
    min_height = max(28, round(32 * scale / 100))
    base = "#2c3e70" if accent else "#ffffff"
    color = "#ffffff" if accent else _BLUE
    border = "none" if accent else f"2px solid {_BLUE}"
    hover = "#3d5291" if accent else "#e8eefc"
    pressed = "#24335c" if accent else "#d5def5"
    checked = "QPushButton:checked { background: #2c3e70; color: #ffffff; }" if not accent else ""
    button.setStyleSheet(
        f"QPushButton {{ border: {border}; border-radius: {radius}px; "
        f"padding: {padding_v}px {padding_h}px; min-height: {min_height}px; "
        f"background: {base}; color: {color}; font-weight: 700; }}"
        f"QPushButton:hover {{ background: {hover}; }}"
        f"QPushButton:pressed {{ background: {pressed}; }}"
        f"{checked}"
        "QPushButton:disabled { background: #dddddd; color: #888888; border-color: #888888; }"
    )


def _browse_button(scale: int = 100) -> QPushButton:
    button = QPushButton("Browse")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip("Open this note in Browse")
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    font = QFont(button.font())
    font.setPointSize(max(8, round(9 * scale / 100)))
    font.setBold(True)
    button.setFont(font)
    padding = max(1, round(7 * scale / 100))
    height = max(18, round(24 * scale / 100))
    button.setStyleSheet(
        _BROWSE_PILL.replace("7px", f"{padding}px").replace("24px", f"{height}px")
    )
    return button


_CLUE_PT = 16
_BLUE = "#2c3e70"
_SCALE_OPTIONS = (50, 60, 70, 80, 90, 100, 110, 125)


def _normalise_scale(value: Any) -> int:
    """Return a supported UI scale percentage."""
    try:
        requested = int(value)
    except (TypeError, ValueError):
        return 80
    return min(_SCALE_OPTIONS, key=lambda option: abs(option - requested))

_BROWSE_PILL = """
QPushButton {
    border: 1px solid #2c3e70;
    border-radius: 8px;
    padding: 1px 7px;
    min-height: 20px;
    max-height: 24px;
    background: #ffffff;
    color: #2c3e70;
    font-size: 9pt;
    font-weight: 700;
}
QPushButton:hover { background: #e8eefc; }
"""


class _CluePane(QScrollArea):
    """Scrollable rich-text clues so Anki bold/highlight markup is visible."""

    def __init__(self, on_browse, session, on_select=None, *, scale: int = 100) -> None:
        super().__init__()
        self._on_browse = on_browse
        self._on_select = on_select
        self._session = session
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self._layout = QVBoxLayout(inner)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self._layout.addStretch(1)
        self.setWidget(inner)
        self._scale = scale
        self._font = self._scaled_font()
        self._rows: list[_ClueRow] = []

    def _scaled_font(self) -> QFont:
        font = self.font()
        font.setPointSize(max(11, round(_CLUE_PT * self._scale / 100)))
        return font

    def set_scale(self, scale: int) -> None:
        self._scale = scale
        self._font = self._scaled_font()

    def set_entries(self, entries: tuple[Any, ...], selected_key: str = "") -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []
        for entry in entries:
            row = _ClueRow(
                self._font,
                entry,
                self._on_browse,
                self._session.settings,
                on_select=self._on_select,
                scale=self._scale,
            )
            self._layout.insertWidget(self._layout.count() - 1, row)
            self._rows.append(row)
        self.set_selected_key(selected_key)

    def set_selected_key(self, selected_key: str) -> None:
        for row in self._rows:
            row.set_selected(row.key == selected_key)


class _ClueRow(QWidget):
    """One numbered clue plus a Browse button for its Anki note."""

    def __init__(
        self, font, entry: Any, on_browse, settings, on_select=None, *, scale: int = 100
    ) -> None:
        super().__init__()
        self._entry = entry
        self.key = f"{entry.direction}:{entry.id}"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(6)
        view = _ClueView(
            font,
            on_activate=lambda: on_browse(entry.id),
            on_select=(lambda: on_select(entry)) if on_select else None,
        )
        self._view = view
        raw = getattr(entry, "clue_html", "") or entry.clue or entry.display_text
        view.set_clue(entry.number, raw, settings, length=entry.length)
        layout.addWidget(view, 1)
        button = _browse_button(scale)
        qconnect(button.clicked, lambda _checked=False: on_browse(entry.id))
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
        self._selected = False

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._view.set_selected(self._selected)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not self._selected:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(255, 224, 130, 70))
        painter.fillRect(0, 6, 3, max(8, self.height() - 12), QColor("#c9a227"))


class _ClueView(QTextBrowser):
    """QLabel often drops span backgrounds; QTextDocument paints them."""

    def __init__(self, font, on_activate=None, on_select=None) -> None:
        super().__init__()
        self._on_activate = on_activate
        self._on_select = on_select
        self._selected = False
        self._number = 0
        self._body = ""
        self._count = ""
        self._muted = "#9aa0a6"
        self.setReadOnly(True)
        self.setOpenExternalLinks(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.document().setDefaultFont(font)
        self.document().setDefaultStyleSheet(
            "b, strong { font-weight: bold; } "
            "i, em { font-style: italic; } "
            "u { text-decoration: underline; }"
        )
        self.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        self.document().contentsChanged.connect(self._fit_height)
        if on_activate is not None:
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            qconnect(self.customContextMenuRequested, self._show_menu)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._on_select is not None
        ):
            self._on_select()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._on_activate is not None:
            self._on_activate()
        super().mouseDoubleClickEvent(event)

    def _show_menu(self, pos) -> None:
        menu = QMenu(self)
        action = menu.addAction("Open in Browse")
        qconnect(action.triggered, lambda _checked=False: self._on_activate())
        menu.exec(self.mapToGlobal(pos))

    def set_clue(
        self, number: int, raw: str, settings: Any = None, *, length: int = 0
    ) -> None:
        color = self.palette().color(QPalette.ColorRole.WindowText).name()
        muted = "#666666" if self.palette().window().color().lightness() >= 128 else "#9aa0a6"
        mark_style = getattr(settings, "clue_mark_style", "highlight")
        mark_color = getattr(settings, "clue_mark_color", "black")
        mark_text = getattr(settings, "clue_mark_text", "red")
        body = anki_html_for_preview(
            raw,
            dark=self.palette().window().color().lightness() < 128,
            mark_style=mark_style,
            mark_color=mark_color,
            mark_text=mark_text,
        )
        count = f" ({int(length)})" if length else ""
        self._number = number
        self._body = body
        self._count = count
        self._muted = muted
        self._paint_html()
        self._fit_height()

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._paint_html()

    def _paint_html(self) -> None:
        color = self.palette().color(QPalette.ColorRole.WindowText).name()
        muted = self._muted
        if self._selected:
            self.setStyleSheet(
                "QTextBrowser { background: rgba(255, 224, 130, 110); "
                "border: none; border-left: 3px solid #c9a227; border-radius: 3px; }"
            )
        else:
            self.setStyleSheet(
                "QTextBrowser { background: transparent; border: none; }"
            )
        self.setHtml(
            f'<html><body style="background: transparent; color:{color}; font-size:{self.document().defaultFont().pointSize()}pt;">'
            f"<b>{self._number}</b> {self._body}"
            f'<span style="color:{muted};">{self._count}</span></body></html>'
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._fit_height()

    def _fit_height(self) -> None:
        width = max(80, self.viewport().width())
        self.document().setTextWidth(width)
        height = int(self.document().size().height()) + 8
        self.setFixedHeight(max(40, height))


def _progress() -> Any | None:
    try:
        from aqt import mw

        return getattr(mw, "progress", None)
    except Exception:
        return None
