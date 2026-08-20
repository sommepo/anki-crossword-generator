# SPDX-License-Identifier: GPL-3.0-or-later
"""Japanese crossword cells: one written character each, including small kana."""

from __future__ import annotations

import unicodedata

from .base import NormalizedAnswer

# Prolonged sound mark is a crossword cell, not punctuation.
_LONG_VOWEL = {"ー", "ｰ", "ㅡ"}


def _is_cell(char: str) -> bool:
    if char in _LONG_VOWEL:
        return True
    category = unicodedata.category(char)
    return category.startswith("L") or category.startswith("N")


def _is_ignorable(char: str) -> bool:
    if char in _LONG_VOWEL:
        return False
    if char.isspace() or char in {"\u3000"}:
        return True
    category = unicodedata.category(char)
    return category.startswith(("P", "Z")) or category in {"Cc", "Cf", "Cs", "Sk"}


class JapaneseAnswerNormalizer:
    """Split Japanese answers into independent kana/kanji/number cells."""

    language = "japanese"

    def normalize(self, text: str) -> NormalizedAnswer:
        original = text
        nfc = unicodedata.normalize("NFC", text)
        cells: list[str] = []
        unsupported: list[str] = []
        for char in nfc:
            if _is_cell(char):
                cells.append(char)
                continue
            if _is_ignorable(char):
                continue
            if char not in unsupported:
                unsupported.append(char)
        return NormalizedAnswer(
            original=original,
            normalized="".join(cells),
            cells=tuple(cells),
            language=self.language,
            display_text=original.strip(),
            unsupported_characters=tuple(unsupported),
        )
