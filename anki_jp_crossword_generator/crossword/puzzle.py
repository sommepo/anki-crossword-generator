# SPDX-License-Identifier: GPL-3.0-or-later
"""Generated crossword output. No Anki, Qt, or HTML."""

from __future__ import annotations

from dataclasses import dataclass

from .models import CrosswordEntry


@dataclass(frozen=True)
class PlacedEntry:
    """One word on the grid, after numbering."""

    id: str
    clue: str
    cells: tuple[str, ...]
    display_text: str
    direction: str
    row: int
    col: int
    number: int
    clue_html: str = ""

    @property
    def length(self) -> int:
        return len(self.cells)

    @property
    def length_label(self) -> str:
        """Newspaper-style letter count, e.g. ``(9)``."""
        return f"({self.length})"

    @property
    def printed_clue(self) -> str:
        """Plain clue line for the puzzle window and later print export."""
        text = (self.clue or self.display_text or "").strip()
        return f"{self.number}. {text} {self.length_label}"

    @property
    def answer_text(self) -> str:
        return "".join(self.cells)


@dataclass(frozen=True)
class Puzzle:
    """A cropped, numbered crossword ready for display or later export."""

    rows: int
    cols: int
    letters: tuple[tuple[str | None, ...], ...]
    entries: tuple[PlacedEntry, ...]
    unused: tuple[CrosswordEntry, ...]
    score: float
    seed: int
    language: str
    candidate_count: int
    elapsed_ms: int
    requested_count: int

    @property
    def placed_count(self) -> int:
        return len(self.entries)

    @property
    def unused_count(self) -> int:
        return len(self.unused)

    def letter_at(self, row: int, col: int) -> str | None:
        if row < 0 or col < 0 or row >= self.rows or col >= self.cols:
            return None
        return self.letters[row][col]

    def number_at(self, row: int, col: int) -> int | None:
        for entry in self.entries:
            if entry.row == row and entry.col == col:
                return entry.number
        return None

    def across(self) -> tuple[PlacedEntry, ...]:
        return tuple(e for e in self.entries if e.direction == "across")

    def down(self) -> tuple[PlacedEntry, ...]:
        return tuple(e for e in self.entries if e.direction == "down")

    def starts_at(self, row: int, col: int) -> tuple[PlacedEntry, ...]:
        return tuple(e for e in self.entries if e.row == row and e.col == col)
