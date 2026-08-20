# SPDX-License-Identifier: GPL-3.0-or-later
"""Native (alphabetic) crossword engine. Places letter/digit cells."""

from __future__ import annotations

from collections.abc import Sequence

from .models import CrosswordEntry, CrosswordInput
from .options import GenerateOptions
from .placer import ProgressFn, WordToPlace, place_words
from .puzzle import Puzzle
from .scorer import NATIVE_WEIGHTS

_NATIVE_LANGUAGES = frozenset({"native", "other"})


def generate_native(
    payload: CrosswordInput,
    options: GenerateOptions,
    *,
    progress: ProgressFn | None = None,
) -> Puzzle:
    """Build an alphabetic crossword from ``payload``."""
    entries, words = _native_words(payload.entries)
    return place_words(
        words,
        options,
        language="native",
        weights=NATIVE_WEIGHTS,
        original_entries=entries,
        progress=progress,
    )


def _native_words(
    entries: Sequence[CrosswordEntry],
) -> tuple[tuple[CrosswordEntry, ...], list[WordToPlace]]:
    kept: list[CrosswordEntry] = []
    words: list[WordToPlace] = []
    for entry in entries:
        if entry.answer.language not in _NATIVE_LANGUAGES:
            continue
        if len(entry.answer.cells) < 2:
            continue
        kept.append(entry)
        words.append(
            WordToPlace(
                id=entry.id,
                cells=entry.answer.cells,
                clue=entry.clue,
                display_text=entry.answer.display_text,
                source=entry,
                clue_html=entry.clue_html,
            )
        )
    return tuple(kept), words
