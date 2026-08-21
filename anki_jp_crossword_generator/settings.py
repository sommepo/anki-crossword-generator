# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent add-on settings. This module does not import Anki or Qt."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Mapping

CLUE_MARK_STYLES = ("highlight", "highlight_bold", "bold", "underline")
CLUE_MARK_STYLE_LABELS = {
    "highlight": "Highlight",
    "highlight_bold": "Highlight and bold",
    "bold": "Bold",
    "underline": "Underline",
}
CLUE_MARK_COLORS = ("black", "gold", "green", "pink", "blue", "theme")
CLUE_MARK_COLOR_LABELS = {
    "black": "Black",
    "gold": "Gold",
    "green": "Green",
    "pink": "Pink",
    "blue": "Blue",
    "theme": "Match window",
}
CLUE_MARK_TEXT_COLORS = ("red", "white", "black", "gold", "auto")
CLUE_MARK_TEXT_LABELS = {
    "red": "Red",
    "white": "White",
    "black": "Black",
    "gold": "Gold",
    "auto": "Auto",
}
SELECTION_MODES = ("search", "random", "due", "selected")
ANSWER_LANGUAGES = ("japanese", "native", "other")
ANSWER_LANGUAGE_LABELS = {
    "japanese": "Japanese",
    "native": "Native",
    "other": "Other / Custom",
}

ANSWER_FIELD_HINTS = (
    "reading",
    "Reading",
    "wordDictionaryForm",
    "Expression",
    "Word",
)
NATIVE_ANSWER_FIELD_HINTS = (
    "englishWord",
    "Word",
    "word",
    "Meaning",
    "meaning",
    "definition",
    "English",
)
CLUE_FIELD_HINTS = (
    "definition",
    "Meaning",
    "meaning",
    "englishSentence",
    "englishWord",
    "Gloss",
    "English",
)
NATIVE_CLUE_FIELD_HINTS = (
    "reading",
    "Reading",
    "Expression",
    "expression",
    "wordDictionaryForm",
)

_GLOSS_FIELD_KEYS = frozenset(
    {"meaning", "definition", "englishsentence", "english", "gloss"}
)
_NATIVE_HEADWORD_FIELD_KEYS = frozenset({"englishword", "word"})
_JAPANESE_HEADWORD_FIELD_KEYS = frozenset(
    {"reading", "expression", "worddictionaryform", "kana"}
)


def answer_field_hints_for(language: str) -> tuple[str, ...]:
    """Headword field first for Native; reading/expression first for Japanese."""
    if (language or "").strip().lower() in {"native", "other", "english"}:
        return NATIVE_ANSWER_FIELD_HINTS
    return ANSWER_FIELD_HINTS


def preferred_answer_field_current(language: str, current: str) -> str:
    """Drop a mismatched field role so hints can pick the right headword field."""
    name = current.strip().casefold()
    lang = (language or "").strip().lower()
    if lang in {"native", "other", "english"} and name in _GLOSS_FIELD_KEYS:
        return ""
    if lang in {"", "japanese"} and name in _NATIVE_HEADWORD_FIELD_KEYS:
        return ""
    return current

DEFAULTS: dict[str, Any] = {
    "deck_name": "",
    "extra_query": "",
    "search_query": "",
    "selection_mode": "random",
    "include_due": True,
    "include_learn": True,
    "include_review": True,
    "include_new": False,
    "include_suspended": False,
    "include_solved": False,
    "target_word_count": 20,
    "minimum_answer_length": 3,
    "min_recommended_words": 8,
    "answer_field": "",
    "clue_field": "",
    "answer_language": "japanese",
    "hide_target_in_example": False,
    "clue_template": "",
    "japanese_answer_field": "",
    "japanese_clue_field": "",
    "japanese_clue_template": "",
    "japanese_hide_target": False,
    "native_answer_field": "",
    "native_clue_field": "",
    "native_clue_template": "",
    "native_hide_target": False,
    "native_max_answer_words": 0,
    "puzzle_scale": 80,
    "generation_output": "interactive",
    "show_excluded_preview": False,
    "clue_mark_style": "highlight",
    "clue_mark_color": "black",
    "clue_mark_text": "red",
    "native_drop_apostrophes": True,
    "maximum_answer_cells": 22,
    "candidate_count": 250,
    "random_seed": None,
    "last_seed": None,
    "last_generation_seed": None,
    "grid_size": "auto",
    "quality": "high",
    "paper_size": "A4",
    "orientation": "auto",
    "puzzle_title": "Japanese Vocabulary Crossword",
    "include_metadata": True,
    "max_notes_scanned": 500,
}


