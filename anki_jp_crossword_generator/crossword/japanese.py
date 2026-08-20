# SPDX-License-Identifier: GPL-3.0-or-later
"""Japanese crossword engine. Places kana/kanji/number cells."""

from __future__ import annotations

from collections.abc import Sequence

from .models import CrosswordEntry, CrosswordInput
from .options import GenerateOptions
from .placer import ProgressFn, WordToPlace, place_words
from .puzzle import Puzzle
from .scorer import JAPANESE_WEIGHTS


def generate_japanese(
    payload: CrosswordInput,
    options: GenerateOptions,
    *,
    progress: ProgressFn | None = None,
) -> Puzzle:
    """Build a Japanese-cell crossword from ``payload``."""
    entries, words = _japanese_words(payload.entries)
    return place_words(
        words,
        options,
        language="japanese",
        weights=JAPANESE_WEIGHTS,
        original_entries=entries,
        progress=progress,
    )


def _japanese_words(
    entries: Sequence[CrosswordEntry],
) -> tuple[tuple[CrosswordEntry, ...], list[WordToPlace]]:
    kept: list[CrosswordEntry] = []
    words: list[WordToPlace] = []
    for entry in entries:
        if entry.answer.language != "japanese":
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
