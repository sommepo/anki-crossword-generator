# SPDX-License-Identifier: GPL-3.0-or-later
"""Phase 3 input types. No Anki, Qt, HTML parsing, or grid solver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..normalization.base import NormalizedAnswer


@dataclass(frozen=True)
class CrosswordEntry:
    """One clue/answer pair ready for the future generator."""

    id: str
    answer: NormalizedAnswer
    clue: str
    clue_html: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CrosswordInput:
    """Complete, language-neutral payload for a future CrosswordGenerator."""

    entries: tuple[CrosswordEntry, ...] = ()

    @property
    def size(self) -> int:
        return len(self.entries)
