# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.crossword.puzzle import PlacedEntry, Puzzle
from anki_jp_crossword_generator.crossword.solver import PlayState, normalize_guess


def _ace_cat() -> Puzzle:
    """ACE across the top row, CAT down through the C."""
    letters = (
        ("A", "C", "E"),
        (None, "A", None),
        (None, "T", None),
    )
    ace = PlacedEntry(
        id="1",
        clue="high card",
        cells=("A", "C", "E"),
        display_text="ACE",
        direction="across",
        row=0,
        col=0,
        number=1,
    )
    cat = PlacedEntry(
        id="2",
        clue="animal",
        cells=("C", "A", "T"),
        display_text="CAT",
        direction="down",
        row=0,
        col=1,
        number=2,
    )
    return Puzzle(
        rows=3,
        cols=3,
        letters=letters,
        entries=(ace, cat),
        unused=(),
        score=1.0,
        seed=1,
        language="native",
        candidate_count=1,
        elapsed_ms=1,
        requested_count=2,
    )


def _kana_cross() -> Puzzle:
    letters = (
        ("き", "の", "う"),
        (None, "き", None),
    )
    across = PlacedEntry(
        id="1",
        clue="yesterday",
        cells=("き", "の", "う"),
        display_text="きのう",
        direction="across",
        row=0,
        col=0,
        number=1,
    )
    down = PlacedEntry(
        id="2",
        clue="tree",
        cells=("の", "き"),
        display_text="のき",
        direction="down",
        row=0,
        col=1,
        number=2,
    )
    return Puzzle(
        rows=2,
        cols=3,
        letters=letters,
        entries=(across, down),
        unused=(),
        score=1.0,
        seed=1,
        language="japanese",
        candidate_count=1,
        elapsed_ms=1,
        requested_count=2,
    )


def test_normalize_native_uppercases() -> None:
    assert normalize_guess("a", "native") == "A"
    assert normalize_guess("3", "native") == "3"
    assert normalize_guess("-", "native") is None
    assert normalize_guess(" ", "native") is None


def test_normalize_japanese_keeps_kana() -> None:
    assert normalize_guess("き", "japanese") == "き"
    assert normalize_guess("ょ", "japanese") == "ょ"


def test_typing_fills_and_advances_across() -> None:
    play = PlayState(_ace_cat())
    play.select_entry(play.puzzle.across()[0])
    play.type_text("ace")
    assert play.guess_at(0, 0) == "A"
    assert play.guess_at(0, 1) == "C"
    assert play.guess_at(0, 2) == "E"
    assert play.cursor == (0, 2)


def test_backspace_clears_then_retreats() -> None:
    play = PlayState(_ace_cat())
    play.select_entry(play.puzzle.across()[0])
    play.type_text("ac")
    play.backspace()
    assert play.guess_at(0, 1) == ""
    assert play.cursor == (0, 1)
    play.backspace()
    assert play.guess_at(0, 0) == ""
    assert play.cursor == (0, 0)


def test_clicking_clue_jumps_to_first_empty() -> None:
    play = PlayState(_ace_cat())
    play.guesses[(0, 0)] = "A"
    play.select_entry(play.puzzle.across()[0])
    assert play.cursor == (0, 1)
    assert play.direction == "across"


def test_toggle_direction_at_crossing() -> None:
    play = PlayState(_ace_cat())
    play.select_cell(0, 1)
    play.direction = "across"
    play.toggle_direction()
    assert play.direction == "down"
    assert play.active_entry() is not None
    assert play.active_entry().id == "2"


def test_check_marks_wrong_and_incomplete() -> None:
    play = PlayState(_ace_cat())
    play.select_entry(play.puzzle.across()[0])
    play.type_text("axe")
    result = play.check()
    assert (0, 0) in result.correct
    assert (0, 1) in result.wrong
    assert result.solved is False

    play.clear_guesses()
    play.select_entry(play.puzzle.across()[0])
    play.type_text("ace")
    play.select_entry(play.puzzle.down()[0])
    play.type_text("at")
    assert play.check().solved is True


def test_japanese_ime_string_fills_cells() -> None:
    play = PlayState(_kana_cross())
    play.select_entry(play.puzzle.across()[0])
    play.type_text("きのう")
    assert play.guess_at(0, 0) == "き"
    assert play.guess_at(0, 1) == "の"
    assert play.guess_at(0, 2) == "う"


def test_completed_clues_count_solved_words() -> None:
    play = PlayState(_ace_cat())
    assert play.completed_clues == 0
    assert play.total_clues == 2
    play.select_entry(play.puzzle.across()[0])
    play.type_text("ace")
    assert play.completed_clues == 1
    play.reveal_all()
    assert play.completed_clues == 2


def test_reveal_and_clear() -> None:
    play = PlayState(_ace_cat())
    play.reveal_all()
    assert play.filled_cells == play.total_cells
    assert play.guess_at(2, 1) == "T"
    play.clear_guesses()
    assert play.filled_cells == 0


def test_word_check_reveal_and_clear() -> None:
    play = PlayState(_ace_cat())
    play.select_entry(play.puzzle.across()[0])
    play.type_text("AXE")
    result = play.check_word()
    assert (0, 1) in result.wrong
    assert play.guess_at(2, 1) == ""
    play.reveal_word()
    assert play.guess_at(0, 0) == "A"
    assert play.guess_at(0, 2) == "E"
    assert play.guess_at(2, 1) == ""
    play.clear_word()
    assert play.guess_at(0, 0) == ""
    assert play.guess_at(0, 1) == ""


def test_printed_clue_includes_letter_count() -> None:
    play = PlayState(_ace_cat())
    across = play.puzzle.across()[0]
    assert across.length_label == "(3)"
    assert across.printed_clue == "1. high card (3)"


def test_next_word_cycles() -> None:
    play = PlayState(_ace_cat())
    play.select_entry(play.puzzle.across()[0])
    play.next_word()
    assert play.active_entry() is not None
    assert play.active_entry().id == "2"
    play.next_word(backward=True)
    assert play.active_entry().id == "1"
