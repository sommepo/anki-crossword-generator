# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a VocabEntry from an Anki note using the configured fields."""

from __future__ import annotations

from dataclasses import replace

from ..anki.gateway import NoteSnapshot
from ..clues.masking import mask_target_in_clue
from ..clues.templates import effective_clue_template, render_clue_template
from ..normalization import get_normalizer, normalize_language
from ..normalization.base import NormalizedAnswer
from ..normalization.headword import extract_native_headword
from ..settings import AddonSettings
from ..vocabulary.models import VocabEntry, resolve_field_name
from ..vocabulary.text import strip_anki_html
from ..vocabulary.validation import duplicate_result, validate_answer

_READING_HINTS = ("reading", "Reading", "kana", "Kana")
_EXPRESSION_HINTS = (
    "Expression",
    "expression",
    "wordDictionaryForm",
    "Word",
    "word",
)
_GLOSS_HINTS = (
    "Meaning",
    "meaning",
    "definition",
    "englishWord",
    "Gloss",
    "English",
)


def build_vocab_entry(
    snapshot: NoteSnapshot,
    settings: AddonSettings,
    *,
    is_due: bool,
    discovered_fields: tuple[str, ...],
) -> VocabEntry:
    """Map one note to a vocabulary entry. Answer language is a setting."""
    names = tuple(snapshot.fields) or discovered_fields
    answer_field = resolve_field_name(settings.answer_field, names)
    clue_field = resolve_field_name(settings.clue_field, names)
    has_answer = bool(answer_field) and answer_field in snapshot.fields
    has_clue = bool(clue_field) and clue_field in snapshot.fields
    answer_raw = snapshot.fields.get(answer_field, "") if has_answer else ""
    answer_text = strip_anki_html(answer_raw)
    language = normalize_language(settings.answer_language)
    normalizer = get_normalizer(
        language,
        drop_apostrophes=settings.native_drop_apostrophes,
    )
    normalized = normalizer.normalize(answer_text) if answer_text else _empty_answer(
        answer_text, language
    )

    clue_raw, clue_text, mask_warning = _render_clue(
        snapshot.fields,
        settings,
        clue_field=clue_field,
        has_clue=has_clue,
        answer_text=answer_text,
    )
    warnings = (mask_warning,) if mask_warning else ()

    source_reading = _lookup(snapshot.fields, _READING_HINTS)
    source_expression = _lookup(snapshot.fields, _EXPRESSION_HINTS)

    validation = validate_answer(
        normalized,
        minimum_cells=settings.minimum_answer_length,
        maximum_cells=settings.maximum_answer_cells,
        has_answer_field=has_answer,
        minimum_native_words=(
            settings.native_min_answer_words if language == "native" else 0
        ),
        maximum_native_words=(
            settings.native_max_answer_words if language == "native" else 0
        ),
    )
    dedupe_key = normalized.normalized if normalized.cells else ""

    return VocabEntry(
        note_id=snapshot.note_id,
        card_ids=snapshot.card_ids,
        note_type=snapshot.note_type,
        decks=snapshot.deck_names,
        tags=snapshot.tags,
        fields=dict(snapshot.fields),
        answer_field=answer_field,
        clue_field=clue_field,
        answer_raw=answer_raw,
        answer_text=answer_text,
        clue_raw=clue_raw,
        clue_text=clue_text,
        has_answer_field=has_answer,
        has_clue_field=has_clue,
        is_due=is_due,
        dedupe_key=dedupe_key,
        answer_language=language,
        normalized=normalized,
        included=validation.ok,
        status=validation.status,
        status_reason=validation.message,
        source_expression=source_expression,
        source_reading=source_reading,
        cell_count=normalized.cell_count,
        warnings=warnings,
    )


def mark_duplicate(entry: VocabEntry) -> VocabEntry:
    """Return a copy flagged as a crossword duplicate."""
    result = duplicate_result()
    return replace(
        entry,
        included=False,
        status=result.status,
        status_reason=result.message,
    )


def _empty_answer(original: str, language: str) -> NormalizedAnswer:
    return NormalizedAnswer(
        original=original,
        normalized="",
        cells=(),
        language=language,
        display_text=original.strip(),
    )


def _render_clue(
    fields: dict[str, str],
    settings: AddonSettings,
    *,
    clue_field: str,
    has_clue: bool,
    answer_text: str,
) -> tuple[str, str, str]:
    template = effective_clue_template(settings.clue_template, clue_field)
    if template:
        clue_raw = render_clue_template(template, fields)
    elif has_clue:
        clue_raw = fields.get(clue_field, "")
    else:
        clue_raw = ""
    if not strip_anki_html(clue_raw) and has_clue:
        clue_raw = fields.get(clue_field, "")

    warning = ""
    if settings.hide_target_in_example and clue_raw:
        extra = tuple(
            value
            for value in (
                _lookup(fields, _READING_HINTS),
                _lookup(fields, _EXPRESSION_HINTS),
                _lookup(fields, _GLOSS_HINTS),
            )
            if value
        )
        if normalize_language(settings.answer_language) != "japanese":
            extra = extra + extract_native_headword(answer_text).mask_targets
        masked = mask_target_in_clue(
            clue_raw,
            answer_text=answer_text,
            extra_targets=extra,
        )
        clue_raw = masked.html
        warning = masked.warning
    return clue_raw, strip_anki_html(clue_raw), warning


def _lookup(fields: dict[str, str], hints: tuple[str, ...]) -> str | None:
    names = tuple(fields)
    for hint in hints:
        resolved = resolve_field_name(hint, names)
        if resolved in fields:
            text = strip_anki_html(fields[resolved])
            if text:
                return text
    return None
