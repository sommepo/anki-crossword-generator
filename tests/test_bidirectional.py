# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.settings import AddonSettings
from anki_jp_crossword_generator.vocabulary.selector import select_vocabulary
from tests.fakes import FakeCollection, FakeNote, sample_notes


def test_japanese_answer_native_clue() -> None:
    result = select_vocabulary(
        FakeCollection(sample_notes(1)),
        AddonSettings.from_dict(
            {
                "search_query": "deck:Japanese",
                "answer_field": "Reading",
                "clue_field": "Meaning",
                "answer_language": "japanese",
                "hide_target_in_example": False,
            }
        ),
    )
    entry = result.selected[0]
    assert entry.answer_text == "えんきする"
    assert entry.clue_text == "to postpone"
    assert entry.answer_language == "japanese"
    assert list(entry.normalized.cells) == ["え", "ん", "き", "す", "る"]


def test_native_answer_japanese_clue() -> None:
    result = select_vocabulary(
        FakeCollection(sample_notes(1)),
        AddonSettings.from_dict(
            {
                "search_query": "deck:Japanese",
                "answer_field": "Meaning",
                "clue_field": "Reading",
                "answer_language": "native",
                "hide_target_in_example": False,
            }
        ),
    )
    entry = result.selected[0]
    assert entry.answer_text == "to postpone"
    assert entry.clue_text == "えんきする"
    assert entry.answer_language == "native"
    assert entry.normalized.display_text == "postpone"
    assert list(entry.normalized.cells) == list("POSTPONE")


def test_legacy_english_language_alias_is_native() -> None:
    settings = AddonSettings.from_dict({"answer_language": "english"})
    assert settings.answer_language == "native"


def test_native_duplicates_after_normalisation() -> None:
    notes = [
        FakeNote(1, "V", {"Reading": "えんきする", "Meaning": "TO POSTPONE"}),
        FakeNote(2, "V", {"Reading": "えんきする", "Meaning": "To Postpone"}),
        FakeNote(3, "V", {"Reading": "えんきする", "Meaning": "to postpone"}),
    ]
    result = select_vocabulary(
        FakeCollection(notes),
        AddonSettings.from_dict(
            {
                "search_query": "deck:Japanese",
                "answer_field": "Meaning",
                "clue_field": "Reading",
                "answer_language": "native",
                "hide_target_in_example": False,
            }
        ),
    )
    assert result.unique_valid == 1
    assert result.skipped_duplicate == 2
    assert result.selected[0].normalized.normalized == "POSTPONE"


def test_kanji_and_kana_are_not_semantic_duplicates() -> None:
    notes = [
        FakeNote(1, "V", {"Reading": "えんきする", "Meaning": "to postpone"}),
        FakeNote(2, "V", {"Reading": "延期する", "Meaning": "to postpone"}),
    ]
    result = select_vocabulary(
        FakeCollection(notes),
        AddonSettings.from_dict(
            {
                "search_query": "deck:Japanese",
                "answer_field": "Reading",
                "clue_field": "Meaning",
                "answer_language": "japanese",
                "hide_target_in_example": False,
            }
        ),
    )
    assert result.unique_valid == 2


def test_example_masking_with_japanese_answer() -> None:
    notes = [
        FakeNote(
            1,
            "V",
            {
                "Reading": "えんきする",
                "Meaning": "to postpone",
                "Example": "The meeting was postponed until next week.",
            },
        )
    ]
    result = select_vocabulary(
        FakeCollection(notes),
        AddonSettings.from_dict(
            {
                "search_query": "deck:Japanese",
                "answer_field": "Reading",
                "clue_field": "Example",
                "answer_language": "japanese",
                "hide_target_in_example": True,
                "clue_template": "{{Example}}",
            }
        ),
    )
    entry = result.selected[0]
    assert entry.answer_text == "えんきする"
    assert "_____" in entry.clue_text
    assert "postponed" not in entry.clue_text.lower()


def test_native_one_word_answers_skipped_when_minimum_is_two() -> None:
    notes = [
        FakeNote(1, "V", {"Reading": "ふせる", "Meaning": "lie down"}),
        FakeNote(2, "V", {"Reading": "ぎゃくじょう", "Meaning": "going into a frenzy"}),
        FakeNote(3, "V", {"Reading": "えんきする", "Meaning": "to postpone"}),
    ]
    result = select_vocabulary(
        FakeCollection(notes),
        AddonSettings.from_dict(
            {
                "search_query": "deck:Japanese",
                "answer_field": "Meaning",
                "clue_field": "Reading",
                "answer_language": "native",
                "hide_target_in_example": False,
                "minimum_answer_length": 3,
                "native_max_answer_words": 2,
            }
        ),
    )
    answers = {entry.normalized.display_text.casefold() for entry in result.selected}
    assert "lie down" in answers
    assert "going into a frenzy" in answers
    assert "going into a frenzy" not in answers
