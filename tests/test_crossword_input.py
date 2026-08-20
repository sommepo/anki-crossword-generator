# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.session import CrosswordSession
from anki_jp_crossword_generator.settings import AddonSettings
from tests.fakes import FakeCollection, sample_notes


def test_crossword_input_has_no_anki_types() -> None:
    session = CrosswordSession(
        FakeCollection(sample_notes(3)),
        AddonSettings.from_dict(
            {
                "deck_name": "Japanese",
                "selection_mode": "search",
                "answer_field": "Reading",
                "clue_field": "Meaning",
                "answer_language": "japanese",
                "hide_target_in_example": False,
            }
        ),
    )
    session.search()
    payload = session.to_crossword_input()
    assert payload.size == 3
    first = payload.entries[0]
    assert first.id == "1000"
    assert list(first.answer.cells) == ["え", "ん", "き", "す", "る"]
    assert first.clue == "to postpone"
    assert not hasattr(first, "note_id")
    assert "note_id" not in first.__dataclass_fields__


def test_crossword_input_keeps_clue_html() -> None:
    from tests.fakes import FakeNote

    notes = [
        FakeNote(
            1,
            "V",
            {
                "Reading": "えんきする",
                "Meaning": (
                    'to <b>postpone</b> '
                    '<span style="background-color: yellow;">now</span>'
                ),
            },
        )
    ]
    session = CrosswordSession(
        FakeCollection(notes),
        AddonSettings.from_dict(
            {
                "deck_name": "Japanese",
                "selection_mode": "search",
                "answer_field": "Reading",
                "clue_field": "Meaning",
                "answer_language": "japanese",
                "hide_target_in_example": False,
            }
        ),
    )
    session.search()
    first = session.to_crossword_input().entries[0]
    assert first.clue == "to postpone now"
    assert "<b>postpone</b>" in first.clue_html
    assert "background-color: yellow;" in first.clue_html
