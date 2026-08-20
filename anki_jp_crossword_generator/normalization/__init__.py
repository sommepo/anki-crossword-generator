# SPDX-License-Identifier: GPL-3.0-or-later
"""Answer normalisation. No Anki, Qt, or crossword-engine imports."""

from .base import (
    AnswerNormalizer,
    NormalizedAnswer,
    language_label,
    normalize_language,
)
from .japanese import JapaneseAnswerNormalizer
from .native import NativeAnswerNormalizer, OtherAnswerNormalizer


def get_normalizer(
    language: str,
    *,
    drop_apostrophes: bool = True,
) -> AnswerNormalizer:
    """Return the normaliser for an answer-language code."""
    key = normalize_language(language)
    if key == "japanese":
        return JapaneseAnswerNormalizer()
    if key == "other":
        return OtherAnswerNormalizer(drop_apostrophes=drop_apostrophes)
    return NativeAnswerNormalizer(drop_apostrophes=drop_apostrophes)


__all__ = [
    "AnswerNormalizer",
    "JapaneseAnswerNormalizer",
    "NativeAnswerNormalizer",
    "NormalizedAnswer",
    "OtherAnswerNormalizer",
    "get_normalizer",
    "language_label",
    "normalize_language",
]
