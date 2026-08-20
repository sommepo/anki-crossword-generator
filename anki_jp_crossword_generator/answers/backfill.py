"""Deterministic preparation of a dedicated Native crossword-answer field.

This module deliberately has no dictionary or network dependency.  It turns a
source field into a conservative first headword and leaves any existing target
value alone.  The Anki-specific write step lives in the UI layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from ..normalization.headword import extract_native_headword
from ..vocabulary.text import strip_anki_html


@dataclass(frozen=True)
class BackfillPreview:
    """One prospective answer-field update."""

    note_id: int
    note_type: str
    source_text: str
    answer: str
    reason: str = ""

    @property
    def can_fill(self) -> bool:
        """Whether this row has a usable extracted answer."""
        return bool(self.answer)


def extract_crossword_answer(value: str | None) -> str:
    """Extract a conservative Native crossword answer from Anki field HTML."""
    visible = strip_anki_html(value or "")
    return extract_native_headword(visible).chosen.strip()


def preview_backfill(
    notes: Iterable[Mapping[str, object]], *, source_field: str, target_field: str
) -> tuple[BackfillPreview, ...]:
    """Plan blank-target updates without mutating notes or depending on Anki."""
    rows: list[BackfillPreview] = []
    for note in notes:
        fields = note.get("fields")
        if not isinstance(fields, Mapping):
            continue
        target = str(fields.get(target_field, "") or "").strip()
        if target:
            continue
        source = str(fields.get(source_field, "") or "")
        answer = extract_crossword_answer(source)
        rows.append(
            BackfillPreview(
                note_id=int(note.get("note_id", 0) or 0),
                note_type=str(note.get("note_type", "") or ""),
                source_text=strip_anki_html(source),
                answer=answer,
                reason="" if answer else "No usable answer could be extracted",
            )
        )
    return tuple(rows)
