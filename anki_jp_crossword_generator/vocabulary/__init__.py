# SPDX-License-Identifier: GPL-3.0-or-later
"""Vocabulary selection from Anki notes."""

from .models import SelectionResult, VocabEntry, discover_fields, resolve_field_name, suggest_field
from .query import build_search_query, deck_clause
from .text import normalize_for_dedupe, strip_anki_html
from .validation import ValidationResult, validate_answer

__all__ = [
    "SelectionResult",
    "ValidationResult",
    "VocabEntry",
    "build_search_query",
    "deck_clause",
    "discover_fields",
    "normalize_for_dedupe",
    "resolve_field_name",
    "strip_anki_html",
    "suggest_field",
    "validate_answer",
]
