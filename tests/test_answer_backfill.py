from __future__ import annotations

from anki_jp_crossword_generator.answers.backfill import (
    extract_crossword_answer,
    preview_backfill,
)


def test_extracts_a_clean_answer_from_html_and_a_synonym_list() -> None:
    assert extract_crossword_answer("<b>to postpone</b>, delay; put off") == "postpone"


def test_preview_never_overwrites_existing_target_values() -> None:
    rows = preview_backfill(
        (
            {"note_id": 1, "note_type": "Mining", "fields": {"Meaning": "to repair", "Crossword Answer": ""}},
            {"note_id": 2, "note_type": "Mining", "fields": {"Meaning": "to delay", "Crossword Answer": "postpone"}},
        ),
        source_field="Meaning",
        target_field="Crossword Answer",
    )
    assert len(rows) == 1
    assert rows[0].answer == "repair"
