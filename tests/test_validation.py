# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.normalization import (
    JapaneseAnswerNormalizer,
    NativeAnswerNormalizer,
)
from anki_jp_crossword_generator.vocabulary.validation import validate_answer


def test_too_short() -> None:
    answer = JapaneseAnswerNormalizer().normalize("あ")
    result = validate_answer(answer, minimum_cells=3, maximum_cells=22)
    assert result.ok is False
    assert result.code == "too_short"


def test_valid_japanese() -> None:
    answer = JapaneseAnswerNormalizer().normalize("えんきする")
    result = validate_answer(answer, minimum_cells=3, maximum_cells=22)
    assert result.ok is True
    assert answer.cell_count == 5


def test_too_long() -> None:
    answer = NativeAnswerNormalizer().normalize("this answer is far too long for a grid")
    result = validate_answer(answer, minimum_cells=3, maximum_cells=10)
    assert result.ok is False
    assert result.code == "too_long"


def test_unsupported() -> None:
    answer = JapaneseAnswerNormalizer().normalize("あ😀")
    result = validate_answer(answer, minimum_cells=1, maximum_cells=22)
    assert result.ok is False
    assert result.code == "unsupported"


def test_empty() -> None:
    answer = NativeAnswerNormalizer().normalize("...")
    result = validate_answer(answer, minimum_cells=3, maximum_cells=22)
    assert result.ok is False
    assert result.code == "empty"


def test_native_phrase_kept_when_there_is_no_minimum() -> None:
    answer = NativeAnswerNormalizer().normalize("going into a frenzy")
    result = validate_answer(
        answer,
        minimum_cells=3,
        maximum_cells=22,
        minimum_native_words=0,
    )
    assert result.ok is True


def test_native_phrase_skipped_when_maximum_is_one() -> None:
    answer = NativeAnswerNormalizer().normalize("lie down")
    result = validate_answer(
        answer,
        minimum_cells=3,
        maximum_cells=22,
        maximum_native_words=1,
    )
    assert result.ok is False
    assert result.code == "word_count"


def test_native_two_word_answer_meets_maximum_of_two() -> None:
    answer = NativeAnswerNormalizer().normalize("lie down")
    result = validate_answer(
        answer,
        minimum_cells=3,
        maximum_cells=22,
        maximum_native_words=2,
    )
    assert result.ok is True
