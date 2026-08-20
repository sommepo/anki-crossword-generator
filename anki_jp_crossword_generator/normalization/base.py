# SPDX-License-Identifier: GPL-3.0-or-later
"""Language-neutral crossword answer representation and normaliser protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

KNOWN_LANGUAGES = ("japanese", "native", "other")


@dataclass(frozen=True)
class NormalizedAnswer:
    """One crossword answer after language-specific cell splitting.

    The future generator consumes only this object. It does not need to know
    whether the source text was Japanese, native-language, or something else.
    """

    original: str
    normalized: str
    cells: tuple[str, ...]
    language: str
    display_text: str
    unsupported_characters: tuple[str, ...] = ()

    @property
    def cell_count(self) -> int:
        return len(self.cells)


class AnswerNormalizer(Protocol):
    """Turn visible answer text into crossword cells."""

    language: str

    def normalize(self, text: str) -> NormalizedAnswer:
        """Return cells for ``text``. Never mutates the caller's string."""


def language_label(language: str) -> str:
    """User-facing name for an answer language code."""
    labels = {
        "japanese": "Japanese",
        "native": "Native",
        "other": "Other",
    }
    key = (language or "japanese").strip().lower()
    if key not in KNOWN_LANGUAGES:
        key = "japanese"
    return labels.get(key, key)


def normalize_language(value: str | None) -> str:
    """Return a known answer-language code, defaulting to Japanese."""
    key = (value or "japanese").strip().lower()
    if key in {"english"}:
        return "native"
    if key in KNOWN_LANGUAGES:
        return key
    return "japanese"
