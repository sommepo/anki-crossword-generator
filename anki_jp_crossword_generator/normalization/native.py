# SPDX-License-Identifier: GPL-3.0-or-later
"""Native-language crossword cells (Latin script, e.g. the user's L1)."""

from __future__ import annotations

import unicodedata

from .base import NormalizedAnswer
from .headword import extract_native_headword

_APOSTROPHES = {"'", "’", "‘", "ʼ", "＇", "`"}


def _is_cell(char: str) -> bool:
    category = unicodedata.category(char)
    return category.startswith("L") or category.startswith("N")


def _is_ignorable(char: str, *, drop_apostrophes: bool) -> bool:
    if char in _APOSTROPHES:
        return drop_apostrophes
    if char.isspace() or char in {"\u3000"}:
        return True
    category = unicodedata.category(char)
    return category.startswith(("P", "Z")) or category in {"Cc", "Cf", "Cs", "Sk"}


def _cell_form(char: str) -> str:
    upper = char.upper()
    return upper if len(upper) == 1 else char


class NativeAnswerNormalizer:
    """One cell per letter or digit after stripping spaces and punctuation."""

    language = "native"

    def __init__(self, *, drop_apostrophes: bool = True) -> None:
        self.drop_apostrophes = drop_apostrophes

    def normalize(self, text: str) -> NormalizedAnswer:
        original = text
        head = extract_native_headword(text)
        source = head.chosen or text
        nfc = unicodedata.normalize("NFC", source)
        cells: list[str] = []
        unsupported: list[str] = []
        for char in nfc:
            if _is_cell(char):
                cells.append(_cell_form(char))
                continue
            if _is_ignorable(char, drop_apostrophes=self.drop_apostrophes):
                continue
            if char not in unsupported:
                unsupported.append(char)
        return NormalizedAnswer(
            original=original,
            normalized="".join(cells),
            cells=tuple(cells),
            language=self.language,
            display_text=head.chosen.strip() or original.strip(),
            unsupported_characters=tuple(unsupported),
        )


class OtherAnswerNormalizer(NativeAnswerNormalizer):
    """Generic letter/digit cells for Other / Custom answers."""

    language = "other"
