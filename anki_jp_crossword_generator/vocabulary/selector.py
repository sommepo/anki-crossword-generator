# SPDX-License-Identifier: GPL-3.0-or-later
"""Select unique vocabulary from an Anki search without generating a grid."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from ..anki.errors import SearchQueryError
from ..anki.gateway import CollectionGateway, NoteSnapshot
from ..anki.solved import is_solved
from ..normalization.base import normalize_language
from ..normalization.headword import extract_native_headword, native_word_count
from ..settings import AddonSettings
from .builder import build_vocab_entry, mark_duplicate
from .models import SelectionResult, VocabEntry, discover_fields, resolve_field_name
from .text import strip_anki_html

SELECTED_MODE_NO_BROWSER = (
    "No notes are selected in Browse. Open Browse, select cards, then search again."
)


LOAD_BATCH = 100


@dataclass(frozen=True)
class ScanCache:
    """Notes loaded for the current query, after skipping unusable fields."""

    query: str
    selection_mode: str
    selected_note_ids: tuple[int, ...]
    matching_notes: int
    matching_cards: int
    snapshots: tuple[NoteSnapshot, ...]
    truncated: bool
    due_note_ids: frozenset[int]
    inspected_notes: int = 0
    skipped_empty: int = 0
    skipped_empty_clue: int = 0
    skipped_short: int = 0
    missing_answer_field_count: int = 0
    missing_clue_field_count: int = 0


def combine_query(base: str, extra: str) -> str:
    """AND an extra Anki search term onto a user query."""
    query = base.strip()
    extra = extra.strip()
    if not query:
        return extra
    if not extra:
        return query
    return f"({query}) {extra}"


def scan_collection(
    collection: CollectionGateway,
    settings: AddonSettings,
    *,
    selected_note_ids: Sequence[int] | None = None,
) -> ScanCache:
    """Run the Anki search, skip unusable notes, and keep eligible ones.

    ``max_notes_scanned`` caps how many *eligible* notes to keep, not how many
    matching notes to look at. Blank clues are skipped and scanning continues.
    """
    query = settings.search_query.strip()
    mode = settings.selection_mode
    selected = tuple(int(nid) for nid in (selected_note_ids or ()))

    if mode == "selected":
        if not selected:
            return ScanCache(
                query=query,
                selection_mode=mode,
                selected_note_ids=selected,
                matching_notes=0,
                matching_cards=0,
                snapshots=(),
                truncated=False,
                due_note_ids=frozenset(),
            )
        note_ids = list(selected)
        matching_notes = len(note_ids)
        matching_cards = 0
    else:
        if not query:
            raise SearchQueryError("Choose a deck first.")
        note_ids = [int(nid) for nid in collection.find_note_ids(query)]
        card_ids = [int(cid) for cid in collection.find_card_ids(query)]
        matching_notes = len(note_ids)
        matching_cards = len(card_ids)

    if mode == "due":
        note_ids = _due_first_note_ids(collection, query, note_ids)

    kept, stats = _collect_eligible_notes(collection, settings, note_ids)
    if mode == "selected":
        matching_cards = sum(len(note.card_ids) for note in kept)

    due_ids = _due_note_ids(collection, query, mode, kept)
    return ScanCache(
        query=query,
        selection_mode=mode,
        selected_note_ids=selected,
        matching_notes=matching_notes,
        matching_cards=matching_cards,
        snapshots=kept,
        truncated=stats["truncated"],
        due_note_ids=due_ids,
        inspected_notes=stats["inspected"],
        skipped_empty=stats["skipped_empty"],
        skipped_empty_clue=stats["skipped_empty_clue"],
        skipped_short=stats["skipped_short"],
        missing_answer_field_count=stats["missing_answer"],
        missing_clue_field_count=stats["missing_clue"],
    )


def _collect_eligible_notes(
    collection: CollectionGateway,
    settings: AddonSettings,
    note_ids: Sequence[int],
) -> tuple[tuple[NoteSnapshot, ...], dict[str, int | bool]]:
    """Walk matching notes, skip blanks, stop after enough eligible cards."""
    kept: list[NoteSnapshot] = []
    inspected = 0
    skipped_empty = 0
    skipped_empty_clue = 0
    skipped_short = 0
    missing_answer = 0
    missing_clue = 0
    want = max(1, settings.max_notes_scanned)

    for start in range(0, len(note_ids), LOAD_BATCH):
        batch_ids = list(note_ids[start : start + LOAD_BATCH])
        snapshots = collection.load_notes(batch_ids)
        for offset, snapshot in enumerate(snapshots):
            inspected += 1
            reason = _skip_reason(snapshot, settings)
            if reason == "missing_answer":
                missing_answer += 1
                continue
            if reason == "missing_clue":
                missing_clue += 1
                skipped_empty_clue += 1
                continue
            if reason == "empty_answer":
                skipped_empty += 1
                continue
            if reason == "empty_clue":
                skipped_empty_clue += 1
                continue
            if reason in {"too_few_words", "too_many_words"}:
                continue
            kept.append(snapshot)
            if len(kept) >= want:
                remaining = start + offset + 1 < len(note_ids)
                return tuple(kept), _eligibility_stats(
                    inspected=inspected,
                    skipped_empty=skipped_empty,
                    skipped_empty_clue=skipped_empty_clue,
                    skipped_short=skipped_short,
                    missing_answer=missing_answer,
                    missing_clue=missing_clue,
                    truncated=remaining,
                )

    return tuple(kept), _eligibility_stats(
        inspected=inspected,
        skipped_empty=skipped_empty,
        skipped_empty_clue=skipped_empty_clue,
        skipped_short=skipped_short,
        missing_answer=missing_answer,
        missing_clue=missing_clue,
        truncated=False,
    )


def _eligibility_stats(
    *,
    inspected: int,
    skipped_empty: int,
    skipped_empty_clue: int,
    skipped_short: int,
    missing_answer: int,
    missing_clue: int,
    truncated: bool,
) -> dict[str, int | bool]:
    return {
        "inspected": inspected,
        "skipped_empty": skipped_empty,
        "skipped_empty_clue": skipped_empty_clue,
        "skipped_short": skipped_short,
        "missing_answer": missing_answer,
        "missing_clue": missing_clue,
        "truncated": truncated,
    }


def _skip_reason(snapshot: NoteSnapshot, settings: AddonSettings) -> str | None:
    """Return why a note cannot be used, or None if it is eligible."""
    if not settings.include_solved and is_solved(snapshot.tags):
        return "solved"
    names = tuple(snapshot.fields)
    answer_field = resolve_field_name(settings.answer_field, names)
    clue_field = resolve_field_name(settings.clue_field, names)
    if not answer_field or answer_field not in snapshot.fields:
        return "missing_answer"
    if not clue_field or clue_field not in snapshot.fields:
        return "missing_clue"
    answer = strip_anki_html(snapshot.fields.get(answer_field, ""))
    clue = strip_anki_html(snapshot.fields.get(clue_field, ""))
    if not answer:
        return "empty_answer"
    if not clue:
        return "empty_clue"
    if (
        normalize_language(settings.answer_language) == "native"
        and settings.native_max_answer_words
    ):
        head = extract_native_headword(answer)
        words = native_word_count(head.chosen or answer)
        if words > settings.native_max_answer_words:
            return "too_many_words"
    return None


def select_from_scan(
    scan: ScanCache,
    settings: AddonSettings,
    *,
    rng: random.Random | None = None,
    seed: int | None = None,
) -> SelectionResult:
    """Filter, dedupe, and pick vocabulary from an already-loaded scan."""
    discovered = discover_fields(list(scan.snapshots))
    answer_field = resolve_field_name(settings.answer_field, discovered)
    clue_field = resolve_field_name(settings.clue_field, discovered)

    warnings: list[str] = []
    if scan.selection_mode == "selected" and not scan.selected_note_ids:
        return SelectionResult(
            query=scan.query,
            selection_mode=scan.selection_mode,
            matching_notes=0,
            matching_cards=0,
            scanned_notes=0,
            truncated=False,
            unique_valid=0,
            selected=(),
            discovered_fields=discovered,
            missing_answer_field_count=0,
            missing_clue_field_count=0,
            skipped_empty=0,
            skipped_empty_clue=0,
            skipped_short=0,
            skipped_duplicate=0,
            warnings=(SELECTED_MODE_NO_BROWSER,),
            seed=seed,
        )

    processed: list[VocabEntry] = []
    missing_answer = scan.missing_answer_field_count
    missing_clue = scan.missing_clue_field_count
    skipped_empty = scan.skipped_empty
    skipped_empty_clue = scan.skipped_empty_clue
    skipped_short = scan.skipped_short
    skipped_duplicate = 0
    seen: set[str] = set()
    mask_warnings: list[str] = []

    for snapshot in scan.snapshots:
        is_due = snapshot.note_id in scan.due_note_ids or snapshot.is_due
        entry = build_vocab_entry(
            snapshot,
            settings,
            is_due=is_due,
            discovered_fields=discovered,
        )
        if not entry.has_answer_field:
            missing_answer += 1
            processed.append(entry)
            continue
        if not entry.clue_text:
            skipped_empty_clue += 1
            continue
        if not entry.answer_text:
            skipped_empty += 1
            continue
        if entry.status == "Too short":
            skipped_short += 1
        if entry.included and entry.dedupe_key:
            if entry.dedupe_key in seen:
                skipped_duplicate += 1
                entry = mark_duplicate(entry)
            else:
                seen.add(entry.dedupe_key)
        processed.append(entry)
        for note in entry.warnings:
            if note and note not in mask_warnings:
                mask_warnings.append(note)

    valid = [entry for entry in processed if entry.included]
    excluded = [entry for entry in processed if not entry.included]
    unique_valid = len(valid)
    chosen_seed = seed
    selected = _choose_entries(valid, settings, rng=rng, seed=chosen_seed)
    preview = tuple(list(selected) + excluded)

    warnings.extend(mask_warnings)

    if scan.truncated:
        warnings.append(
            f"Stopped after collecting {len(scan.snapshots):,} eligible notes "
            f"(cap {settings.max_notes_scanned:,}). Blank clues were skipped; "
            "later matching notes were not inspected."
        )
    if missing_answer and unique_valid == 0:
        warnings.append(
            f"None of the selected cards contain valid answers in the configured "
            f"{answer_field} field."
        )
    elif missing_answer:
        warnings.append(
            f"{missing_answer} note(s) do not have the answer field "
            f"“{answer_field}”."
        )
    if missing_clue:
        warnings.append(
            f"{missing_clue} note(s) do not have the clue field “{clue_field}” "
            "and were skipped."
        )
    if skipped_empty_clue and not missing_clue and unique_valid == 0:
        warnings.append(
            f"{skipped_empty_clue} note(s) had a blank clue field and were skipped."
        )
    if unique_valid and unique_valid < settings.min_recommended_words:
        warnings.append(
            f"Only {unique_valid} eligible vocabulary entries were found. "
            f"At least {settings.min_recommended_words} are recommended "
            "for a useful crossword."
        )
    if unique_valid == 0 and not missing_answer and scan.matching_notes:
        if skipped_empty_clue:
            warnings.append(
                "No notes had both a valid answer and a non-empty clue in the "
                "configured fields."
            )
        else:
            warnings.append(
                f"None of the selected cards contain valid answers in the configured "
                f"{answer_field} field."
            )

    return SelectionResult(
        query=scan.query,
        selection_mode=scan.selection_mode,
        matching_notes=scan.matching_notes,
        matching_cards=scan.matching_cards,
        scanned_notes=scan.inspected_notes,
        truncated=scan.truncated,
        unique_valid=unique_valid,
        selected=tuple(selected),
        discovered_fields=discovered,
        missing_answer_field_count=missing_answer,
        missing_clue_field_count=missing_clue,
        skipped_empty=skipped_empty,
        skipped_empty_clue=skipped_empty_clue,
        skipped_short=skipped_short,
        skipped_duplicate=skipped_duplicate,
        warnings=tuple(warnings),
        seed=chosen_seed if settings.selection_mode == "random" else seed,
        excluded=tuple(excluded),
        preview=preview,
    )


def select_vocabulary(
    collection: CollectionGateway,
    settings: AddonSettings,
    *,
    selected_note_ids: Sequence[int] | None = None,
    rng: random.Random | None = None,
    seed: int | None = None,
) -> SelectionResult:
    """Scan the collection and return the vocabulary that would be used."""
    scan = scan_collection(
        collection, settings, selected_note_ids=selected_note_ids
    )
    return select_from_scan(scan, settings, rng=rng, seed=seed)


def _choose_entries(
    entries: list[VocabEntry],
    settings: AddonSettings,
    *,
    rng: random.Random | None,
    seed: int | None,
) -> list[VocabEntry]:
    limit = min(settings.target_word_count, len(entries))
    mode = settings.selection_mode
    if limit == 0:
        return []
    if mode == "random":
        picker = rng or random.Random(seed)
        chosen = list(entries)
        picker.shuffle(chosen)
        return chosen[:limit]
    if mode == "due":
        due = [entry for entry in entries if entry.is_due]
        rest = [entry for entry in entries if not entry.is_due]
        ordered = due + rest
        return ordered[:limit]
    return entries[:limit]


def _due_first_note_ids(
    collection: CollectionGateway,
    query: str,
    note_ids: Sequence[int],
) -> list[int]:
    """Put due notes first so Prefer due is not stuck behind blank early IDs."""
    if not query.strip() or not note_ids:
        return list(note_ids)
    try:
        due_ids = [int(nid) for nid in collection.find_note_ids(combine_query(query, "is:due"))]
    except SearchQueryError:
        return list(note_ids)
    allowed = set(note_ids)
    due_first = [nid for nid in due_ids if nid in allowed]
    due_set = set(due_first)
    rest = [nid for nid in note_ids if nid not in due_set]
    return due_first + rest


def _due_note_ids(
    collection: CollectionGateway,
    query: str,
    mode: str,
    snapshots: tuple[NoteSnapshot, ...],
) -> frozenset[int]:
    if mode not in {"due", "search", "random"}:
        return frozenset(snap.note_id for snap in snapshots if snap.is_due)
    if not query.strip():
        return frozenset(snap.note_id for snap in snapshots if snap.is_due)
    due_query = combine_query(query, "is:due")
    try:
        due_card_ids = [int(cid) for cid in collection.find_card_ids(due_query)]
    except SearchQueryError:
        return frozenset(snap.note_id for snap in snapshots if snap.is_due)
    due_cards = set(due_card_ids)
    return frozenset(
        snap.note_id
        for snap in snapshots
        if snap.is_due or any(cid in due_cards for cid in snap.card_ids)
    )
