# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.crossword.puzzle import PlacedEntry, Puzzle
from anki_jp_crossword_generator.export.pdf import _page_plan, _pdf_clue_html, _plain_clue


def _puzzle(rows: int = 3, cols: int = 3) -> Puzzle:
    entry = PlacedEntry(
        id="1",
        clue="a plain clue",
        clue_html="a <b>bold</b> clue",
        cells=("A", "B", "C"),
        display_text="ABC",
        direction="across",
        row=0,
        col=0,
        number=1,
    )
    letters = tuple(
        tuple("A" if row == 0 and col == 0 else None for col in range(cols))
        for row in range(rows)
    )
    return Puzzle(
        rows=rows,
        cols=cols,
        letters=letters,
        entries=(entry,),
        unused=(),
        score=1.0,
        seed=1,
        language="native",
        candidate_count=1,
        elapsed_ms=1,
        requested_count=1,
    )


def test_pdf_plan_centres_a_grid_with_positive_cell_size() -> None:
    plan = _page_plan(_puzzle(), resolution=300)
    assert plan.cell > 18
    assert plan.grid_x >= plan.margin
    assert plan.grid_y > plan.margin


def test_pdf_plan_is_always_landscape_for_one_page_layout() -> None:
    assert _page_plan(_puzzle(rows=5, cols=12), resolution=300).landscape
    assert _page_plan(_puzzle(rows=12, cols=5), resolution=300).landscape


def test_pdf_clues_are_plain_and_safe_for_qpainter() -> None:
    assert _plain_clue(_puzzle().entries[0]) == "a bold clue"


def test_pdf_clues_preserve_marked_words_as_bold_underlining() -> None:
    clue = _pdf_clue_html(_puzzle().entries[0])
    assert "bold" in clue
    assert "underline" in clue
