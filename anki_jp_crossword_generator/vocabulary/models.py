# SPDX-License-Identifier: GPL-3.0-or-later
"""Vocabulary entries selected from an Anki collection."""

from __future__ import annotations

from dataclasses import dataclass

from ..normalization.base import NormalizedAnswer
from ..anki.gateway import NoteSnapshot


@dataclass(frozen=True)
class VocabEntry:
    """One unique crossword candidate derived from a note."""

    note_id: int
    card_ids: tuple[int, ...]
    note_type: str
    decks: tuple[str, ...]
    tags: tuple[str, ...]
    fields: dict[str, str]
    answer_field: str
    clue_field: str
    answer_raw: str
    answer_text: str
    clue_raw: str
    clue_text: str
    has_answer_field: bool
    has_clue_field: bool
    is_due: bool
    dedupe_key: str
    answer_language: str = "japanese"
    normalized: NormalizedAnswer | None = None
    included: bool = True
    status: str = "Valid"
    status_reason: str = ""
    source_expression: str | None = None
    source_reading: str | None = None
    cell_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SelectionResult:
    """Outcome of a vocabulary search / selection pass."""

    query: str
    selection_mode: str
    matching_notes: int
    matching_cards: int
    scanned_notes: int
    truncated: bool
    unique_valid: int
    selected: tuple[VocabEntry, ...]
    discovered_fields: tuple[str, ...]
    missing_answer_field_count: int
    missing_clue_field_count: int
    skipped_empty: int
    skipped_empty_clue: int
    skipped_short: int
    skipped_duplicate: int
    warnings: tuple[str, ...]
    seed: int | None = None
    error: str | None = None
    excluded: tuple[VocabEntry, ...] = ()
    preview: tuple[VocabEntry, ...] = ()

    @property
    def selected_count(self) -> int:
        return len(self.selected)

    @property
    def excluded_count(self) -> int:
        return len(self.excluded)

    @property
    def valid_count(self) -> int:
        return self.unique_valid


def discover_fields(notes: list[NoteSnapshot]) -> tuple[str, ...]:
    """Return field names in first-seen order across the matched notes."""
    seen: set[str] = set()
    ordered: list[str] = []
    for note in notes:
        for name in note.fields:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
    return tuple(ordered)


def resolve_field_name(requested: str, discovered: tuple[str, ...]) -> str:
    """Keep the user's field name; match case-insensitively when possible."""
    wanted = requested.strip()
    if not wanted:
        return wanted
    for name in discovered:
        if name == wanted:
            return name
    lowered = wanted.casefold()
    for name in discovered:
        if name.casefold() == lowered:
            return name
    return wanted


def suggest_field(
    discovered: tuple[str, ...],
    hints: tuple[str, ...],
    current: str = "",
) -> str:
    """Pick a field from the deck: keep a valid current name, else first hint hit."""
    if current.strip():
        resolved = resolve_field_name(current, discovered)
        if resolved in discovered:
            return resolved
    for hint in hints:
        resolved = resolve_field_name(hint, discovered)
        if resolved in discovered:
            return resolved
    return discovered[0] if discovered else ""
