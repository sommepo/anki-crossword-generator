# SPDX-License-Identifier: GPL-3.0-or-later
"""Weighted crossword quality score.

Weights are documented here so they can be tuned without hunting through
placement code. The scorer only sees geometry: placed spans and letters.
It does not know Japanese from Native.
"""

from __future__ import annotations

from dataclasses import dataclass

from .puzzle import PlacedEntry, Puzzle


@dataclass(frozen=True)
class ScoreWeights:
    """Linear weights. Positive terms reward; negative terms penalise."""

    placed_word: float = 100.0
    intersection: float = 14.0
    checked_cell: float = 5.0
    density: float = 40.0
    compactness: float = 18.0
    unused_word: float = -12.0
    isolated_word: float = -60.0
    extra_component: float = -80.0
    aspect: float = -16.0
    area: float = -0.12
    short3: float = -2.0
    two_letter: float = -25.0


# Japanese vocab is often 3–5 kana; do not punish 3-cell words heavily.
JAPANESE_WEIGHTS = ScoreWeights(short3=-0.5)

# Alphabetic puzzles benefit from a slightly stronger 3-letter penalty.
NATIVE_WEIGHTS = ScoreWeights(short3=-3.0)


def score_puzzle(
    *,
    rows: int,
    cols: int,
    letters: tuple[tuple[str | None, ...], ...],
    entries: tuple[PlacedEntry, ...],
    unused_count: int,
    weights: ScoreWeights,
) -> float:
    """Return a scalar quality score for a cropped grid."""
    if rows <= 0 or cols <= 0 or not entries:
        return -1_000.0 + unused_count * weights.unused_word

    filled = sum(1 for row in letters for cell in row if cell)
    area = max(1, rows * cols)
    density = filled / area
    crossings = _intersection_count(entries)
    checked = _checked_cell_count(entries)
    isolated = _isolated_count(entries)
    components = _component_count(letters)
    aspect_penalty = 0.0
    if min(rows, cols) > 0:
        aspect_penalty = (max(rows, cols) / min(rows, cols)) - 1.0
    short3 = sum(1 for entry in entries if entry.length == 3)
    two = sum(1 for entry in entries if entry.length <= 2)

    total = 0.0
    total += weights.placed_word * len(entries)
    total += weights.intersection * crossings
    total += weights.checked_cell * checked
    total += weights.density * density
    total += weights.compactness * density
    total += weights.unused_word * unused_count
    total += weights.isolated_word * isolated
    total += weights.extra_component * max(0, components - 1)
    total += weights.aspect * aspect_penalty
    total += weights.area * area
    total += weights.short3 * short3
    total += weights.two_letter * two
    return total


def excellent_threshold(requested: int, weights: ScoreWeights) -> float:
    """Stop early once every requested word is placed with solid crossings."""
    return requested * weights.placed_word + requested * 6.0 + 30.0


def _intersection_count(entries: tuple[PlacedEntry, ...]) -> int:
    cells: dict[tuple[int, int], int] = {}
    for entry in entries:
        for row, col in _span(entry):
            cells[row, col] = cells.get((row, col), 0) + 1
    return sum(1 for count in cells.values() if count >= 2)


def _checked_cell_count(entries: tuple[PlacedEntry, ...]) -> int:
    return _intersection_count(entries)


def _isolated_count(entries: tuple[PlacedEntry, ...]) -> int:
    if len(entries) <= 1:
        return 0
    occupancy: dict[tuple[int, int], int] = {}
    for entry in entries:
        for row, col in _span(entry):
            occupancy[row, col] = occupancy.get((row, col), 0) + 1
    isolated = 0
    for entry in entries:
        if not any(occupancy[pos] >= 2 for pos in _span(entry)):
            isolated += 1
    return isolated


def _component_count(letters: tuple[tuple[str | None, ...], ...]) -> int:
    rows = len(letters)
    cols = len(letters[0]) if letters else 0
    seen: set[tuple[int, int]] = set()
    components = 0
    for row in range(rows):
        for col in range(cols):
            if letters[row][col] is None or (row, col) in seen:
                continue
            components += 1
            stack = [(row, col)]
            seen.add((row, col))
            while stack:
                r, c = stack.pop()
                for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                    if (
                        0 <= nr < rows
                        and 0 <= nc < cols
                        and letters[nr][nc] is not None
                        and (nr, nc) not in seen
                    ):
                        seen.add((nr, nc))
                        stack.append((nr, nc))
    return components


def _span(entry: PlacedEntry) -> tuple[tuple[int, int], ...]:
    dr, dc = (0, 1) if entry.direction == "across" else (1, 0)
    return tuple((entry.row + dr * i, entry.col + dc * i) for i in range(entry.length))


def score_frozen(puzzle: Puzzle, weights: ScoreWeights) -> float:
    """Re-score an already built puzzle (tests / debugging)."""
    return score_puzzle(
        rows=puzzle.rows,
        cols=puzzle.cols,
        letters=puzzle.letters,
        entries=puzzle.entries,
        unused_count=puzzle.unused_count,
        weights=weights,
    )
