from anki_jp_crossword_generator.crossword.puzzle import PlacedEntry, Puzzle
from anki_jp_crossword_generator.history import (
    delete_history_record,
    load_history,
    save_history_record,
)


def _puzzle() -> Puzzle:
    return Puzzle(
        rows=1,
        cols=3,
        letters=(("C", "A", "T"),),
        entries=(
            PlacedEntry(
                id="1",
                clue="A pet",
                cells=("C", "A", "T"),
                display_text="cat",
                direction="across",
                row=0,
                col=0,
                number=1,
                clue_html="<b>A</b> pet",
            ),
        ),
        unused=(),
        score=12.5,
        seed=42,
        language="native",
        candidate_count=250,
        elapsed_ms=10,
        requested_count=1,
    )


def test_history_round_trips_an_immutable_puzzle_snapshot(tmp_path) -> None:
    path = tmp_path / "puzzle-history.json"
    saved = save_history_record(path, _puzzle(), title="Anki Crossword")

    records = load_history(path)

    assert len(records) == 1
    assert records[0].id == saved.id
    assert records[0].puzzle.letters == (("C", "A", "T"),)
    assert records[0].puzzle.entries[0].clue_html == "<b>A</b> pet"


def test_history_can_remove_a_snapshot(tmp_path) -> None:
    path = tmp_path / "puzzle-history.json"
    saved = save_history_record(path, _puzzle(), title="Anki Crossword")

    delete_history_record(path, saved.id)

    assert load_history(path) == []
