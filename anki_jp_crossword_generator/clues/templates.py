# SPDX-License-Identifier: GPL-3.0-or-later
"""Field templates for crossword clues. Independent of answer normalisation."""

from __future__ import annotations

import re

from ..vocabulary.models import resolve_field_name

PLACEHOLDER_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def effective_clue_template(template: str, clue_field: str) -> str:
    """Use ``{{clue_field}}`` when the stored template is empty."""
    text = template.strip()
    if text:
        return text
    name = clue_field.strip()
    if not name:
        return ""
    return "{{" + name + "}}"


def render_clue_template(template: str, fields: dict[str, str]) -> str:
    """Replace ``{{Field}}`` placeholders with the note's field HTML.

    Unknown placeholders become empty strings. Matching is case-insensitive.
    """
    names = tuple(fields)

    def replace(match: re.Match[str]) -> str:
        requested = match.group(1).strip()
        resolved = resolve_field_name(requested, names)
        if resolved in fields:
            return fields[resolved]
        return ""

    return PLACEHOLDER_RE.sub(replace, template)


def template_uses_only_field(template: str, field_name: str) -> bool:
    """True when the template is empty or exactly ``{{field_name}}``."""
    text = template.strip()
    if not text:
        return True
    name = field_name.strip()
    if not name:
        return False
    return text == "{{" + name + "}}"
