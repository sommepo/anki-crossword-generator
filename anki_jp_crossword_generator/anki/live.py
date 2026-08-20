# SPDX-License-Identifier: GPL-3.0-or-later
"""Live Anki collection adapter. Imported only when running inside Anki."""

from __future__ import annotations

from typing import Any, Sequence

from .errors import SearchQueryError
from .gateway import NoteSnapshot


def _format_search_error(exc: BaseException, query: str) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return (
        f"Anki could not run this search:\n\n{query}\n\n{message}\n\n"
        "Use Anki's search syntax (the same as Browse)."
    )


class LiveCollection:
    """CollectionGateway backed by an open Anki ``Collection``."""

    def __init__(self, col: Any) -> None:
        self._col = col

    def find_note_ids(self, query: str) -> list[int]:
        try:
            return [int(nid) for nid in self._col.find_notes(query)]
        except Exception as exc:  # noqa: BLE001 - wrap Anki search failures
            raise SearchQueryError(_format_search_error(exc, query)) from exc

    def find_card_ids(self, query: str) -> list[int]:
        try:
            return [int(cid) for cid in self._col.find_cards(query)]
        except Exception as exc:  # noqa: BLE001 - wrap Anki search failures
            raise SearchQueryError(_format_search_error(exc, query)) from exc

    def load_notes(self, note_ids: Sequence[int]) -> list[NoteSnapshot]:
        snapshots: list[NoteSnapshot] = []
        for note_id in note_ids:
            note = self._col.get_note(note_id)
            model = note.note_type() if hasattr(note, "note_type") else None
            note_type = ""
            if isinstance(model, dict):
                note_type = str(model.get("name") or "")
            tags = tuple(
                str(tag)
                for tag in (getattr(note, "tags", None) or [])
                if str(tag).strip()
            )
            fields = _note_fields(note)
            card_ids = _card_ids(self._col, note, int(note_id))
            deck_names = _deck_names(self._col, card_ids)
            snapshots.append(
                NoteSnapshot(
                    note_id=int(note_id),
                    note_type=note_type,
                    tags=tags,
                    fields=fields,
                    card_ids=tuple(card_ids),
                    deck_names=tuple(deck_names),
                    due_card_ids=(),
                )
            )
        return snapshots

    def list_decks(self) -> list[str]:
        try:
            entries = self._col.decks.all_names_and_ids()
            names = [str(getattr(entry, "name", "")) for entry in entries]
        except Exception:
            try:
                names = [str(deck.get("name", "")) for deck in self._col.decks.all()]
            except Exception:
                names = []
        return [name for name in names if name]

    def fields_for_deck(self, deck_name: str) -> list[str]:
        from ..vocabulary.query import deck_clause

        query = deck_clause(deck_name)
        if not query:
            return []
        try:
            note_ids = self.find_note_ids(query)
        except SearchQueryError:
            return []
        seen_models: set[int] = set()
        ordered: list[str] = []
        seen_fields: set[str] = set()
        for note_id in note_ids:
            try:
                note = self._col.get_note(note_id)
                model = note.note_type() if hasattr(note, "note_type") else None
            except Exception:
                continue
            if not isinstance(model, dict):
                continue
            model_id = int(model.get("id") or 0)
            if model_id in seen_models:
                continue
            seen_models.add(model_id)
            for fld in model.get("flds", []) or []:
                name = str((fld or {}).get("name") or "")
                if name and name not in seen_fields:
                    seen_fields.add(name)
                    ordered.append(name)
            if len(seen_models) >= 25:
                break
        return ordered

    def add_tags(self, note_ids: Sequence[int], tags: Sequence[str]) -> int:
        """Apply the supplied tags to each existing note once."""
        clean_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
        updated = 0
        for note_id in dict.fromkeys(int(nid) for nid in note_ids):
            try:
                note = self._col.get_note(note_id)
            except Exception:
                continue
            changed = False
            existing = {str(tag) for tag in (getattr(note, "tags", None) or [])}
            for tag in clean_tags:
                if tag in existing:
                    continue
                try:
                    note.add_tag(tag)
                except Exception:
                    try:
                        note.tags.append(tag)
                    except Exception:
                        continue
                existing.add(tag)
                changed = True
            if not changed:
                continue
            try:
                self._col.update_note(note)
                updated += 1
            except Exception:
                continue
        return updated


def _note_fields(note: Any) -> dict[str, str]:
    try:
        names = list(note.keys())
        return {str(name): str(note[name] if note[name] is not None else "") for name in names}
    except Exception:
        model = note.note_type() if hasattr(note, "note_type") else None
        names = []
        if isinstance(model, dict):
            names = [str(field["name"]) for field in model.get("flds", [])]
        values = list(getattr(note, "fields", []) or [])
        return {
            name: str(value if value is not None else "")
            for name, value in zip(names, values)
        }


def _card_ids(col: Any, note: Any, note_id: int) -> list[int]:
    if hasattr(col, "card_ids_of_note"):
        try:
            return [int(cid) for cid in col.card_ids_of_note(note_id)]
        except Exception:
            pass
    try:
        return [int(card.id) for card in note.cards()]
    except Exception:
        return []


def _deck_names(col: Any, card_ids: Sequence[int]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for card_id in card_ids:
        try:
            card = col.get_card(card_id)
            name = str(col.decks.name(card.did))
        except Exception:
            continue
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names
