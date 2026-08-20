# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import pytest

from anki_jp_crossword_generator.anki.errors import SearchQueryError
from anki_jp_crossword_generator.settings import AddonSettings
from anki_jp_crossword_generator.vocabulary.selector import (
    combine_query,
    select_vocabulary,
)
from tests.fakes import FakeCollection, FakeNote, sample_notes


def _settings(**overrides: object) -> AddonSettings:
    data = {
        "search_query": "deck:Japanese",
        "selection_mode": "search",
        "target_word_count": 20,
        "random_seed": 1,
        "answer_field": "Reading",
        "clue_field": "Meaning",
    }
    data.update(overrides)
    return AddonSettings.from_dict(data)


def test_search_counts_notes_cards_and_unique_answers() -> None:
    collection = FakeCollection(sample_notes(10))
    result = select_vocabulary(collection, _settings())
    assert result.matching_notes == 10
    assert result.matching_cards == 20
    assert result.unique_valid == 10
    assert result.selected_count == 10
    assert "Reading" in result.discovered_fields
    assert "Meaning" in result.discovered_fields


def test_duplicate_answers_are_merged() -> None:
    notes = sample_notes(2)
    notes.append(
        FakeNote(
            note_id=9999,
            note_type="Japanese Vocab",
            fields={
                "Expression": "延期する",
                "Reading": "えんきする",
                "Meaning": "to put off",
            },
        )
    )
    collection = FakeCollection(notes)
    result = select_vocabulary(collection, _settings(target_word_count=20))
    assert result.unique_valid == 2
    assert result.skipped_duplicate == 1
    answers = [entry.answer_text for entry in result.selected]
    assert answers.count("えんきする") == 1


def test_empty_and_short_answers_are_skipped() -> None:
    notes = [
        FakeNote(1, "V", {"Reading": "", "Meaning": "x"}),
        FakeNote(2, "V", {"Reading": "あ", "Meaning": "x"}),
        FakeNote(3, "V", {"Reading": "あいう", "Meaning": "ok"}),
    ]
    result = select_vocabulary(FakeCollection(notes), _settings())
    assert result.skipped_empty == 1
    assert result.skipped_short == 1
    assert result.unique_valid == 1
    assert result.selected[0].answer_text == "あいう"


def test_missing_answer_field() -> None:
    notes = [FakeNote(1, "V", {"Front": "えんきする", "Meaning": "to postpone"})]
    result = select_vocabulary(FakeCollection(notes), _settings())
    assert result.unique_valid == 0
    assert result.missing_answer_field_count == 1
    assert any("valid answers" in warning for warning in result.warnings)


def test_missing_clue_field_skips_the_note() -> None:
    notes = [FakeNote(1, "V", {"Reading": "えんきする", "Gloss": "to postpone"})]
    result = select_vocabulary(FakeCollection(notes), _settings())
    assert result.unique_valid == 0
    assert result.missing_clue_field_count == 1
    assert result.skipped_empty_clue == 1
    assert any("clue field" in warning for warning in result.warnings)


def test_blank_clue_is_skipped_and_another_note_is_used() -> None:
    notes = [
        FakeNote(1, "V", {"Reading": "あああ", "Meaning": ""}),
        FakeNote(2, "V", {"Reading": "いいい", "Meaning": "yes"}),
    ]
    result = select_vocabulary(
        FakeCollection(notes), _settings(target_word_count=1, selection_mode="search")
    )
    assert result.skipped_empty_clue == 1
    assert result.unique_valid == 1
    assert result.selected[0].answer_text == "いいい"


