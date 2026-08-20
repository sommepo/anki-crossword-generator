# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import replace

from anki_jp_crossword_generator.crossword.japanese import generate_japanese
from anki_jp_crossword_generator.crossword.models import CrosswordEntry, CrosswordInput
from anki_jp_crossword_generator.crossword.native import generate_native
from anki_jp_crossword_generator.crossword.options import GenerateOptions, parse_grid_size
from anki_jp_crossword_generator.crossword.placer import WordToPlace, _Grid
from anki_jp_crossword_generator.normalization.japanese import JapaneseAnswerNormalizer
from anki_jp_crossword_generator.normalization.native import NativeAnswerNormalizer


def _jp(note_id: str, text: str, clue: str) -> CrosswordEntry:
    answer = JapaneseAnswerNormalizer().normalize(text)
    return CrosswordEntry(id=note_id, answer=answer, clue=clue)


def _na(note_id: str, text: str, clue: str) -> CrosswordEntry:
    answer = NativeAnswerNormalizer().normalize(text)
    return CrosswordEntry(id=note_id, answer=answer, clue=clue)


def _assert_matches_grid(puzzle) -> None:
    for entry in puzzle.entries:
        dr, dc = (0, 1) if entry.direction == "across" else (1, 0)
        for index, letter in enumerate(entry.cells):
            assert puzzle.letter_at(entry.row + dr * index, entry.col + dc * index) == letter


def _shared_cells(puzzle) -> int:
    occupancy: dict[tuple[int, int], int] = {}
    for entry in puzzle.entries:
        dr, dc = (0, 1) if entry.direction == "across" else (1, 0)
        for index in range(entry.length):
            pos = (entry.row + dr * index, entry.col + dc * index)
            occupancy[pos] = occupancy.get(pos, 0) + 1
    return sum(1 for count in occupancy.values() if count >= 2)


def test_parse_grid_size() -> None:
    assert parse_grid_size("auto") is None
    assert parse_grid_size("15x15") == 15
    assert parse_grid_size("13×13") == 13
    assert parse_grid_size("11") == 11


def test_known_japanese_pair_crosses() -> None:
    payload = CrosswordInput(
        entries=(
            _jp("1", "えんきする", "to postpone"),
            _jp("2", "きのう", "yesterday"),
        )
    )
    puzzle = generate_japanese(
        payload, GenerateOptions(seed=1, candidate_count=40)
    )
    assert puzzle.placed_count == 2
    assert puzzle.language == "japanese"
    assert _shared_cells(puzzle) >= 1
    _assert_matches_grid(puzzle)
    answers = {"".join(entry.cells) for entry in puzzle.entries}
    assert answers == {"えんきする", "きのう"}


def test_placed_clues_keep_html() -> None:
    postpone = replace(
        _jp("1", "えんきする", "to postpone"),
        clue_html="to <b>postpone</b>",
    )
    yesterday = _jp("2", "きのう", "yesterday")
    puzzle = generate_japanese(
        CrosswordInput(entries=(postpone, yesterday)),
        GenerateOptions(seed=1, candidate_count=20),
    )
    by_id = {entry.id: entry for entry in puzzle.entries}
    assert "<b>postpone</b>" in by_id["1"].clue_html


def test_generation_is_deterministic() -> None:
    payload = CrosswordInput(
        entries=(
            _jp("1", "えんきする", "postpone"),
            _jp("2", "きのう", "yesterday"),
            _jp("3", "がっこう", "school"),
            _jp("4", "せんせい", "teacher"),
            _jp("5", "ともだち", "friend"),
            _jp("6", "でんしゃ", "train"),
            _jp("7", "あした", "tomorrow"),
            _jp("8", "こうえん", "park"),
        )
    )
    options = GenerateOptions(seed=42, candidate_count=30)
    first = generate_japanese(payload, options)
    second = generate_japanese(payload, options)
    assert first.letters == second.letters
    assert first.score == second.score
    assert [ (e.row, e.col, e.direction, e.cells) for e in first.entries ] == [
        (e.row, e.col, e.direction, e.cells) for e in second.entries
    ]


def test_japanese_grid_is_connected_with_several_words() -> None:
    payload = CrosswordInput(
        entries=(
            _jp("1", "えんきする", "postpone"),
            _jp("2", "きのう", "yesterday"),
            _jp("3", "がっこう", "school"),
            _jp("4", "せんせい", "teacher"),
            _jp("5", "ともだち", "friend"),
            _jp("6", "でんしゃ", "train"),
            _jp("7", "あした", "tomorrow"),
            _jp("8", "こうえん", "park"),
            _jp("9", "びょういん", "hospital"),
            _jp("10", "べんきょうする", "study"),
        )
    )
    puzzle = generate_japanese(
        payload, GenerateOptions(seed=9, candidate_count=80)
    )
    assert puzzle.placed_count >= 6
    assert _shared_cells(puzzle) >= 2
    _assert_matches_grid(puzzle)
    assert puzzle.across() and puzzle.down()


def test_native_pair_crosses() -> None:
    payload = CrosswordInput(
        entries=(
            _na("1", "postpone", "えんきする"),
            _na("2", "school", "がっこう"),
            _na("3", "train", "でんしゃ"),
            _na("4", "park", "こうえん"),
            _na("5", "teacher", "せんせい"),
            _na("6", "friend", "ともだち"),
            _na("7", "hospital", "びょういん"),
            _na("8", "tomorrow", "あした"),
        )
    )
    puzzle = generate_native(payload, GenerateOptions(seed=3, candidate_count=80))
    assert puzzle.language == "native"
    assert puzzle.placed_count >= 5
    assert _shared_cells(puzzle) >= 2
    _assert_matches_grid(puzzle)


def test_japanese_engine_ignores_native_answers() -> None:
    payload = CrosswordInput(
        entries=(
            _na("1", "postpone", "えんきする"),
            _jp("2", "きのう", "yesterday"),
        )
    )
    puzzle = generate_japanese(
        payload, GenerateOptions(seed=1, candidate_count=10)
    )
    assert puzzle.placed_count == 1
    assert puzzle.entries[0].cells == ("き", "の", "う")


def test_shared_start_cell_uses_one_number() -> None:
    from anki_jp_crossword_generator.crossword.placer import WordToPlace, _assign_numbers

    numbered = _assign_numbers(
        [
            (WordToPlace("1", ("C", "A", "T"), "feline", "CAT"), 0, 0, "across"),
            (WordToPlace("2", ("C", "A", "R"), "vehicle", "CAR"), 0, 0, "down"),
        ]
    )
    assert numbered[0].number == numbered[1].number == 1


def test_numbering_is_reading_order() -> None:
    from anki_jp_crossword_generator.crossword.placer import WordToPlace, _assign_numbers

    numbered = _assign_numbers(
        [
            (WordToPlace("a", ("A", "B"), "c1", "AB"), 0, 2, "across"),
            (WordToPlace("b", ("C", "D"), "c2", "CD"), 0, 0, "down"),
        ]
    )
    by_id = {item.id: item for item in numbered}
    assert by_id["b"].number == 1
    assert by_id["a"].number == 2


def test_parallel_contact_is_rejected() -> None:
    grid = _Grid(None)
    grid.place(WordToPlace("1", ("C", "A", "T"), "c", "CAT"), 0, 0, "across")
    dog = WordToPlace("2", ("D", "O", "G"), "d", "DOG")
    slots = grid.find_slots(dog)
    assert all(
        not (slot.row == 1 and slot.direction == "across")
        for slot in slots
    )
