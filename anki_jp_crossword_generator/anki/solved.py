# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable, reversible tags used to keep completed crossword notes separate."""

from __future__ import annotations

from datetime import date
from typing import Iterable

SOLVED_TAG_PREFIX = "anki_crossword::solved::"


def solved_tag(when: date | None = None) -> str:
    """Return a date-sorted tag for a puzzle completed on ``when``."""
    completed = when or date.today()
    return f"{SOLVED_TAG_PREFIX}{completed.isoformat()}"


def is_solved(tags: Iterable[str]) -> bool:
    """Whether a note has ever been marked solved by this add-on."""
    prefix = SOLVED_TAG_PREFIX.casefold()
    return any(str(tag).casefold().startswith(prefix) for tag in tags)
