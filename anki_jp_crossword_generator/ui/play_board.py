# SPDX-License-Identifier: GPL-3.0-or-later
"""Clickable crossword grid with IME-aware typing."""

from __future__ import annotations

from typing import Callable

from aqt.qt import (
    QColor,
    QFont,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPainter,
    QPalette,
    QPen,
    QSizePolicy,
    Qt,
    QWidget,
)

from ..crossword.solver import PlayState

_CELL = 42
_BLOCK = "#1a1a1a"
_INK = "#1a1a1a"
_LINE = "#1a1a1a"
_PAPER = "#ffffff"
_WORD = "#fff3c4"
_CURSOR = "#ffe082"


class PlayBoard(QWidget):
    """Renders ``PlayState`` and routes clicks and keystrokes into it."""

    def __init__(
        self,
        play: PlayState,
        on_change: Callable[[], None] | None = None,
        *,
        scale: int = 100,
    ) -> None:
        super().__init__()
        self.play = play
        self._on_change = on_change
        self._show_answers = False
        self._scale = max(50, min(125, int(scale)))
        self._cell = max(24, round(_CELL * self._scale / 100))
        self._squares: dict[tuple[int, int], _Square] = {}
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(0)
        self.setAutoFillBackground(True)
        _apply_fill(self, _BLOCK)
        self._editor = _CellEditor(self)
        self._build()
        self.refresh()

    def set_play(self, play: PlayState) -> None:
        self.play = play
        self._build()
        self.refresh()

    def set_show_answers(self, show: bool) -> None:
        self._show_answers = bool(show)
        self.refresh()

    def move_cursor(self, drow: int, dcol: int) -> None:
        self.play.move(drow, dcol)
        self._after_edit(changed=False)

    def toggle_direction(self) -> None:
        self.play.toggle_direction()
        self._after_edit(changed=False)

    def next_word(self, *, backward: bool = False) -> None:
        self.play.next_word(backward=backward)
        self._after_edit(changed=False)

    def type_text(self, text: str) -> None:
        if self._show_answers:
            return
        self.play.type_text(text)
        self._after_edit(changed=True)

    def backspace(self) -> None:
        if self._show_answers:
            return
        self.play.backspace()
        self._after_edit(changed=True)

    def refresh(self) -> None:
        play = self.play
        word = set(play.word_cells())
        cursor = play.cursor
        checked = play.check_result
        for (row, col), square in self._squares.items():
            if self._show_answers:
                letter = play.solution_at(row, col) or ""
                mark = ""
            else:
                letter = play.guess_at(row, col)
                mark = ""
                if checked is not None:
                    if (row, col) in checked.wrong:
                        mark = "wrong"
                    elif (row, col) in checked.correct:
                        mark = "correct"
            square.set_display(
                letter,
                selected=(row, col) == cursor,
                in_word=(row, col) in word,
                mark=mark,
                draw_north=not play.is_playable(row - 1, col),
                draw_west=not play.is_playable(row, col - 1),
            )
        self._place_editor()

    def _build(self) -> None:
        self._editor.setParent(self)
        self._editor.hide()
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self._editor:
                widget.setParent(None)
                widget.deleteLater()
        self._squares.clear()
        puzzle = self.play.puzzle
        for row in range(puzzle.rows):
            for col in range(puzzle.cols):
                playable = self.play.is_playable(row, col)
                number = puzzle.number_at(row, col) if playable else None
                square = _Square(
                    row,
                    col,
                    number,
                    playable,
                    on_click=self._on_square_clicked,
                    cell_size=self._cell,
                )
                self._grid.addWidget(square, row, col)
                if playable:
                    self._squares[(row, col)] = square
        self.setFixedSize(
            max(self._cell, puzzle.cols * self._cell),
            max(self._cell, puzzle.rows * self._cell),
        )
        self._editor.setParent(self)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(_BLOCK))

    def _on_square_clicked(self, row: int, col: int) -> None:
        self.play.select_cell(row, col)
        self._after_edit(changed=False)

    def _place_editor(self) -> None:
        square = self._squares.get(self.play.cursor)
        if square is None or self._show_answers:
            self._editor.hide()
            return
        self._editor.setParent(square)
        self._editor.setGeometry(0, 0, self._cell, self._cell)
        self._editor.clear()
        self._editor.show()
        self._editor.raise_()
        square.raise_number()
        self._editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _after_edit(self, *, changed: bool) -> None:  # noqa: ARG002 - kept for callers
        self.refresh()
        if self._on_change is not None:
            self._on_change()


