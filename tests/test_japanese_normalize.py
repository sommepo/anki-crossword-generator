# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.normalization import JapaneseAnswerNormalizer


def _cells(text: str) -> list[str]:
    return list(JapaneseAnswerNormalizer().normalize(text).cells)


def test_kyou_small_kana_are_separate_cells() -> None:
    assert _cells("きょう") == ["き", "ょ", "う"]


def test_gakkou() -> None:
    assert _cells("がっこう") == ["が", "っ", "こ", "う"]


def test_shougakkou() -> None:
    assert _cells("しょうがっこう") == ["し", "ょ", "う", "が", "っ", "こ", "う"]


def test_super_long_vowel() -> None:
    assert _cells("スーパー") == ["ス", "ー", "パ", "ー"]


def test_ticket() -> None:
    assert _cells("チケット") == ["チ", "ケ", "ッ", "ト"]


def test_party_small_katakana() -> None:
    assert _cells("パーティー") == ["パ", "ー", "テ", "ィ", "ー"]


def test_konnichiwa() -> None:
    assert _cells("こんにちは") == ["こ", "ん", "に", "ち", "は"]


def test_ippai() -> None:
    assert _cells("いっぱい") == ["い", "っ", "ぱ", "い"]


def test_computer() -> None:
    assert _cells("コンピューター") == ["コ", "ン", "ピ", "ュ", "ー", "タ", "ー"]


def test_punctuation_is_stripped_original_preserved() -> None:
    result = JapaneseAnswerNormalizer().normalize("「こんにちは」")
    assert result.original == "「こんにちは」"
    assert list(result.cells) == ["こ", "ん", "に", "ち", "は"]


def test_middle_dot_removed() -> None:
    assert _cells("スーパー・マーケット") == list("スーパーマーケット")


def test_spaces_removed_from_cells() -> None:
    result = JapaneseAnswerNormalizer().normalize("お 元 気 で す か")
    assert list(result.cells) == ["お", "元", "気", "で", "す", "か"]
    assert result.original == "お 元 気 で す か"


def test_mixed_kana_kanji_ascii_and_numbers() -> None:
    result = JapaneseAnswerNormalizer().normalize("TVが2つ")
    assert list(result.cells) == ["T", "V", "が", "2", "つ"]


def test_unsupported_emoji_is_reported() -> None:
    result = JapaneseAnswerNormalizer().normalize("あ😀い")
    assert result.unsupported_characters == ("😀",)
    assert list(result.cells) == ["あ", "い"]
