# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.settings import AddonSettings, DEFAULTS


def test_defaults_do_not_assume_a_deck_or_field_names() -> None:
    settings = AddonSettings()
    assert settings.deck_name == ""
    assert settings.search_query == ""
    assert settings.selection_mode == "random"
    assert settings.target_word_count == 20
    assert settings.answer_field == ""
    assert settings.clue_field == ""
    assert settings.include_due is True
    assert settings.include_new is False
    assert settings.minimum_answer_length == 3
    assert settings.answer_language == "japanese"
    assert settings.candidate_count == 250


def test_from_dict_fills_missing_keys() -> None:
    settings = AddonSettings.from_dict({"deck_name": "Core"})
    assert settings.deck_name == "Core"
    assert settings.answer_field == DEFAULTS["answer_field"]
    assert settings.target_word_count == 20


def test_legacy_default_japanese_search_is_discarded() -> None:
    settings = AddonSettings.from_dict({"search_query": "deck:Japanese"})
    assert settings.deck_name == ""
    assert settings.extra_query == ""


def test_legacy_search_keeps_a_real_deck() -> None:
    settings = AddonSettings.from_dict({"search_query": "deck:Mining tag::N2"})
    assert settings.deck_name == "Mining"
    assert settings.extra_query == "tag::N2"


def test_unknown_keys_are_preserved() -> None:
    settings = AddonSettings.from_dict({"future_flag": True, "deck_name": "X"})
    assert settings.extra["future_flag"] is True
    dumped = settings.to_dict()
    assert dumped["future_flag"] is True
    assert dumped["deck_name"] == "X"


def test_invalid_mode_falls_back_to_random() -> None:
    settings = AddonSettings.from_dict({"selection_mode": "weighted"})
    assert settings.selection_mode == "random"


def test_round_trip() -> None:
    original = AddonSettings(deck_name="Mining", extra_query="tag::N2", target_word_count=15)
    restored = AddonSettings.from_dict(original.to_dict())
    assert restored.deck_name == "Mining"
    assert restored.extra_query == "tag::N2"
    assert restored.target_word_count == 15


def test_legacy_single_fields_migrate_into_the_active_profile() -> None:
    japanese = AddonSettings.from_dict(
        {
            "answer_language": "japanese",
            "answer_field": "Reading",
            "clue_field": "Meaning",
            "clue_template": "{{Meaning}}",
        }
    )
    assert japanese.japanese_answer_field == "Reading"
    assert japanese.japanese_clue_field == "Meaning"
    assert japanese.japanese_clue_template == "{{Meaning}}"
    assert japanese.native_answer_field == ""

    native = AddonSettings.from_dict(
        {
            "answer_language": "native",
            "answer_field": "englishWord",
            "clue_field": "reading",
        }
    )
    assert native.native_answer_field == "englishWord"
    assert native.native_clue_field == "reading"
    assert native.japanese_answer_field == ""


def test_show_excluded_preview_defaults_off() -> None:
    settings = AddonSettings.from_dict({})
    assert settings.show_excluded_preview is False


def test_clue_marks_default_to_red_on_black() -> None:
    settings = AddonSettings.from_dict({})
    assert settings.clue_mark_color == "black"
    assert settings.clue_mark_text == "red"


def test_legacy_theme_highlight_migrates_to_red_on_black() -> None:
    settings = AddonSettings.from_dict({"clue_mark_color": "theme"})
    assert settings.clue_mark_color == "black"
    assert settings.clue_mark_text == "red"


def test_explicit_highlight_keeps_colour_and_gains_red_text() -> None:
    settings = AddonSettings.from_dict({"clue_mark_color": "gold"})
    assert settings.clue_mark_color == "gold"
    assert settings.clue_mark_text == "red"


def test_native_word_limits_default_to_none() -> None:
    settings = AddonSettings.from_dict({})
    assert settings.native_max_answer_words == 0


def test_native_max_answer_words_is_clamped_and_migrates_legacy_value() -> None:
    settings = AddonSettings.from_dict({"native_max_answer_words": 9})
    assert settings.native_max_answer_words == 3
    migrated = AddonSettings.from_dict({"native_min_answer_words": 1})
    assert migrated.native_max_answer_words == 1


def test_generation_output_defaults_to_interactive_and_validates_values() -> None:
    assert AddonSettings.from_dict({}).generation_output == "interactive"
    assert AddonSettings.from_dict({"generation_output": "pdf_preview"}).generation_output == "pdf_preview"
    assert AddonSettings.from_dict({"generation_output": "something_else"}).generation_output == "interactive"


def test_solved_crosswords_are_excluded_by_default() -> None:
    assert AddonSettings.from_dict({}).include_solved is False
    assert AddonSettings.from_dict({"include_solved": True}).include_solved is True
