# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import pytest

from anki_jp_crossword_generator.anki.errors import SearchQueryError
from anki_jp_crossword_generator.session import CrosswordSession
from anki_jp_crossword_generator.settings import AddonSettings
from tests.fakes import FakeCollection, FakeNote, sample_notes


def _session(count: int, **overrides: object) -> CrosswordSession:
    settings = AddonSettings.from_dict(
        {
            "deck_name": "Japanese",
            "selection_mode": "search",
            "target_word_count": 20,
            "random_seed": 1,
            "answer_field": "Reading",
            "clue_field": "Meaning",
            **overrides,
        }
    )
    return CrosswordSession(FakeCollection(sample_notes(count)), settings)


def test_generate_disabled_until_enough_vocabulary() -> None:
    session = _session(5)
    session.search()
    assert session.can_generate() is False
    reason = session.generate_blocked_reason()
    assert reason is not None
    assert "5 eligible" in reason
    assert "8" in reason


def test_generate_enabled_when_enough_vocabulary_exists() -> None:
    session = _session(12)
    session.search()
    assert session.last_result is not None
    assert session.last_result.unique_valid == 12
    assert session.can_generate() is True
    assert session.generate_blocked_reason() is None


def test_generate_builds_a_connected_japanese_grid() -> None:
    session = _session(12, candidate_count=60, quality="fast")
    session.search()
    puzzle = session.generate("japanese", new_seed=True)
    assert puzzle.placed_count >= 8
    assert puzzle.language == "japanese"
    assert puzzle.rows >= 1 and puzzle.cols >= 1
    occupied = [
        (row, col)
        for row in range(puzzle.rows)
        for col in range(puzzle.cols)
        if puzzle.letter_at(row, col)
    ]
    assert occupied
    assert session.last_puzzle is puzzle


def test_changing_answer_field_updates_preview_without_losing_scan() -> None:
    session = _session(8)
    session.search()
    first_ids = [entry.note_id for entry in session.last_result.selected]
    session.set_clue_field("Example")
    result = session.refresh_preview()
    assert [entry.note_id for entry in result.selected] == first_ids
    assert result.selected[0].clue_field == "Example"
    assert result.selected[0].clue_text.startswith("Example for")


def test_preview_lists_exact_vocabulary() -> None:
    session = _session(3, selection_mode="search", target_word_count=20)
    result = session.search()
    answers = [entry.answer_text for entry in result.selected]
    clues = [entry.clue_text for entry in result.selected]
    assert answers == ["えんきする", "ちょうさする", "さける"]
    assert clues == ["to postpone", "to investigate", "to avoid"]


def test_no_search_yet_cannot_generate() -> None:
    session = _session(12)
    assert session.can_generate() is False
    assert session.generate_blocked_reason() == "Preview vocabulary first."


def test_search_requires_a_deck() -> None:
    session = CrosswordSession(FakeCollection(sample_notes(3)), AddonSettings())
    with pytest.raises(SearchQueryError, match="Choose a deck"):
        session.search()


def test_search_can_run_twice() -> None:
    session = _session(8)
    first = session.search(force_reload=True)
    second = session.search(force_reload=True)
    assert second.unique_valid == first.unique_valid
    assert second.selected_count == first.selected_count


def test_fields_come_from_the_selected_deck() -> None:
    collection = FakeCollection(
        [
            FakeNote(
                1,
                "Mining",
                {"reading": "あいう", "definition": "to postpone"},
                deck_names=("Mining",),
            ),
            FakeNote(
                2,
                "English",
                {"Front": "hello", "Back": "there"},
                deck_names=("English",),
            ),
        ]
    )
    session = CrosswordSession(collection, AddonSettings(deck_name="Mining"))
    fields = session.fields_for_current_deck()
    assert fields == ("reading", "definition")
    answer, clue = session.apply_field_suggestions(fields)
    assert answer == "reading"
    assert clue == "definition"
    assert session.settings.native_answer_field == "definition"
    assert session.settings.native_clue_field == "reading"


def test_japanese_and_native_profiles_are_independent() -> None:
    session = _session(3, hide_target_in_example=False)
    session.set_profile_answer_field("japanese", "Reading")
    session.set_profile_clue_field("japanese", "Meaning")
    session.set_profile_answer_field("native", "Meaning")
    session.set_profile_clue_field("native", "Reading")
    japanese = session.search(language="japanese")
    assert japanese.selected[0].answer_text == "えんきする"
    native = session.search(language="native")
    assert native.selected[0].answer_text == "to postpone"
    assert native.selected[0].normalized.display_text == "postpone"
    assert list(native.selected[0].normalized.cells) == list("POSTPONE")
    assert session.settings.japanese_answer_field == "Reading"
    assert session.settings.japanese_clue_field == "Meaning"


def test_mining_fields_prefer_english_word_for_native() -> None:
    collection = FakeCollection(
        [
            FakeNote(
                1,
                "Mining",
                {
                    "reading": "えんきする",
                    "englishWord": "postpone, delay",
                    "englishSentence": "The meeting was postponed.",
                },
                deck_names=("Mining",),
            )
        ]
    )
    session = CrosswordSession(collection, AddonSettings(deck_name="Mining"))
    session.apply_field_suggestions(session.fields_for_current_deck())
    assert session.settings.japanese_answer_field == "reading"
    assert session.settings.native_answer_field == "englishWord"
    assert session.settings.native_clue_field == "reading"
    result = session.search(language="native")
    assert result.selected[0].normalized.display_text == "postpone"
    assert list(result.selected[0].normalized.cells) == list("POSTPONE")


def test_blank_clues_are_filtered_before_the_word_cap() -> None:
    notes = [
        FakeNote(index, "V", {"Reading": f"あああ{index:02d}", "englishSentence": "<br>"})
        for index in range(25)
    ]
    notes.append(
        FakeNote(
            99,
            "V",
            {
                "Reading": "えんきする",
                "englishSentence": "The meeting was postponed.",
            },
        )
    )
    session = CrosswordSession(
        FakeCollection(notes),
        AddonSettings.from_dict(
            {
                "deck_name": "Japanese",
                "selection_mode": "random",
                "target_word_count": 1,
                "random_seed": 1,
                "answer_field": "Reading",
                "clue_field": "englishSentence",
                "max_notes_scanned": 10,
            }
        ),
    )
    result = session.search()
    assert result.selected_count == 1
    assert result.selected[0].note_id == 99
    assert result.skipped_empty_clue == 25
