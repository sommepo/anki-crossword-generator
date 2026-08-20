# SPDX-License-Identifier: GPL-3.0-or-later
"""Pick a crossword headword from a Native-language field.

Alphabetic puzzles use a single written word (or a hyphenated compound), not a
dictionary gloss. This step is shared by every Latin-alphabet native language:

* split synonym lists (comma / semicolon)
* drop a leading infinitive particle (English ``to ``)
* prefer the first remaining single token

Japanese answers never use this module.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# List separators only — never split on spaces (that would break "New York").
_LIST_SPLIT = re.compile(r"\s*[,;、，]+\s*")
_PARENS = re.compile(r"\s*\([^)]*\)\s*")

# First-token particles that are not crossword material in alphabetic puzzles.
# Matched only as a whole token plus following space, so Spanish "todo" is safe.
_LEADING_PARTICLES = re.compile(r"^(?:to)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class NativeHeadword:
    """One field value reduced to a crossword headword plus mask targets."""

    original: str
    chosen: str
    alternatives: tuple[str, ...]

    @property
    def mask_targets(self) -> tuple[str, ...]:
        """Forms that may appear in an example sentence."""
        seen: list[str] = []
        keys: set[str] = set()
        for item in (self.chosen, *self.alternatives, self.original):
            text = item.strip()
            if not text:
                continue
            key = text.casefold()
            if key not in keys:
                keys.add(key)
                seen.append(text)
        return tuple(seen)


def extract_native_headword(text: str) -> NativeHeadword:
    """Return the crossword headword without mutating ``text``."""
    original = text
    nfc = unicodedata.normalize("NFC", text).strip()
    if not nfc:
        return NativeHeadword(original=original, chosen="", alternatives=())

    cleaned: list[str] = []
    seen: set[str] = set()
    for part in _LIST_SPLIT.split(nfc):
        item = _clean_alternative(part)
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

    if not cleaned:
        return NativeHeadword(original=original, chosen="", alternatives=())

    singles = [item for item in cleaned if _is_single_token(item)]
    chosen = singles[0] if singles else cleaned[0]
    return NativeHeadword(
        original=original,
        chosen=chosen,
        alternatives=tuple(cleaned),
    )


def _clean_alternative(part: str) -> str:
    text = _PARENS.sub(" ", part).strip()
    text = _LEADING_PARTICLES.sub("", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _is_single_token(text: str) -> bool:
    if not text or any(char.isspace() for char in text):
        return False
    return True


def native_word_count(text: str) -> int:
    """Count whitespace-separated words in a Native headword."""
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    return len(cleaned.split())
