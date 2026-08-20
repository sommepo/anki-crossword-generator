# SPDX-License-Identifier: GPL-3.0-or-later
"""In-memory crossword play state. No Anki, Qt, or HTML."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from .puzzle import PlacedEntry, Puzzle

Coord = tuple[int, int]


@dataclass(frozen=True)
class CheckResult:
    """Per-cell comparison of guesses against the solution."""

    correct: frozenset[Coord]
    wrong: frozenset[Coord]
    empty: frozenset[Coord]

    @property
    def solved(self) -> bool:
        return not self.wrong and not self.empty


def _delta(direction: str) -> Coord:
    return (0, 1) if direction == "across" else (1, 0)


def normalize_guess(char: str, language: str) -> str | None:
    """Return the cell token for one typed character, or None to ignore it."""
    if not char or char.isspace():
        return None
    letter = unicodedata.normalize("NFC", char)
    if len(letter) != 1:
        letter = letter[-1]
    lang = (language or "").strip().lower()
    if lang == "japanese":
        return letter
    category = unicodedata.category(letter)
    if category.startswith("L") or category.startswith("N"):
        upper = letter.upper()
        return upper if len(upper) == 1 else letter
    return None


class PlayState:
    """Cursor, guesses, and checking for one generated puzzle."""

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.guesses: dict[Coord, str] = {}
        self.direction = "across"
        self.check_result: CheckResult | None = None
        coords = tuple(
            (row, col)
            for row in range(puzzle.rows)
            for col in range(puzzle.cols)
            if puzzle.letter_at(row, col) is not None
        )
        self._coords = coords
        self.row, self.col = coords[0] if coords else (0, 0)
        if coords and not self.active_entry():
            self.direction = "down" if self.direction == "across" else "across"

    @property
    def cursor(self) -> Coord:
        return (self.row, self.col)

    @property
    def language(self) -> str:
        return self.puzzle.language

    @property
    def total_cells(self) -> int:
        return len(self._coords)

    @property
    def filled_cells(self) -> int:
        return sum(1 for coord in self._coords if self.guesses.get(coord))

    @property
    def total_clues(self) -> int:
        return len(self.puzzle.entries)

    @property
    def completed_clues(self) -> int:
        completed = 0
        for entry in self.puzzle.entries:
            cells = self.cells_of(entry)
            if cells and all(
                self.guesses.get(coord) == (self.puzzle.letter_at(*coord) or "")
                for coord in cells
            ):
                completed += 1
        return completed

    def is_playable(self, row: int, col: int) -> bool:
        return self.puzzle.letter_at(row, col) is not None

    def solution_at(self, row: int, col: int) -> str | None:
        return self.puzzle.letter_at(row, col)

    def guess_at(self, row: int, col: int) -> str:
        return self.guesses.get((row, col), "")

    def cells_of(self, entry: PlacedEntry) -> tuple[Coord, ...]:
        dr, dc = _delta(entry.direction)
        return tuple(
            (entry.row + dr * index, entry.col + dc * index)
            for index in range(entry.length)
        )

    def entries_at(self, row: int, col: int) -> tuple[PlacedEntry, ...]:
        return tuple(
            entry
            for entry in self.puzzle.entries
            if (row, col) in self.cells_of(entry)
        )

    def active_entry(self) -> PlacedEntry | None:
        at_cursor = self.entries_at(self.row, self.col)
        for entry in at_cursor:
            if entry.direction == self.direction:
                return entry
        return at_cursor[0] if at_cursor else None

    def word_cells(self) -> tuple[Coord, ...]:
        entry = self.active_entry()
        if entry is None:
            return ()
        return self.cells_of(entry)

    def select_cell(self, row: int, col: int) -> None:
        if not self.is_playable(row, col):
            return
        if (row, col) == self.cursor:
            self.toggle_direction()
            return
        self.row, self.col = row, col
        if not any(e.direction == self.direction for e in self.entries_at(row, col)):
            other = "down" if self.direction == "across" else "across"
            if any(e.direction == other for e in self.entries_at(row, col)):
                self.direction = other

    def select_entry(self, entry: PlacedEntry) -> None:
        self.direction = entry.direction
        cells = self.cells_of(entry)
        if not cells:
            return
        empty = next((coord for coord in cells if not self.guesses.get(coord)), cells[0])
        self.row, self.col = empty

    def toggle_direction(self) -> None:
        other = "down" if self.direction == "across" else "across"
        if any(e.direction == other for e in self.entries_at(self.row, self.col)):
            self.direction = other

    def type_text(self, text: str) -> None:
        for char in unicodedata.normalize("NFC", text or ""):
            token = normalize_guess(char, self.language)
            if token is None:
                continue
            self._place(token)
            self._advance()

    def backspace(self) -> None:
        coord = self.cursor
        if self.guesses.get(coord):
            self.guesses.pop(coord, None)
            self.check_result = None
            return
        self._retreat()
        self.guesses.pop(self.cursor, None)
        self.check_result = None

    def move(self, drow: int, dcol: int) -> None:
        row, col = self.row + drow, self.col + dcol
        while 0 <= row < self.puzzle.rows and 0 <= col < self.puzzle.cols:
            if self.is_playable(row, col):
                self.row, self.col = row, col
                return
            row += drow
            col += dcol

    def next_word(self, *, backward: bool = False) -> None:
        entries = self.puzzle.across() + self.puzzle.down()
        if not entries:
            return
        current = self.active_entry()
        if current is None:
            self.select_entry(entries[-1] if backward else entries[0])
            return
        try:
            index = entries.index(current)
        except ValueError:
            self.select_entry(entries[0])
            return
        step = -1 if backward else 1
        self.select_entry(entries[(index + step) % len(entries)])

    def check(self) -> CheckResult:
        return self._check_coords(self._coords)

    def check_word(self) -> CheckResult:
        cells = self.word_cells()
        if not cells and self.is_playable(self.row, self.col):
            cells = (self.cursor,)
        return self._check_coords(cells)

    def reveal_all(self) -> None:
        self.guesses = {
            coord: self.puzzle.letter_at(*coord) or ""
            for coord in self._coords
        }
        self.check_result = None

    def reveal_word(self) -> None:
        for coord in self.word_cells():
            self.guesses[coord] = self.puzzle.letter_at(*coord) or ""
        self.check_result = None

    def clear_guesses(self) -> None:
        self.guesses.clear()
        self.check_result = None

    def clear_word(self) -> None:
        for coord in self.word_cells():
            self.guesses.pop(coord, None)
        self.check_result = None

    def _check_coords(self, coords: tuple[Coord, ...]) -> CheckResult:
        correct: set[Coord] = set()
        wrong: set[Coord] = set()
        empty: set[Coord] = set()
        for coord in coords:
            solution = self.puzzle.letter_at(*coord) or ""
            guess = self.guesses.get(coord, "")
            if not guess:
                empty.add(coord)
            elif guess == solution:
                correct.add(coord)
            else:
                wrong.add(coord)
        result = CheckResult(
            correct=frozenset(correct),
            wrong=frozenset(wrong),
            empty=frozenset(empty),
        )
        self.check_result = result
        return result

    def _place(self, token: str) -> None:
        if not self.is_playable(self.row, self.col):
            return
        self.guesses[(self.row, self.col)] = token
        self.check_result = None

    def _advance(self) -> None:
        dr, dc = _delta(self.direction)
        row, col = self.row + dr, self.col + dc
        if self.is_playable(row, col):
            self.row, self.col = row, col

    def _retreat(self) -> None:
        dr, dc = _delta(self.direction)
        row, col = self.row - dr, self.col - dc
        if self.is_playable(row, col):
            self.row, self.col = row, col
