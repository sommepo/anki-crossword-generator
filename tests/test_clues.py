# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.clues.templates import render_clue_template
from anki_jp_crossword_generator.clues.masking import mask_target_in_clue
from anki_jp_crossword_generator.vocabulary.text import strip_anki_html


FIELDS = {
    "Meaning": "to postpone",
    "Expression": "延期する",
    "Example": "The meeting was postponed until next week.",
    "Reading": "えんきする",
}


def test_single_field_template() -> None:
    assert render_clue_template("{{Meaning}}", FIELDS) == "to postpone"
    assert render_clue_template("{{Expression}}", FIELDS) == "延期する"


def test_stacked_template() -> None:
    rendered = render_clue_template("{{Meaning}}\n\n{{Example}}", FIELDS)
    assert "to postpone" in rendered
    assert "The meeting was postponed" in rendered


def test_joined_template() -> None:
    assert (
        render_clue_template("{{Expression}} — {{Meaning}}", FIELDS)
        == "延期する — to postpone"
    )


def test_unknown_placeholder_is_empty() -> None:
    assert render_clue_template("{{Missing}}", FIELDS) == ""


def test_case_insensitive_field_names() -> None:
    assert render_clue_template("{{meaning}}", FIELDS) == "to postpone"


def test_mask_postponed_in_example() -> None:
    result = mask_target_in_clue(
        "The meeting was postponed until next week.",
        answer_text="to postpone",
    )
    assert result.masked is True
    assert "_____" in result.html
    assert "postponed" not in result.html.lower()


def test_mask_html_bold() -> None:
    result = mask_target_in_clue(
        "The meeting was <b>postponed</b> until next week.",
        answer_text="to postpone",
    )
    assert result.masked is True
    assert "<b>" in result.html or "<b " in result.html
    assert "_____" in result.html
    assert "postponed" not in strip_anki_html(result.html).lower()


def test_mask_keeps_highlight_span() -> None:
    result = mask_target_in_clue(
        'The meeting was <span style="background-color: yellow;">postponed</span>.',
        answer_text="to postpone",
    )
    assert result.masked is True
    assert "background-color" in result.html
    assert "_____" in result.html


def test_mask_does_not_wipe_a_definition_clue() -> None:
    result = mask_target_in_clue("to postpone", answer_text="to postpone")
    assert result.masked is False
    assert result.html == "to postpone"


def test_mask_warns_when_example_has_no_target() -> None:
    result = mask_target_in_clue(
        "The meeting was delayed until next week.",
        answer_text="えんきする",
    )
    assert result.masked is False
    assert result.warning
    assert result.html == "The meeting was delayed until next week."
