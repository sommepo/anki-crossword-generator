# SPDX-License-Identifier: GPL-3.0-or-later
"""Crossword-suitability checks. Length is in cells, not a language rule."""

from __future__ import annotations

from dataclasses import dataclass

from ..normalization.base import NormalizedAnswer
from ..normalization.headword import native_word_count

STATUS_VALID = "Valid"
STATUS_EMPTY = "Empty answer"
STATUS_SHORT = "Too short"
STATUS_LONG = "Too long"
STATUS_UNSUPPORTED = "Unsupported characters"
STATUS_DUPLICATE = "Duplicate"
STATUS_INVALID_FIELD = "Invalid field"
STATUS_WORD_COUNT = "Word count"


@dataclass(frozen=True)
class ValidationResult:
    """Why a normalised answer can or cannot be placed on a grid."""

    ok: bool
    code: str
    message: str

    @property
    def status(self) -> str:
        labels = {
            "valid": STATUS_VALID,
            "empty": STATUS_EMPTY,
            "too_short": STATUS_SHORT,
            "too_long": STATUS_LONG,
            "unsupported": STATUS_UNSUPPORTED,
            "duplicate": STATUS_DUPLICATE,
            "invalid_field": STATUS_INVALID_FIELD,
            "word_count": STATUS_WORD_COUNT,
        }
        return labels.get(self.code, self.message or self.code)


def validate_answer(
    answer: NormalizedAnswer | None,
    *,
    minimum_cells: int,
    maximum_cells: int,
    has_answer_field: bool = True,
    minimum_native_words: int = 0,
    maximum_native_words: int = 0,
) -> ValidationResult:
    """Check a single normalised answer. Dedup is applied separately."""
    if not has_answer_field:
        return ValidationResult(
            ok=False,
            code="invalid_field",
            message="The configured answer field is missing on this note.",
        )
    if answer is None:
        return ValidationResult(ok=False, code="empty", message="The answer is empty.")
    if answer.unsupported_characters:
        shown = " ".join(answer.unsupported_characters[:6])
        return ValidationResult(
            ok=False,
            code="unsupported",
            message=f"Unsupported characters for crossword cells: {shown}",
        )
    if not answer.cells:
        return ValidationResult(ok=False, code="empty", message="The answer is empty.")
    if len(answer.cells) < minimum_cells:
        return ValidationResult(
            ok=False,
            code="too_short",
            message=(
                f"Need at least {minimum_cells} cells; this answer has "
                f"{len(answer.cells)}."
            ),
        )
    if len(answer.cells) > maximum_cells:
        return ValidationResult(
            ok=False,
            code="too_long",
            message=(
                f"At most {maximum_cells} cells are allowed; this answer has "
                f"{len(answer.cells)}."
            ),
        )
    if answer.language == "native" and minimum_native_words:
        words = native_word_count(answer.display_text)
        if words < minimum_native_words:
            needed = (
                "1 word" if minimum_native_words == 1 else f"{minimum_native_words} words"
            )
            return ValidationResult(
                ok=False,
                code="word_count",
                message=f"Need at least {needed}; this Native answer has {words}.",
            )
    if answer.language == "native" and maximum_native_words:
        words = native_word_count(answer.display_text)
        if words > maximum_native_words:
            allowed = (
                "1 word" if maximum_native_words == 1 else f"{maximum_native_words} words"
            )
            return ValidationResult(
                ok=False,
                code="word_count",
                message=f"At most {allowed}; this Native answer has {words}.",
            )
    return ValidationResult(ok=True, code="valid", message="")


def duplicate_result() -> ValidationResult:
    return ValidationResult(
        ok=False,
        code="duplicate",
        message="Another note already uses this crossword answer.",
    )
