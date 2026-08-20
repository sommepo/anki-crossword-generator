# SPDX-License-Identifier: GPL-3.0-or-later
"""Profile-local, immutable snapshots of generated crosswords."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .crossword.puzzle import PlacedEntry, Puzzle


@dataclass(frozen=True)
class HistoryRecord:
    """One saved crossword and the information needed to reopen it."""

    id: str
    created_at: str
    title: str
    puzzle: Puzzle


def history_path(mw: Any) -> Path:
    """Return a profile-specific history location outside the add-on package."""
    profile_folder = Path(mw.pm.profileFolder())
    return profile_folder / "anki_crossword_generator" / "puzzle-history.json"


def load_history(path: Path) -> list[HistoryRecord]:
    """Load valid snapshots, newest first; corrupt records are ignored."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    records: list[HistoryRecord] = []
    for item in payload if isinstance(payload, list) else []:
        try:
            records.append(_record_from_dict(item))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(records, key=lambda item: item.created_at, reverse=True)


def save_history_record(path: Path, puzzle: Puzzle, *, title: str) -> HistoryRecord:
    """Append a snapshot and retain the most recent 100 puzzles."""
    record = HistoryRecord(
        id=uuid4().hex,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        title=title,
        puzzle=puzzle,
    )
    records = [record, *load_history(path)][:100]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([_record_to_dict(item) for item in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return record


def delete_history_record(path: Path, record_id: str) -> None:
    """Delete one stored snapshot; a missing record is harmless."""
    records = [item for item in load_history(path) if item.id != record_id]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([_record_to_dict(item) for item in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _record_to_dict(record: HistoryRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "created_at": record.created_at,
        "title": record.title,
        "puzzle": _puzzle_to_dict(record.puzzle),
    }


def _record_from_dict(value: dict[str, Any]) -> HistoryRecord:
    return HistoryRecord(
        id=str(value["id"]),
        created_at=str(value["created_at"]),
        title=str(value.get("title") or "Anki Crossword"),
        puzzle=_puzzle_from_dict(value["puzzle"]),
    )


def _puzzle_to_dict(puzzle: Puzzle) -> dict[str, Any]:
    return {
        "rows": puzzle.rows,
        "cols": puzzle.cols,
        "letters": [list(row) for row in puzzle.letters],
        "entries": [
            {
                "id": entry.id,
                "clue": entry.clue,
                "cells": list(entry.cells),
                "display_text": entry.display_text,
                "direction": entry.direction,
                "row": entry.row,
                "col": entry.col,
                "number": entry.number,
                "clue_html": entry.clue_html,
            }
            for entry in puzzle.entries
        ],
        "score": puzzle.score,
        "seed": puzzle.seed,
        "language": puzzle.language,
        "candidate_count": puzzle.candidate_count,
        "elapsed_ms": puzzle.elapsed_ms,
        "requested_count": puzzle.requested_count,
    }


def _puzzle_from_dict(value: dict[str, Any]) -> Puzzle:
    entries = tuple(
        PlacedEntry(
            id=str(entry["id"]),
            clue=str(entry.get("clue") or ""),
            cells=tuple(str(cell) for cell in entry["cells"]),
            display_text=str(entry.get("display_text") or ""),
            direction=str(entry["direction"]),
            row=int(entry["row"]),
            col=int(entry["col"]),
            number=int(entry["number"]),
            clue_html=str(entry.get("clue_html") or ""),
        )
        for entry in value["entries"]
    )
    return Puzzle(
        rows=int(value["rows"]),
        cols=int(value["cols"]),
        letters=tuple(tuple(cell for cell in row) for row in value["letters"]),
        entries=entries,
        unused=(),
        score=float(value.get("score") or 0),
        seed=int(value.get("seed") or 0),
        language=str(value.get("language") or "japanese"),
        candidate_count=int(value.get("candidate_count") or 0),
        elapsed_ms=int(value.get("elapsed_ms") or 0),
        requested_count=int(value.get("requested_count") or len(entries)),
    )
