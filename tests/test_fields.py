# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.anki.gateway import NoteSnapshot
from anki_jp_crossword_generator.vocabulary.models import (
    discover_fields,
    resolve_field_name,
    suggest_field,
)


def _note(fields: dict[str, str]) -> NoteSnapshot:
    return NoteSnapshot(
        note_id=1,
        note_type="V",
        tags=(),
        fields=fields,
        card_ids=(1,),
        deck_names=("Japanese",),
        due_card_ids=(),
    )


def test_discover_fields_preserves_first_seen_order() -> None:
    notes = [
        _note({"Reading": "a", "Meaning": "b"}),
        _note({"Reading": "c", "Example": "d", "Meaning": "e"}),
    ]
    assert discover_fields(notes) == ("Reading", "Meaning", "Example")


def test_resolve_field_matches_case_insensitively() -> None:
    discovered = ("reading", "meaning")
    assert resolve_field_name("Reading", discovered) == "reading"
    assert resolve_field_name("Meaning", discovered) == "meaning"
    assert resolve_field_name("Expression", discovered) == "Expression"


def test_suggest_field_uses_deck_fields_not_hardcoded_defaults() -> None:
    discovered = ("wordDictionaryForm", "reading", "definition")
    assert suggest_field(discovered, ("reading", "Reading"), "") == "reading"
    assert suggest_field(discovered, ("definition", "Meaning"), "") == "definition"
    assert (
        suggest_field(discovered, ("reading",), "Reading") == "reading"
    )
