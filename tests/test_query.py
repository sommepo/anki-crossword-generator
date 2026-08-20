# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.settings import AddonSettings
from anki_jp_crossword_generator.vocabulary.query import (
    build_search_query,
    card_state_clause,
    deck_clause,
)


def test_deck_clause_quotes_names() -> None:
    assert deck_clause("Mining") == 'deck:"Mining"'
    assert deck_clause("  ") == ""


def test_card_state_or() -> None:
    assert card_state_clause(
        include_due=True,
        include_learn=False,
        include_review=False,
        include_new=False,
    ) == "is:due"
    assert "OR" in card_state_clause(
        include_due=True,
        include_learn=True,
        include_review=True,
        include_new=False,
    )


def test_build_search_excludes_new_and_suspended_by_default() -> None:
    settings = AddonSettings(deck_name="Mining")
    query = build_search_query(settings)
    assert 'deck:"Mining"' in query
    assert "is:due" in query
    assert "is:review" in query
    assert "is:new" not in query
    assert "-is:suspended" in query


def test_build_search_can_include_new() -> None:
    settings = AddonSettings(deck_name="Mining", include_new=True)
    query = build_search_query(settings)
    assert "is:new" in query


def test_build_search_requires_nonempty_answer_and_clue_fields() -> None:
    settings = AddonSettings(
        deck_name="Mining",
        answer_field="reading",
        clue_field="englishSentence",
    )
    query = build_search_query(settings)
    assert '"reading:*"' in query
    assert '"englishSentence:*"' in query
