# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from datetime import date

from anki_jp_crossword_generator.anki.solved import is_solved, solved_tag
from anki_jp_crossword_generator.crossword.puzzle import PlacedEntry, Puzzle
from anki_jp_crossword_generator.session import CrosswordSession
from anki_jp_crossword_generator.settings import AddonSettings

from tests.fakes import FakeCollection, FakeNote


def _puzzle() -> Puzzle:
    entry = PlacedEntry(
        id="10",
        clue="clue",
        cells=("A", "B", "C"),
        display_text="ABC",
        direction="across",
        row=0,
        col=0,
        number=1,
    )
    return Puzzle(
        rows=1,
        cols=3,
        letters=(("A", "B", "C"),),
        entries=(entry,),
        unused=(),
        score=1.0,
        seed=1,
        language="native",
        candidate_count=1,
        elapsed_ms=1,
        requested_count=1,
    )


def test_solved_tag_is_date_sorted_and_detectable() -> None:
    tag = solved_tag(date(2026, 8, 20))
    assert tag == "anki_crossword::solved::2026-08-20"
    assert is_solved((tag,))
    assert not is_solved(("other_tag",))


def test_mark_puzzle_solved_tags_its_source_notes() -> None:
    collection = FakeCollection([FakeNote(10, "Basic", {"Answer": "abc", "Clue": "x"})])
    session = CrosswordSession(collection, AddonSettings())
    updated, tag = session.mark_puzzle_solved(_puzzle())
    assert updated == 1
    assert tag in collection.notes[10].tags