def test_nonempty_field_query_excludes_empty_string_clues_from_the_pool() -> None:
    notes = [
        FakeNote(index, "V", {"Reading": f"あああ{index}", "englishSentence": ""})
        for index in range(15)
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
    result = select_vocabulary(
        FakeCollection(notes),
        _settings(
            search_query='deck:Japanese "Reading:*" "englishSentence:*"',
            clue_field="englishSentence",
            target_word_count=1,
            max_notes_scanned=10,
            selection_mode="random",
            random_seed=1,
        ),
        seed=1,
    )
    assert result.matching_notes == 1
    assert result.selected[0].note_id == 99


def test_scan_keeps_looking_past_html_blank_clues_beyond_the_cap() -> None:
    notes = [
        FakeNote(index, "V", {"Reading": f"あああ{index:02d}", "Meaning": "<br>"})
        for index in range(15)
    ]
    notes.append(
        FakeNote(99, "V", {"Reading": "えんきする", "Meaning": "The meeting was postponed."})
    )
    result = select_vocabulary(
        FakeCollection(notes),
        _settings(
            search_query="deck:Japanese",
            max_notes_scanned=10,
            target_word_count=1,
            selection_mode="search",
        ),
    )
    assert result.matching_notes == 16
    assert result.skipped_empty_clue == 15
    assert result.unique_valid == 1
    assert result.selected[0].note_id == 99
    assert result.scanned_notes == 16
    assert result.truncated is False


def test_max_notes_scanned_caps_eligible_notes_not_raw_ids() -> None:
    blanks = [
        FakeNote(index, "V", {"Reading": f"あああ{index:02d}", "Meaning": "<br>"})
        for index in range(20)
    ]
    goods = [
        FakeNote(100 + index, "V", {"Reading": f"いいい{index:02d}", "Meaning": f"clue {index}"})
        for index in range(8)
    ]
    result = select_vocabulary(
        FakeCollection(blanks + goods),
        _settings(
            search_query="deck:Japanese",
            max_notes_scanned=5,
            target_word_count=20,
            selection_mode="search",
        ),
    )
    assert result.matching_notes == 28
    assert result.unique_valid == 5
    assert result.skipped_empty_clue == 20
    assert result.truncated is True
    assert result.scanned_notes == 25


def test_case_insensitive_field_match() -> None:
    notes = [FakeNote(1, "V", {"reading": "えんきする", "meaning": "to postpone"})]
    result = select_vocabulary(FakeCollection(notes), _settings())
    assert result.unique_valid == 1
    assert result.selected[0].answer_text == "えんきする"
    assert result.selected[0].clue_text == "to postpone"


def test_html_is_stripped_in_preview() -> None:
    notes = [
        FakeNote(
            1,
            "V",
            {
                "Reading": "<b>えんきする</b>",
                "Meaning": "to <i>postpone</i>",
            },
        )
    ]
    result = select_vocabulary(FakeCollection(notes), _settings())
    assert result.selected[0].answer_text == "えんきする"
    assert result.selected[0].clue_text == "to postpone"
    assert "<" in result.selected[0].answer_raw


def test_tag_and_deck_query() -> None:
    notes = sample_notes(3)
    notes[0].tags = ("N2",)
    notes[1].tags = ("N3",)
    notes[2].tags = ("N2",)
    notes[2].deck_names = ("English",)
    collection = FakeCollection(notes)
    result = select_vocabulary(
        collection, _settings(search_query="deck:Japanese tag::N2")
    )
    assert result.matching_notes == 1
    assert result.selected[0].note_id == 1000


def test_random_selection_is_deterministic_with_seed() -> None:
    collection = FakeCollection(sample_notes(12))
    settings_a = _settings(selection_mode="random", target_word_count=5, random_seed=42)
    settings_b = _settings(selection_mode="random", target_word_count=5, random_seed=42)
    settings_c = _settings(selection_mode="random", target_word_count=5, random_seed=99)
    first = select_vocabulary(collection, settings_a, seed=42)
    second = select_vocabulary(collection, settings_b, seed=42)
    third = select_vocabulary(collection, settings_c, seed=99)
    assert [e.note_id for e in first.selected] == [e.note_id for e in second.selected]
    assert [e.note_id for e in first.selected] != [e.note_id for e in third.selected]


def test_due_mode_prefers_due_cards() -> None:
    notes = sample_notes(6, due=True)
    collection = FakeCollection(notes)
    result = select_vocabulary(
        collection, _settings(selection_mode="due", target_word_count=2)
    )
    assert result.selected_count == 2
    assert all(entry.is_due for entry in result.selected)


def test_due_mode_scans_due_notes_before_blank_early_ids() -> None:
    blanks = [
        FakeNote(
            index,
            "V",
            {"Reading": f"あああ{index:02d}", "Meaning": "early {index}"},
        )
        for index in range(12)
    ]
    due_note = FakeNote(
        99,
        "V",
        {"Reading": "えんきする", "Meaning": "The meeting was postponed."},
        due_card_ids=(990,),
        card_ids=(990,),
    )
    result = select_vocabulary(
        FakeCollection(blanks + [due_note]),
        _settings(
            search_query="deck:Japanese",
            selection_mode="due",
            max_notes_scanned=5,
            target_word_count=1,
        ),
    )
    assert result.selected[0].note_id == 99
    assert result.selected[0].is_due is True


def test_selected_mode_uses_provided_ids() -> None:
    collection = FakeCollection(sample_notes(6))
    result = select_vocabulary(
        collection,
        _settings(selection_mode="selected", target_word_count=20),
        selected_note_ids=[1002, 1004],
    )
    assert result.matching_notes == 2
    assert {entry.note_id for entry in result.selected} == {1002, 1004}


def test_selected_mode_without_ids_warns() -> None:
    collection = FakeCollection(sample_notes(3))
    result = select_vocabulary(
        collection, _settings(selection_mode="selected"), selected_note_ids=[]
    )
    assert result.unique_valid == 0
    assert any("Browse" in warning for warning in result.warnings)


def test_invalid_search_raises() -> None:
    collection = FakeCollection(sample_notes(1))
    with pytest.raises(SearchQueryError):
        select_vocabulary(collection, _settings(search_query="INVALID"))


def test_combine_query() -> None:
    assert combine_query("deck:Japanese", "is:due") == "(deck:Japanese) is:due"
    assert combine_query("", "is:due") == "is:due"


def test_too_few_words_warning() -> None:
    collection = FakeCollection(sample_notes(5))
    result = select_vocabulary(collection, _settings())
    assert result.unique_valid == 5
    assert any("at least 8" in warning.lower() for warning in result.warnings)


def test_native_max_words_scan_keeps_looking_past_multi_word_answers() -> None:
    notes = [
        FakeNote(index, "V", {"Reading": "あ", "Meaning": "two words"})
        for index in range(1, 9)
    ]
    notes.append(
        FakeNote(99, "V", {"Reading": "ふせる", "Meaning": "postpone"})
    )
    result = select_vocabulary(
        FakeCollection(notes),
        _settings(
            answer_field="Meaning",
            clue_field="Reading",
            answer_language="native",
            hide_target_in_example=False,
            native_max_answer_words=1,
            max_notes_scanned=5,
            minimum_answer_length=3,
        ),
    )
    answers = {entry.normalized.display_text.casefold() for entry in result.selected}
    assert "postpone" in answers
    assert "two words" not in answers
