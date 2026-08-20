# SPDX-License-Identifier: GPL-3.0-or-later
"""In-memory Anki collection used by tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from anki_jp_crossword_generator.anki.errors import SearchQueryError
from anki_jp_crossword_generator.anki.gateway import NoteSnapshot


@dataclass
class FakeNote:
    note_id: int
    note_type: str
    fields: dict[str, str]
    tags: tuple[str, ...] = ()
    card_ids: tuple[int, ...] = field(default_factory=tuple)
    deck_names: tuple[str, ...] = ("Japanese",)
    due_card_ids: tuple[int, ...] = ()
    is_new: bool = False
    is_learn: bool = False

    def __post_init__(self) -> None:
        if not self.card_ids:
            self.card_ids = (self.note_id * 10,)

    def snapshot(self) -> NoteSnapshot:
        return NoteSnapshot(
            note_id=self.note_id,
            note_type=self.note_type,
            tags=self.tags,
            fields=dict(self.fields),
            card_ids=self.card_ids,
            deck_names=self.deck_names,
            due_card_ids=self.due_card_ids,
        )


class FakeCollection:
    """Small subset of Anki search syntax for tests."""

    def __init__(self, notes: list[FakeNote]) -> None:
        self.notes = {note.note_id: note for note in notes}

    def find_note_ids(self, query: str) -> list[int]:
        self._reject_invalid(query)
        return [
            note.note_id
            for note in self.notes.values()
            if _note_matches(note, query)
        ]

    def find_card_ids(self, query: str) -> list[int]:
        self._reject_invalid(query)
        ids: list[int] = []
        for note in self.notes.values():
            if not _note_matches(note, query, ignore_queue=True):
                continue
            if _due_only(query):
                ids.extend(note.due_card_ids)
            else:
                ids.extend(note.card_ids)
        return ids

    def load_notes(self, note_ids: list[int] | tuple[int, ...]) -> list[NoteSnapshot]:
        snapshots: list[NoteSnapshot] = []
        for note_id in note_ids:
            note = self.notes.get(int(note_id))
            if note is not None:
                snapshots.append(note.snapshot())
        return snapshots

    def list_decks(self) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for note in self.notes.values():
            for name in note.deck_names:
                if name not in seen:
                    seen.add(name)
                    names.append(name)
        return names

    def fields_for_deck(self, deck_name: str) -> list[str]:
        wanted = deck_name.strip().casefold()
        ordered: list[str] = []
        seen: set[str] = set()
        for note in self.notes.values():
            if not any(wanted in name.casefold() for name in note.deck_names):
                continue
            for field_name in note.fields:
                if field_name not in seen:
                    seen.add(field_name)
                    ordered.append(field_name)
        return ordered

    def add_tags(self, note_ids: list[int] | tuple[int, ...], tags: list[str] | tuple[str, ...]) -> int:
        updated = 0
        for note_id in dict.fromkeys(int(nid) for nid in note_ids):
            note = self.notes.get(note_id)
            if note is None:
                continue
            merged = tuple(dict.fromkeys((*note.tags, *(str(tag) for tag in tags))))
            if merged != note.tags:
                note.tags = merged
                updated += 1
        return updated

    def _reject_invalid(self, query: str) -> None:
        if "INVALID" in query.upper().split():
            raise SearchQueryError(f"Anki could not run this search:\n\n{query}")


QUEUE_TOKENS = {"is:due", "is:learn", "is:review", "is:new"}


def _field_wildcard(token: str) -> str | None:
    raw = token.strip().strip('"')
    if raw.endswith(":*") and len(raw) > 2:
        return raw[:-2]
    return None


def _tokens(query: str) -> list[str]:
    cleaned = query.replace("(", " ").replace(")", " ")
    return [part for part in cleaned.split() if part]


def _due_only(query: str) -> bool:
    tokens = {part.lower() for part in _tokens(query)}
    queues = tokens & QUEUE_TOKENS
    return queues == {"is:due"}


def _note_matches(note: FakeNote, query: str, *, ignore_queue: bool = False) -> bool:
    tokens = _tokens(query)
    queue_tokens = [part.lower() for part in tokens if part.lower() in QUEUE_TOKENS]
    others = [
        part
        for part in tokens
        if part.lower() not in QUEUE_TOKENS and part.lower() != "or"
    ]
    for token in others:
        lowered = token.lower()
        field_name = _field_wildcard(token)
        if field_name is not None:
            # Anki's Field:* matches any stored value, including HTML-only
            # blanks such as "<br>". Visible emptiness is handled later.
            if field_name not in note.fields or note.fields[field_name] == "":
                return False
            continue
        if lowered == "-is:suspended":
            continue
        if lowered.startswith("deck:"):
            wanted = token.split(":", 1)[1].strip('"')
            if not any(wanted.lower() in name.lower() for name in note.deck_names):
                return False
            continue
        if lowered.startswith("tag:"):
            wanted = token.split(":", 1)[1].lstrip(":").strip('"')
            if not any(wanted.lower() == tag.lower() for tag in note.tags):
                return False
            continue
        if lowered.startswith("nid:"):
            if str(note.note_id) != token.split(":", 1)[1]:
                return False
            continue
        if lowered.startswith(("is:", "prop:", "rated:", "-is:")):
            continue
    if queue_tokens and not ignore_queue:
        if not any(_has_queue_state(note, token) for token in queue_tokens):
            return False
    return True


def _has_queue_state(note: FakeNote, token: str) -> bool:
    if token == "is:due":
        return bool(note.due_card_ids)
    if token == "is:new":
        return bool(note.is_new)
    if token == "is:learn":
        return bool(note.is_learn)
    if token == "is:review":
        return not note.is_new
    return False


def sample_notes(count: int = 12, *, due: bool = False) -> list[FakeNote]:
    """Build a Japanese-like vocab set for tests (not real study data)."""
    readings = [
        "えんきする",
        "ちょうさする",
        "さける",
        "べんきょうする",
        "がっこう",
        "せんせい",
        "ともだち",
        "でんしゃ",
        "びょういん",
        "こうえん",
        "あした",
        "きのう",
        "たべる",
        "のむ",
        "はなす",
    ]
    meanings = [
        "to postpone",
        "to investigate",
        "to avoid",
        "to study",
        "school",
        "teacher",
        "friend",
        "train",
        "hospital",
        "park",
        "tomorrow",
        "yesterday",
        "to eat",
        "to drink",
        "to speak",
    ]
    notes: list[FakeNote] = []
    for index in range(count):
        reading = readings[index % len(readings)]
        meaning = meanings[index % len(meanings)]
        note_id = 1000 + index
        due_cards = (note_id * 10,) if due and index < max(1, count // 3) else ()
        notes.append(
            FakeNote(
                note_id=note_id,
                note_type="Japanese Vocab",
                fields={
                    "Expression": reading,
                    "Reading": reading,
                    "Meaning": meaning,
                    "Example": f"Example for {meaning}.",
                },
                tags=("N2",),
                card_ids=(note_id * 10, note_id * 10 + 1),
                due_card_ids=due_cards,
            )
        )
    return notes
