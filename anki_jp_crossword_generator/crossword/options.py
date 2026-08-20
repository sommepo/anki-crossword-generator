# SPDX-License-Identifier: GPL-3.0-or-later
"""Placement options derived from add-on settings. No Anki or Qt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..settings import AddonSettings


def parse_grid_size(value: str) -> int | None:
    """Return an N×N bound, or None for auto (unbounded then crop)."""
    text = (value or "auto").strip().lower().replace("×", "x")
    if not text or text == "auto":
        return None
    if "x" in text:
        text = text.split("x", 1)[0].strip()
    try:
        size = int(text)
    except ValueError:
        return None
    if size < 5:
        return None
    return size


@dataclass(frozen=True)
class GenerateOptions:
    """Controls multi-candidate search. Deterministic when ``seed`` is fixed."""

    seed: int
    candidate_count: int = 250
    max_size: int | None = None

    @classmethod
    def from_settings(cls, settings: AddonSettings, seed: int) -> GenerateOptions:
        count = max(1, int(settings.candidate_count))
        quality = str(settings.quality or "high").strip().lower()
        if quality == "fast":
            count = min(count, 50)
        elif quality in {"medium", "normal"}:
            count = min(count, 100)
        return cls(
            seed=int(seed),
            candidate_count=count,
            max_size=parse_grid_size(str(settings.grid_size)),
        )
