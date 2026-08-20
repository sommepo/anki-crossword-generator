# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.normalization import NativeAnswerNormalizer


def _normalize(text: str, *, drop_apostrophes: bool = True):
    return NativeAnswerNormalizer(drop_apostrophes=drop_apostrophes).normalize(text)


def _cells(text: str, *, drop_apostrophes: bool = True) -> list[str]:
    return list(_normalize(text, drop_apostrophes=drop_apostrophes).cells)


def test_to_postpone() -> None:
    result = _normalize("to postpone")
    assert list(result.cells) == list("POSTPONE")
    assert result.display_text == "postpone"
    assert result.original == "to postpone"


def test_comma_separated_synonyms_use_the_first_headword() -> None:
    result = _normalize("postpone, delay, put off")
    assert list(result.cells) == list("POSTPONE")
    assert result.display_text == "postpone"
    assert result.original == "postpone, delay, put off"


def test_take_care_of() -> None:
    assert _cells("take care of") == list("TAKECAREOF")


def test_mother_in_law() -> None:
    assert _cells("mother-in-law") == list("MOTHERINLAW")


def test_dont_drops_apostrophe() -> None:
    result = NativeAnswerNormalizer().normalize("don't")
    assert list(result.cells) == list("DONT")
    assert result.original == "don't"


def test_hello_world_casefold() -> None:
    assert _cells("Hello World") == list("HELLOWORLD")


def test_apostrophes_can_be_kept() -> None:
    result = NativeAnswerNormalizer(drop_apostrophes=False).normalize("don't")
    assert result.unsupported_characters == ("'",)


def test_original_is_not_mutated() -> None:
    original = "To Postpone"
    result = NativeAnswerNormalizer().normalize(original)
    assert result.original == "To Postpone"
    assert result.normalized == "POSTPONE"
    assert result.display_text == "Postpone"