def _as_int(value: Any, fallback: int, *, minimum: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = fallback
    if minimum is not None:
        number = max(minimum, number)
    return number


def _as_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _as_choice(value: Any, allowed: tuple[str, ...], fallback: str) -> str:
    key = _as_str(value, fallback).strip().lower()
    if key in allowed:
        return key
    return fallback


def _as_bool(value: Any, fallback: bool) -> bool:
    if value is None:
        return fallback
    return bool(value)


def _coerce_answer_language(value: Any) -> str:
    key = _as_str(value, "japanese").strip().lower()
    if key == "english":
        return "native"
    if key in ANSWER_LANGUAGES:
        return key
    return "japanese"


@dataclass
class AddonSettings:
    """User-facing configuration. Unknown keys are preserved for later phases."""

    deck_name: str = ""
    extra_query: str = ""
    search_query: str = ""
    selection_mode: str = "random"
    include_due: bool = True
    include_learn: bool = True
    include_review: bool = True
    include_new: bool = False
    include_suspended: bool = False
    include_solved: bool = False
    target_word_count: int = 20
    minimum_answer_length: int = 3
    min_recommended_words: int = 8
    answer_field: str = ""
    clue_field: str = ""
    answer_language: str = "japanese"
    hide_target_in_example: bool = False
    clue_template: str = ""
    japanese_answer_field: str = ""
    japanese_clue_field: str = ""
    japanese_clue_template: str = ""
    japanese_hide_target: bool = False
    native_answer_field: str = ""
    native_clue_field: str = ""
    native_clue_template: str = ""
    native_hide_target: bool = False
    # Retained solely to read settings saved by earlier development builds.
    native_min_answer_words: int = 0
    native_max_answer_words: int = 0
    puzzle_scale: int = 80
    generation_output: str = "interactive"
    show_excluded_preview: bool = False
    clue_mark_style: str = "highlight"
    clue_mark_color: str = "black"
    clue_mark_text: str = "red"
    native_drop_apostrophes: bool = True
    maximum_answer_cells: int = 22
    candidate_count: int = 250
    random_seed: int | None = None
    last_seed: int | None = None
    last_generation_seed: int | None = None
    grid_size: str = "auto"
    quality: str = "high"
    paper_size: str = "A4"
    orientation: str = "auto"
    puzzle_title: str = "Japanese Vocabulary Crossword"
    include_metadata: bool = True
    max_notes_scanned: int = 500
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for Anki's add-on config store."""
        data = asdict(self)
        extra = data.pop("extra", {}) or {}
        merged = dict(extra)
        merged.update(data)
        return merged

    def apply_active_profile(self) -> None:
        """Copy the Japanese or Native profile into the working search fields."""
        if self.answer_language == "native":
            self.answer_field = self.native_answer_field
            self.clue_field = self.native_clue_field
            self.clue_template = self.native_clue_template
            self.hide_target_in_example = self.native_hide_target
            return
        self.answer_field = self.japanese_answer_field
        self.clue_field = self.japanese_clue_field
        self.clue_template = self.japanese_clue_template
        self.hide_target_in_example = self.japanese_hide_target

    def write_active_profile(self) -> None:
        """Copy working search fields back into the active language profile."""
        if self.answer_language == "native":
            self.native_answer_field = self.answer_field
            self.native_clue_field = self.clue_field
            self.native_clue_template = self.clue_template
            self.native_hide_target = self.hide_target_in_example
            return
        self.japanese_answer_field = self.answer_field
        self.japanese_clue_field = self.clue_field
        self.japanese_clue_template = self.clue_template
        self.japanese_hide_target = self.hide_target_in_example

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> AddonSettings:
        """Load settings, filling defaults for missing keys."""
        raw = dict(DEFAULTS)
        extra: dict[str, Any] = {}
        known = {item.name for item in fields(cls)} - {"extra"}
        if data:
            for key, value in data.items():
                if key in known:
                    raw[key] = value
                else:
                    extra[key] = value

        mode = str(raw.get("selection_mode") or "random").strip().lower()
        if mode not in SELECTION_MODES:
            mode = "random"

        deck_name = _as_str(raw.get("deck_name"), "").strip()
        extra_query = _as_str(raw.get("extra_query"), "").strip()
        search_query = _as_str(raw.get("search_query"), "").strip()
        if not deck_name and not extra_query and search_query:
            deck_name, extra_query = _split_legacy_search(search_query)

        language = _coerce_answer_language(raw.get("answer_language"))
        answer_field = _as_str(raw.get("answer_field"), "").strip()
        clue_field = _as_str(raw.get("clue_field"), "").strip()
        clue_template = _as_str(raw.get("clue_template"), "")
        # Fill-in-the-gap clues are temporarily unavailable in the UI.  Ignore
        # old enabled settings so reopening the add-on restores normal clues.
        hide_target = False
        japanese_answer = _as_str(raw.get("japanese_answer_field"), "").strip()
        native_answer = _as_str(raw.get("native_answer_field"), "").strip()
        japanese_clue = _as_str(raw.get("japanese_clue_field"), "").strip()
        native_clue = _as_str(raw.get("native_clue_field"), "").strip()
        japanese_template = _as_str(raw.get("japanese_clue_template"), "")
        native_template = _as_str(raw.get("native_clue_template"), "")
        if "japanese_hide_target" in raw:
            japanese_hide = False
        else:
            japanese_hide = False
        if "native_hide_target" in raw:
            native_hide = False
        else:
            native_hide = False
        # Earlier builds accidentally described this control as a minimum. Treat
        # its saved value as the intended maximum when upgrading existing users.
        legacy_native_min_words = min(
            3, _as_int(raw.get("native_min_answer_words"), 0, minimum=0)
        )
        if data and "native_max_answer_words" in data:
            native_max_words = min(
                3, _as_int(raw.get("native_max_answer_words"), 0, minimum=0)
            )
        else:
            native_max_words = legacy_native_min_words
        puzzle_scale = min(125, max(50, _as_int(raw.get("puzzle_scale"), 80)))
        generation_output = _as_choice(
            raw.get("generation_output"), ("interactive", "pdf_preview"), "interactive"
        )
        if not japanese_answer and language != "native":
            japanese_answer = answer_field
        if not native_answer and language == "native":
            native_answer = answer_field
        if not japanese_clue and language != "native":
            japanese_clue = clue_field
        if not native_clue and language == "native":
            native_clue = clue_field
        if not japanese_template and language != "native":
            japanese_template = clue_template
        if not native_template and language == "native":
            native_template = clue_template
        if language == "native":
            answer_field = native_answer or answer_field
            clue_field = native_clue or clue_field
            clue_template = native_template
            hide_target = native_hide
        else:
            answer_field = japanese_answer or answer_field
            clue_field = japanese_clue or clue_field
            clue_template = japanese_template
            hide_target = japanese_hide

        mark_style = _as_choice(
            raw.get("clue_mark_style"), CLUE_MARK_STYLES, "highlight"
        )
        incoming = data or {}
        if "clue_mark_text" not in incoming and str(
            incoming.get("clue_mark_color") or "theme"
        ).strip().lower() in {"", "theme"}:
            mark_color = "black"
            mark_text = "red"
        else:
            mark_color = _as_choice(
                raw.get("clue_mark_color"), CLUE_MARK_COLORS, "black"
            )
            mark_text = _as_choice(
                raw.get("clue_mark_text"), CLUE_MARK_TEXT_COLORS, "red"
            )

        return cls(
            deck_name=deck_name,
            extra_query=extra_query,
            search_query=search_query,
            selection_mode=mode,
            include_due=_as_bool(raw.get("include_due"), True),
            include_learn=_as_bool(raw.get("include_learn"), True),
            include_review=_as_bool(raw.get("include_review"), True),
            include_new=_as_bool(raw.get("include_new"), False),
            include_suspended=_as_bool(raw.get("include_suspended"), False),
            include_solved=_as_bool(raw.get("include_solved"), False),
            target_word_count=_as_int(raw.get("target_word_count"), 20, minimum=1),
            minimum_answer_length=_as_int(
                raw.get("minimum_answer_length"), 3, minimum=1
            ),
            min_recommended_words=_as_int(
                raw.get("min_recommended_words"), 8, minimum=1
            ),
            answer_field=answer_field,
            clue_field=clue_field,
            answer_language=language,
            hide_target_in_example=hide_target,
            clue_template=clue_template,
            japanese_answer_field=japanese_answer,
            japanese_clue_field=japanese_clue,
            japanese_clue_template=japanese_template,
            japanese_hide_target=japanese_hide,
            native_answer_field=native_answer,
            native_clue_field=native_clue,
            native_clue_template=native_template,
            native_hide_target=native_hide,
            native_min_answer_words=0,
            native_max_answer_words=native_max_words,
            puzzle_scale=puzzle_scale,
            generation_output=generation_output,
            show_excluded_preview=_as_bool(raw.get("show_excluded_preview"), False),
            clue_mark_style=mark_style,
            clue_mark_color=mark_color,
            clue_mark_text=mark_text,
            native_drop_apostrophes=_as_bool(raw.get("native_drop_apostrophes"), True),
            maximum_answer_cells=_as_int(
                raw.get("maximum_answer_cells"), 22, minimum=3
            ),
            candidate_count=_as_int(raw.get("candidate_count"), 250, minimum=1),
            random_seed=_as_optional_int(raw.get("random_seed")),
            last_seed=_as_optional_int(raw.get("last_seed")),
            last_generation_seed=_as_optional_int(raw.get("last_generation_seed")),
            grid_size=_as_str(raw.get("grid_size"), "auto"),
            quality=_as_str(raw.get("quality"), "high"),
            paper_size=_as_str(raw.get("paper_size"), "A4"),
            orientation=_as_str(raw.get("orientation"), "auto"),
            puzzle_title=_as_str(
                raw.get("puzzle_title"), "Japanese Vocabulary Crossword"
            ),
            include_metadata=_as_bool(raw.get("include_metadata"), True),
            max_notes_scanned=_as_int(raw.get("max_notes_scanned"), 500, minimum=1),
            extra=extra,
        )


def _split_legacy_search(query: str) -> tuple[str, str]:
    """Pull a leading ``deck:`` token out of an old free-text search.

    The previous default ``deck:Japanese`` is discarded so the deck dropdown
    starts blank rather than pointing at a deck the user may not have.
    """
    text = query.strip()
    if not text:
        return "", ""
    token, rest = _first_token(text)
    if not token.lower().startswith("deck:"):
        return "", text
    deck = token[5:].strip().strip('"')
    leftover = rest.strip()
    if deck.casefold() == "japanese" and not leftover:
        return "", ""
    return deck, leftover


def _first_token(text: str) -> tuple[str, str]:
    if text[:1] == '"':
        end = text.find('"', 1)
        if end < 0:
            return text, ""
        return text[: end + 1], text[end + 1 :]
    for index, char in enumerate(text):
        if char.isspace():
            return text[:index], text[index:]
    return text, ""
