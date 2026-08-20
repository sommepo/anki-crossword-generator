# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.normalization.headword import (
    extract_native_headword,
    native_word_count,
)


def test_strips_leading_infinitive_to() -> None:
    head = extract_native_headword("to postpone")
    assert head.original == "to postpone"
    assert head.chosen == "postpone"


def test_prefers_first_single_token_in_a_list() -> None:
    head = extract_native_headword("postpone, delay, put off")
    assert head.original == "postpone, delay, put off"
    assert head.chosen == "postpone"
    assert head.alternatives == ("postpone", "delay", "put off")


def test_strips_to_before_choosing_from_a_list() -> None:
    head = extract_native_headword("to postpone, delay")
    assert head.chosen == "postpone"


def test_keeps_uncut_phrases_without_commas() -> None:
    head = extract_native_headword("take care of")
    assert head.chosen == "take care of"


def test_does_not_mutate_the_original_string() -> None:
    original = "To Postpone"
    head = extract_native_headword(original)
    assert original == "To Postpone"
    assert head.original == "To Postpone"
    assert head.chosen == "Postpone"


def test_native_word_count_splits_on_spaces() -> None:
    assert native_word_count("postpone") == 1
    assert native_word_count("lie down") == 2
    assert native_word_count("take care of") == 3
    assert native_word_count("going into a frenzy") == 4
    assert native_word_count("mother-in-law") == 1
