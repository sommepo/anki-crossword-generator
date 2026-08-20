# SPDX-License-Identifier: GPL-3.0-or-later
"""Anki-independent snapshots of notes used for vocabulary selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class NoteSnapshot:
    """A note as seen by the crossword add-on.

    Field values are stored exactly as they appear on the note. Internal
    identifiers are kept for later phases and diagnostics, not for display.
    """

    note_id: int
    note_type: str
    tags: tuple[str, ...]
    fields: dict[str, str]
    card_ids: tuple[int, ...]
    deck_names: tuple[str, ...]
    due_card_ids: tuple[int, ...]

    @property
    def is_due(self) -> bool:
        return bool(self.due_card_ids)


class CollectionGateway(Protocol):
    """Minimal collection interface used by vocabulary selection.

    Implementations may wrap a live Anki collection or an in-memory fake.
    """

    def find_note_ids(self, query: str) -> Sequence[int]:
        """Return note ids matching an Anki search expression."""

    def find_card_ids(self, query: str) -> Sequence[int]:
        """Return card ids matching an Anki search expression."""

    def load_notes(self, note_ids: Sequence[int]) -> Sequence[NoteSnapshot]:
        """Load snapshots for the given note ids, preserving input order."""

    def list_decks(self) -> Sequence[str]:
        """Return deck names in Anki's tree order."""

    def fields_for_deck(self, deck_name: str) -> Sequence[str]:
        """Return field names used by note types in this deck."""

    def add_tags(self, note_ids: Sequence[int], tags: Sequence[str]) -> int:
        """Add tags to notes and return the number of notes updated."""