class _Square(QWidget):
    def __init__(
        self,
        row: int,
        col: int,
        number: int | None,
        playable: bool,
        on_click,
        *,
        cell_size: int,
    ) -> None:
        super().__init__()
        self._row = row
        self._col = col
        self._playable = playable
        self._on_click = on_click
        self._cell = cell_size
        self._fill = QColor(_BLOCK if not playable else _PAPER)
        self._draw_north = True
        self._draw_west = True
        self.setFixedSize(self._cell, self._cell)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAutoFillBackground(False)
        self._letter = QLabel("", self)
        self._letter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._letter.setGeometry(0, 0, self._cell, self._cell)
        self._letter.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._letter.setAutoFillBackground(False)
        _ink_label(self._letter)
        font = QFont(self._letter.font())
        font.setPixelSize(max(15, round(20 * self._cell / _CELL)))
        font.setBold(True)
        self._letter.setFont(font)
        self._number: QLabel | None = None
        if not playable:
            self._letter.hide()
            return
        if number:
            num = QLabel(str(number), self)
            num.setGeometry(2, 0, round(self._cell * 0.52), round(self._cell * 0.34))
            num.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            num.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            num.setAutoFillBackground(False)
            nfont = QFont(num.font())
            nfont.setPixelSize(max(8, round(10 * self._cell / _CELL)))
            num.setFont(nfont)
            _ink_label(num, "#555555")
            self._number = num

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._playable and event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self._row, self._col)
        super().mousePressEvent(event)

    def raise_number(self) -> None:
        if self._number is not None:
            self._number.raise_()

    def set_display(
        self,
        letter: str,
        *,
        selected: bool,
        in_word: bool,
        mark: str,
        draw_north: bool = True,
        draw_west: bool = True,
    ) -> None:
        if not self._playable:
            return
        self._fill = QColor(_square_fill(selected, in_word, mark))
        self._draw_north = draw_north
        self._draw_west = draw_west
        self._letter.setText(letter)
        self._letter.setVisible(bool(letter))
        _ink_label(self._letter)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._fill)
        if not self._playable:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(QColor(_LINE), 1))
        rect = self.rect()
        painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if self._draw_west:
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
        if self._draw_north:
            painter.drawLine(rect.topLeft(), rect.topRight())


class _CellEditor(QLineEdit):
    """Focus sink so Japanese IME composition can commit into the play state."""

    def __init__(self, board: PlayBoard) -> None:
        super().__init__(board)
        self._board = board
        self._composing = False
        self.setFrame(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setAutoFillBackground(False)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0, 0))
        pal.setColor(QPalette.ColorRole.Text, QColor(_INK))
        self.setPalette(pal)
        font = QFont(self.font())
        font.setPixelSize(max(15, round(20 * board._cell / _CELL)))
        font.setBold(True)
        self.setFont(font)
        self.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color:"
            + _INK
            + "; }"
        )

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._composing:
            super().keyPressEvent(event)
            return
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Left:
            self._board.move_cursor(0, -1)
            event.accept()
            return
        if key == Qt.Key.Key_Right:
            self._board.move_cursor(0, 1)
            event.accept()
            return
        if key == Qt.Key.Key_Up:
            self._board.move_cursor(-1, 0)
            event.accept()
            return
        if key == Qt.Key.Key_Down:
            self._board.move_cursor(1, 0)
            event.accept()
            return
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._board.backspace()
            event.accept()
            return
        if key == Qt.Key.Key_Space:
            self._board.toggle_direction()
            event.accept()
            return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self._board.next_word(
                backward=key == Qt.Key.Key_Backtab
                or bool(mods & Qt.KeyboardModifier.ShiftModifier)
            )
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._board.next_word()
            event.accept()
            return
        text = event.text()
        ctrl = bool(
            mods
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )
        if text and not ctrl:
            if self._board.play.language == "japanese" and text.isascii():
                super().keyPressEvent(event)
                return
            self._board.type_text(text)
            event.accept()
            return
        super().keyPressEvent(event)

    def inputMethodEvent(self, event) -> None:  # noqa: N802 - Qt API
        commit = event.commitString()
        preedit = event.preeditString()
        if commit:
            self._composing = False
            self._board.type_text(commit)
            self.clear()
            event.accept()
            return
        self._composing = bool(preedit)
        super().inputMethodEvent(event)


def _apply_fill(widget: QWidget, fill: str) -> None:
    pal = widget.palette()
    colour = QColor(fill)
    pal.setColor(QPalette.ColorRole.Window, colour)
    pal.setColor(QPalette.ColorRole.Base, colour)
    widget.setPalette(pal)


def _ink_label(label: QWidget, colour: str = _INK) -> None:
    pal = label.palette()
    pal.setColor(QPalette.ColorRole.WindowText, QColor(colour))
    pal.setColor(QPalette.ColorRole.Text, QColor(colour))
    label.setPalette(pal)
    label.setStyleSheet(
        "QLabel { background: transparent; border: none; color: " + colour + "; }"
    )


def _square_fill(selected: bool, in_word: bool, mark: str) -> str:
    if mark == "wrong":
        return "#f8d0d0"
    if mark == "correct":
        return "#d5f0d8"
    if selected:
        return _CURSOR
    if in_word:
        return _WORD
    return _PAPER
