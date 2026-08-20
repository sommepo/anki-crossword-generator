# SPDX-License-Identifier: GPL-3.0-or-later
"""Application service: search, preview, normalisation, and crossword generation.

This module has no Qt dependency.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import Optional

from .anki.errors import SearchQueryError
from .anki.gateway import CollectionGateway
from .anki.solved import solved_tag
from .clues.templates import template_uses_only_field
from .crossword.errors import GenerationError
from .crossword.japanese import generate_japanese
from .crossword.models import CrosswordEntry, CrosswordInput
from .crossword.native import generate_native
from .crossword.options import GenerateOptions
from .crossword.puzzle import Puzzle
from .normalization.base import normalize_language
from .settings import (
    ANSWER_FIELD_HINTS,
    CLUE_FIELD_HINTS,
    NATIVE_ANSWER_FIELD_HINTS,
    NATIVE_CLUE_FIELD_HINTS,
    SELECTION_MODES,
    AddonSettings,
    preferred_answer_field_current,
)
from .vocabulary.models import SelectionResult, suggest_field
from .vocabulary.query import build_search_query, has_card_state_filter
from .vocabulary.selector import ScanCache, scan_collection, select_from_scan

SelectedIdsFn = Callable[[], Sequence[int]]


class CrosswordSession:
    """Coordinates settings, collection search, and preview state."""

    def __init__(
        self,
        collection: CollectionGateway,
        settings: AddonSettings,
        *,
        selected_note_ids_fn: Optional[SelectedIdsFn] = None,
    ) -> None:
        self.collection = collection
        self.settings = settings
        self._selected_note_ids_fn = selected_note_ids_fn or (lambda: [])
        self.last_result: SelectionResult | None = None
        self.last_puzzle: Puzzle | None = None
        self._scan: ScanCache | None = None

    def selected_note_ids(self) -> list[int]:
        try:
            return [int(nid) for nid in self._selected_note_ids_fn()]
        except Exception:
            return []

    def list_decks(self) -> list[str]:
        try:
            return [str(name) for name in self.collection.list_decks() if str(name)]
        except Exception:
            return []

    def fields_for_current_deck(self) -> tuple[str, ...]:
        deck = self.settings.deck_name.strip()
        if not deck:
            return ()
        try:
            return tuple(self.collection.fields_for_deck(deck))
        except Exception:
            return ()

    def apply_field_suggestions(self, discovered: tuple[str, ...]) -> tuple[str, str]:
        """Fill Japanese and Native profiles from the selected deck."""
        settings = self.settings
        ja_answer = suggest_field(
            discovered,
            ANSWER_FIELD_HINTS,
            preferred_answer_field_current("japanese", settings.japanese_answer_field),
        )
        ja_clue = suggest_field(
            discovered, CLUE_FIELD_HINTS, settings.japanese_clue_field
        )
        na_answer = suggest_field(
            discovered,
            NATIVE_ANSWER_FIELD_HINTS,
            preferred_answer_field_current("native", settings.native_answer_field),
        )
        na_clue = suggest_field(
            discovered, NATIVE_CLUE_FIELD_HINTS, settings.native_clue_field
        )
        if ja_answer:
            settings.japanese_answer_field = ja_answer
        if ja_clue:
            settings.japanese_clue_field = ja_clue
            if not settings.japanese_clue_template.strip():
                settings.japanese_clue_template = "{{" + ja_clue + "}}"
        if na_answer:
            settings.native_answer_field = na_answer
        if na_clue:
            settings.native_clue_field = na_clue
            if not settings.native_clue_template.strip():
                settings.native_clue_template = "{{" + na_clue + "}}"
        settings.apply_active_profile()
        return settings.japanese_answer_field, settings.japanese_clue_field

    def activate_profile(self, language: str) -> None:
        """Switch the working search fields to the Japanese or Native profile."""
        key = normalize_language(language)
        if key == "other":
            key = "native"
        if key != self.settings.answer_language:
            self._scan = None
        self.settings.answer_language = key
        before = (
            self.settings.answer_field,
            self.settings.clue_field,
            self.settings.clue_template,
            self.settings.hide_target_in_example,
        )
        self.settings.apply_active_profile()
        after = (
            self.settings.answer_field,
            self.settings.clue_field,
            self.settings.clue_template,
            self.settings.hide_target_in_example,
        )
        if before != after:
            self._scan = None

    def search(self, *, force_reload: bool = True, language: str | None = None) -> SelectionResult:
        """Run the current Anki search and rebuild the preview."""
        if language:
            self.activate_profile(language)
        else:
            self.settings.apply_active_profile()
        self._prepare_query()
        selected_ids = (
            self.selected_note_ids()
            if self.settings.selection_mode == "selected"
            else []
        )
        if force_reload or self._scan is None or not self._scan_matches(selected_ids):
            self._scan = scan_collection(
                self.collection,
                self.settings,
                selected_note_ids=selected_ids,
            )
        seed = self._seed_for_selection()
        rng = random.Random(seed) if seed is not None else None
        self.last_result = select_from_scan(
            self._scan, self.settings, rng=rng, seed=seed
        )
        if self.settings.selection_mode == "random" and seed is not None:
            self.settings.last_seed = seed
        return self.last_result

    def refresh_preview(self) -> SelectionResult:
        """Re-apply field/length/count settings without hitting Anki again."""
        return self.search(force_reload=False)

    def can_generate(self) -> bool:
        """True when enough unique valid answers exist to justify a puzzle."""
        result = self.last_result
        if result is None or result.error:
            return False
        return result.unique_valid >= self.settings.min_recommended_words

    def generate_blocked_reason(self) -> str | None:
        """Explain why Generate is disabled, or None if it may be clicked."""
        if self.last_result is None:
            return "Preview vocabulary first."
        if self.last_result.unique_valid == 0:
            answer = self.settings.answer_field or "answer"
            clue = self.settings.clue_field or "clue"
            return (
                f"No eligible vocabulary was found. Notes need a non-empty "
                f"{answer} field and a non-empty {clue} field."
            )
        if self.last_result.unique_valid < self.settings.min_recommended_words:
            return (
                f"Only {self.last_result.unique_valid} eligible vocabulary "
                f"entries were found. At least "
                f"{self.settings.min_recommended_words} are recommended "
                "for a useful crossword."
            )
        return None

    def generate(self, language: str, *, progress=None, new_seed: bool = True) -> Puzzle:
        """Place the current preview vocabulary on a crossword grid."""
        self.activate_profile(language)
        blocked = self.generate_blocked_reason()
        if blocked:
            raise GenerationError(blocked)
        payload = self.to_crossword_input()
        if not payload.entries:
            raise GenerationError("No eligible vocabulary was found to place.")
        if new_seed or self.settings.last_generation_seed is None:
            seed = self.new_generation_seed()
        else:
            seed = int(self.settings.last_generation_seed)
        options = GenerateOptions.from_settings(self.settings, seed)
        key = normalize_language(language)
        if key == "japanese":
            puzzle = generate_japanese(payload, options, progress=progress)
        else:
            puzzle = generate_native(payload, options, progress=progress)
        if puzzle.placed_count == 0:
            raise GenerationError(
                "No satisfactory crossword could be generated from this vocabulary "
                "set. Try increasing the word pool or lowering the minimum answer "
                "length."
            )
        self.last_puzzle = puzzle
        return puzzle

    def mark_puzzle_solved(self, puzzle: Puzzle | None = None) -> tuple[int, str]:
        """Tag every source note in a placed puzzle with today's solved tag."""
        completed = puzzle or self.last_puzzle
        if completed is None:
            return 0, solved_tag()
        note_ids: list[int] = []
        for entry in completed.entries:
            try:
                note_ids.append(int(entry.id))
            except (TypeError, ValueError):
                continue
        tag = solved_tag()
        updated = self.collection.add_tags(note_ids, (tag,))
        self._scan = None
        self.last_result = None
        return updated, tag

    def new_generation_seed(self) -> int:
        seed = random.randrange(1, 1_000_000_000)
        self.settings.last_generation_seed = seed
        return seed

    def to_crossword_input(self) -> CrosswordInput:
        """Language-neutral payload for the future generator. No Anki types."""
        result = self.last_result
        if result is None:
            return CrosswordInput()
        entries: list[CrosswordEntry] = []
        for entry in result.selected:
            if not entry.included or entry.normalized is None:
                continue
            if not entry.normalized.cells:
                continue
            entries.append(
                CrosswordEntry(
                    id=str(entry.note_id),
                    answer=entry.normalized,
                    clue=entry.clue_text,
                    clue_html=entry.clue_raw,
                    metadata={
                        "display_text": entry.normalized.display_text,
                        "language": entry.answer_language,
                    },
                )
            )
        return CrosswordInput(entries=tuple(entries))

    def set_deck_name(self, name: str) -> None:
        if name != self.settings.deck_name:
            self._scan = None
        self.settings.deck_name = name.strip()

    def set_extra_query(self, query: str) -> None:
        if query.strip() != self.settings.extra_query:
            self._scan = None
        self.settings.extra_query = query.strip()

    def set_card_state(
        self,
        *,
        include_due: bool | None = None,
        include_learn: bool | None = None,
        include_review: bool | None = None,
        include_new: bool | None = None,
        include_suspended: bool | None = None,
        include_solved: bool | None = None,
    ) -> None:
        changed = False
        mapping = (
            ("include_due", include_due),
            ("include_learn", include_learn),
            ("include_review", include_review),
            ("include_new", include_new),
            ("include_suspended", include_suspended),
            ("include_solved", include_solved),
        )
        for attr, value in mapping:
            if value is None:
                continue
            if getattr(self.settings, attr) != value:
                setattr(self.settings, attr, value)
                changed = True
        if changed:
            self._scan = None

    def set_selection_mode(self, mode: str) -> None:
        normalized = mode.strip().lower()
        if normalized not in SELECTION_MODES:
            raise ValueError(f"Unknown selection mode: {mode}")
        if normalized != self.settings.selection_mode:
            self.settings.selection_mode = normalized
            self._scan = None

    def set_answer_field(self, name: str) -> None:
        cleaned = name.strip()
        if cleaned != self.settings.answer_field:
            self._scan = None
        self.settings.answer_field = cleaned
        self.settings.write_active_profile()

    def set_answer_language(self, language: str) -> None:
        self.activate_profile(language)

    def set_clue_field(self, name: str) -> None:
        cleaned = name.strip()
        previous = self.settings.clue_field
        if cleaned != previous:
            self._scan = None
            if template_uses_only_field(self.settings.clue_template, previous):
                self.settings.clue_template = "{{" + cleaned + "}}" if cleaned else ""
        self.settings.clue_field = cleaned
        self.settings.write_active_profile()

    def set_clue_template(self, template: str) -> None:
        self.settings.clue_template = template
        self.settings.write_active_profile()

    def set_hide_target_in_example(self, enabled: bool) -> None:
        self.settings.hide_target_in_example = bool(enabled)
        self.settings.write_active_profile()

    def set_clue_mark_style(self, style: str) -> None:
        from .settings import CLUE_MARK_STYLES

        key = (style or "").strip().lower()
        self.settings.clue_mark_style = key if key in CLUE_MARK_STYLES else "highlight"

    def set_clue_mark_color(self, color: str) -> None:
        from .settings import CLUE_MARK_COLORS

        key = (color or "").strip().lower()
        self.settings.clue_mark_color = key if key in CLUE_MARK_COLORS else "black"

    def set_clue_mark_text(self, color: str) -> None:
        from .settings import CLUE_MARK_TEXT_COLORS

        key = (color or "").strip().lower()
        self.settings.clue_mark_text = key if key in CLUE_MARK_TEXT_COLORS else "red"

    def set_profile_answer_field(self, language: str, name: str) -> None:
        cleaned = name.strip()
        if normalize_language(language) == "native":
            if cleaned != self.settings.native_answer_field:
                if self.settings.answer_language == "native":
                    self._scan = None
            self.settings.native_answer_field = cleaned
        else:
            if cleaned != self.settings.japanese_answer_field:
                if self.settings.answer_language != "native":
                    self._scan = None
            self.settings.japanese_answer_field = cleaned
        if normalize_language(language) == self.settings.answer_language:
            self.settings.apply_active_profile()

    def set_profile_clue_field(self, language: str, name: str) -> None:
        cleaned = name.strip()
        if normalize_language(language) == "native":
            previous = self.settings.native_clue_field
            if cleaned != previous and template_uses_only_field(
                self.settings.native_clue_template, previous
            ):
                self.settings.native_clue_template = "{{" + cleaned + "}}" if cleaned else ""
            if cleaned != previous and self.settings.answer_language == "native":
                self._scan = None
            self.settings.native_clue_field = cleaned
        else:
            previous = self.settings.japanese_clue_field
            if cleaned != previous and template_uses_only_field(
                self.settings.japanese_clue_template, previous
            ):
                self.settings.japanese_clue_template = (
                    "{{" + cleaned + "}}" if cleaned else ""
                )
            if cleaned != previous and self.settings.answer_language != "native":
                self._scan = None
            self.settings.japanese_clue_field = cleaned
        if normalize_language(language) == self.settings.answer_language:
            self.settings.apply_active_profile()

    def set_profile_clue_template(self, language: str, template: str) -> None:
        if normalize_language(language) == "native":
            self.settings.native_clue_template = template
        else:
            self.settings.japanese_clue_template = template
        if normalize_language(language) == self.settings.answer_language:
            self.settings.apply_active_profile()

    def set_profile_hide_target(self, language: str, enabled: bool) -> None:
        if normalize_language(language) == "native":
            self.settings.native_hide_target = bool(enabled)
        else:
            self.settings.japanese_hide_target = bool(enabled)
        if normalize_language(language) == self.settings.answer_language:
            self.settings.apply_active_profile()

    def set_native_max_answer_words(self, count: int) -> None:
        cleaned = max(0, min(3, int(count)))
        if cleaned != self.settings.native_max_answer_words:
            self._scan = None
        self.settings.native_max_answer_words = cleaned

    def set_native_drop_apostrophes(self, enabled: bool) -> None:
        self.settings.native_drop_apostrophes = bool(enabled)

    def set_target_word_count(self, count: int) -> None:
        self.settings.target_word_count = max(1, int(count))

    def set_minimum_answer_length(self, length: int) -> None:
        cleaned = max(1, int(length))
        if cleaned != self.settings.minimum_answer_length:
            self._scan = None
        self.settings.minimum_answer_length = cleaned

    def new_random_seed(self) -> int:
        seed = random.randrange(1, 1_000_000_000)
        self.settings.random_seed = seed
        self.settings.last_seed = seed
        return seed

    def _prepare_query(self) -> None:
        if self.settings.selection_mode == "selected":
            return
        if not self.settings.deck_name.strip() and not self.settings.extra_query.strip():
            raise SearchQueryError("Choose a deck first.")
        if not has_card_state_filter(self.settings):
            raise SearchQueryError(
                "Tick at least one card state (due, learning, review, or new)."
            )
        self.settings.search_query = build_search_query(self.settings)

    def _scan_matches(self, selected_ids: Sequence[int]) -> bool:
        if self._scan is None:
            return False
        return (
            self._scan.query == self.settings.search_query.strip()
            and self._scan.selection_mode == self.settings.selection_mode
            and self._scan.selected_note_ids == tuple(int(n) for n in selected_ids)
        )

    def _seed_for_selection(self) -> int | None:
        if self.settings.selection_mode != "random":
            return None
        if self.settings.random_seed is not None:
            return int(self.settings.random_seed)
        if self.settings.last_seed is not None:
            return int(self.settings.last_seed)
        return self.new_random_seed()
