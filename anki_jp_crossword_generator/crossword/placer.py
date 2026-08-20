# SPDX-License-Identifier: GPL-3.0-or-later
"""Language-agnostic freeform placement on opaque cell tokens.

The kernel never branches on Japanese vs Native. Each engine passes a list of
cell sequences (already normalised) and receives a cropped, numbered puzzle.
"""

from __future__ import annotations

import random
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from .models import CrosswordEntry
from .options import GenerateOptions
from .puzzle import PlacedEntry, Puzzle
from .scorer import ScoreWeights, excellent_threshold, score_puzzle

ProgressFn = Callable[[int, int], None]

_DIRS = {
    "across": (0, 1),
    "down": (1, 0),
}


@dataclass(frozen=True)
class WordToPlace:
    """One vocabulary item as the placer sees it."""

    id: str
    cells: tuple[str, ...]
    clue: str
    display_text: str
    source: CrosswordEntry | None = None
    clue_html: str = ""

    @property
    def length(self) -> int:
        return len(self.cells)


@dataclass
class _Slot:
    row: int
    col: int
    direction: str
    crossings: int


@dataclass
class _Placed:
    word: WordToPlace
    row: int
    col: int
    direction: str


@dataclass
class _Grid:
    max_size: int | None
    cells: dict[tuple[int, int], str] = field(default_factory=dict)
    by_letter: dict[str, list[tuple[int, int]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    placed: list[_Placed] = field(default_factory=list)

    def copy(self) -> _Grid:
        clone = _Grid(self.max_size)
        clone.cells = dict(self.cells)
        clone.by_letter = defaultdict(list, {k: list(v) for k, v in self.by_letter.items()})
        clone.placed = list(self.placed)
        return clone

    def place(self, word: WordToPlace, row: int, col: int, direction: str) -> None:
        dr, dc = _DIRS[direction]
        for index, letter in enumerate(word.cells):
            pos = (row + dr * index, col + dc * index)
            if pos not in self.cells:
                self.cells[pos] = letter
                self.by_letter[letter].append(pos)
        self.placed.append(_Placed(word, row, col, direction))

    def find_slots(self, word: WordToPlace) -> list[_Slot]:
        if not self.cells:
            return [_Slot(0, 0, "across", 0), _Slot(0, 0, "down", 0)]
        letters = word.cells
        seen: set[tuple[int, int, str]] = set()
        slots: list[_Slot] = []
        for index, letter in enumerate(letters):
            for row, col in self.by_letter.get(letter, ()):
                for direction, (dr, dc) in _DIRS.items():
                    start_r = row - dr * index
                    start_c = col - dc * index
                    key = (start_r, start_c, direction)
                    if key in seen:
                        continue
                    seen.add(key)
                    crossings = self._validate(word, start_r, start_c, direction)
                    if crossings is None or crossings < 1:
                        continue
                    if self._span_taken(start_r, start_c, direction, word.length):
                        continue
                    if not self._fits(word, start_r, start_c, direction):
                        continue
                    slots.append(_Slot(start_r, start_c, direction, crossings))
        return slots

    def _span_taken(self, row: int, col: int, direction: str, length: int) -> bool:
        for item in self.placed:
            if (
                item.row == row
                and item.col == col
                and item.direction == direction
                and item.word.length == length
            ):
                return True
        return False

    def _validate(
        self, word: WordToPlace, row: int, col: int, direction: str
    ) -> int | None:
        dr, dc = _DIRS[direction]
        pr, pc = dc, dr
        before = (row - dr, col - dc)
        after = (row + dr * word.length, col + dc * word.length)
        if before in self.cells or after in self.cells:
            return None
        crossings = 0
        for index, letter in enumerate(word.cells):
            pos = (row + dr * index, col + dc * index)
            existing = self.cells.get(pos)
            if existing is not None:
                if existing != letter:
                    return None
                crossings += 1
                continue
            if (pos[0] + pr, pos[1] + pc) in self.cells:
                return None
            if (pos[0] - pr, pos[1] - pc) in self.cells:
                return None
        return crossings

    def _fits(self, word: WordToPlace, row: int, col: int, direction: str) -> bool:
        if self.max_size is None:
            return True
        dr, dc = _DIRS[direction]
        rows = [r for r, _c in self.cells]
        cols = [c for _r, c in self.cells]
        min_r = min(rows + [row, row + dr * (word.length - 1)])
        max_r = max(rows + [row, row + dr * (word.length - 1)])
        min_c = min(cols + [col, col + dc * (word.length - 1)])
        max_c = max(cols + [col, col + dc * (word.length - 1)])
        return (max_r - min_r + 1) <= self.max_size and (max_c - min_c + 1) <= self.max_size


def place_words(
    words: Sequence[WordToPlace],
    options: GenerateOptions,
    *,
    language: str,
    weights: ScoreWeights,
    original_entries: Sequence[CrosswordEntry] = (),
    progress: ProgressFn | None = None,
) -> Puzzle:
    """Run many seeded attempts and keep the highest-scoring grid."""
    usable = [word for word in words if word.length >= 2]
    if not usable:
        return _empty_puzzle(options, language, tuple(original_entries))

    started = time.perf_counter()
    rng = random.Random(options.seed)
    best: Puzzle | None = None
    target = excellent_threshold(len(usable), weights)
    attempts = max(1, options.candidate_count)
    for index in range(attempts):
        attempt_rng = random.Random(rng.randrange(1, 1_000_000_000))
        puzzle = _one_attempt(
            usable,
            options,
            attempt_rng,
            language=language,
            weights=weights,
            original_entries=original_entries,
        )
        if best is None or puzzle.score > best.score:
            best = puzzle
        if progress is not None:
            progress(index + 1, attempts)
        if (
            best.placed_count == len(usable)
            and best.score >= target
            and index + 1 >= min(20, attempts)
        ):
            break
    assert best is not None
    elapsed = int((time.perf_counter() - started) * 1000)
    return Puzzle(
        rows=best.rows,
        cols=best.cols,
        letters=best.letters,
        entries=best.entries,
        unused=best.unused,
        score=best.score,
        seed=options.seed,
        language=language,
        candidate_count=best.candidate_count,
        elapsed_ms=elapsed,
        requested_count=len(usable),
    )


def _one_attempt(
    words: Sequence[WordToPlace],
    options: GenerateOptions,
    rng: random.Random,
    *,
    language: str,
    weights: ScoreWeights,
    original_entries: Sequence[CrosswordEntry],
) -> Puzzle:
    order = list(words)
    skipped: list[WordToPlace] = []
    if options.max_size is not None:
        fitting = [word for word in order if word.length <= options.max_size]
        if not fitting:
            return _empty_puzzle(options, language, tuple(original_entries))
        skipped.extend(word for word in order if word.length > options.max_size)
        order = fitting
    order.sort(key=lambda word: (-word.length, rng.random()))
    if len(order) > 1:
        seed_at = rng.randrange(min(3, len(order)))
        order[0], order[seed_at] = order[seed_at], order[0]
    grid = _Grid(options.max_size)
    first = order[0]
    first_dir = rng.choice(("across", "down"))
    grid.place(first, 0, 0, first_dir)
    for word in order[1:]:
        slots = grid.find_slots(word)
        if not slots:
            skipped.append(word)
            continue
        slots.sort(key=lambda slot: -slot.crossings)
        best_cross = slots[0].crossings
        top = [slot for slot in slots if slot.crossings == best_cross]
        chosen = rng.choice(top)
        grid.place(word, chosen.row, chosen.col, chosen.direction)
    return _freeze(
        grid,
        options,
        language=language,
        weights=weights,
        original_entries=original_entries,
        skipped=skipped,
    )


def _freeze(
    grid: _Grid,
    options: GenerateOptions,
    *,
    language: str,
    weights: ScoreWeights,
    original_entries: Sequence[CrosswordEntry],
    skipped: Sequence[WordToPlace],
) -> Puzzle:
    if not grid.cells:
        return _empty_puzzle(options, language, tuple(original_entries))
    rows_i = [r for r, _c in grid.cells]
    cols_i = [c for _r, c in grid.cells]
    min_r, max_r = min(rows_i), max(rows_i)
    min_c, max_c = min(cols_i), max(cols_i)
    rows = max_r - min_r + 1
    cols = max_c - min_c + 1
    matrix = [
        [grid.cells.get((min_r + r, min_c + c)) for c in range(cols)]
        for r in range(rows)
    ]
    letters = tuple(tuple(row) for row in matrix)
    raw = [
        (
            item.word,
            item.row - min_r,
            item.col - min_c,
            item.direction,
        )
        for item in grid.placed
    ]
    numbered = _assign_numbers(raw)
    unused_ids = {word.id for word in skipped}
    unused = tuple(entry for entry in original_entries if entry.id in unused_ids)
    score = score_puzzle(
        rows=rows,
        cols=cols,
        letters=letters,
        entries=numbered,
        unused_count=len(skipped),
        weights=weights,
    )
    return Puzzle(
        rows=rows,
        cols=cols,
        letters=letters,
        entries=numbered,
        unused=unused,
        score=round(score, 3),
        seed=options.seed,
        language=language,
        candidate_count=options.candidate_count,
        elapsed_ms=0,
        requested_count=len(grid.placed) + len(skipped),
    )


def _assign_numbers(
    raw: list[tuple[WordToPlace, int, int, str]],
) -> tuple[PlacedEntry, ...]:
    starts: dict[tuple[int, int], int] = {}
    ordered = sorted(raw, key=lambda item: (item[1], item[2], item[3]))
    next_number = 1
    numbered: list[PlacedEntry] = []
    for word, row, col, direction in ordered:
        key = (row, col)
        if key not in starts:
            starts[key] = next_number
            next_number += 1
        numbered.append(
            PlacedEntry(
                id=word.id,
                clue=word.clue,
                cells=word.cells,
                display_text=word.display_text,
                direction=direction,
                row=row,
                col=col,
                number=starts[key],
                clue_html=word.clue_html,
            )
        )
    numbered.sort(key=lambda entry: (entry.direction != "across", entry.number, entry.id))
    return tuple(numbered)


def _empty_puzzle(
    options: GenerateOptions, language: str, unused: tuple[CrosswordEntry, ...]
) -> Puzzle:
    return Puzzle(
        rows=0,
        cols=0,
        letters=(),
        entries=(),
        unused=unused,
        score=-1_000.0,
        seed=options.seed,
        language=language,
        candidate_count=options.candidate_count,
        elapsed_ms=0,
        requested_count=len(unused),
    )
