# SPDX-License-Identifier: GPL-3.0-or-later
"""Build Anki search strings from the selection controls. No Anki import."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..settings import AddonSettings


def quote_search_value(value: str) -> str:
    """Quote a value for Anki's search syntax."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def deck_clause(deck_name: str) -> str:
    """Return ``deck:"Name"`` or an empty string."""
    name = deck_name.strip()
    if not name:
        return ""
    return f"deck:{quote_search_value(name)}"


def nonempty_field_clause(field_name: str) -> str:
    """Match notes whose field is non-empty, using Anki's ``Field:*`` syntax."""
    name = field_name.strip()
    if not name:
        return ""
    return quote_search_value(f"{name}:*")


def card_state_clause(
    *,
    include_due: bool,
    include_learn: bool,
    include_review: bool,
    include_new: bool,
) -> str:
    """OR together the selected Anki card queues."""
    terms: list[str] = []
    if include_due:
        terms.append("is:due")
    if include_learn:
        terms.append("is:learn")
    if include_review:
        terms.append("is:review")
    if include_new:
        terms.append("is:new")
    if not terms:
        return ""
    if len(terms) == 1:
        return terms[0]
    return "(" + " OR ".join(terms) + ")"


def build_search_query(settings: AddonSettings) -> str:
    """Compile deck + extra filter + card-state checkboxes into one Anki search."""
    parts: list[str] = []
    deck = deck_clause(settings.deck_name)
    if deck:
        parts.append(deck)
    extra = settings.extra_query.strip()
    if extra:
        parts.append(f"({extra})" if any(ch.isspace() for ch in extra) else extra)
    states = card_state_clause(
        include_due=settings.include_due,
        include_learn=settings.include_learn,
        include_review=settings.include_review,
        include_new=settings.include_new,
    )
    if states:
        parts.append(states)
    if not settings.include_suspended:
        parts.append("-is:suspended")
    answer = nonempty_field_clause(settings.answer_field)
    clue = nonempty_field_clause(settings.clue_field)
    if answer:
        parts.append(answer)
    if clue:
        parts.append(clue)
    return " ".join(parts)


def has_card_state_filter(settings: AddonSettings) -> bool:
    return any(
        (
            settings.include_due,
            settings.include_learn,
            settings.include_review,
            settings.include_new,
        )
    )
