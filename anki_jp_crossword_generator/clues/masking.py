# SPDX-License-Identifier: GPL-3.0-or-later
"""Hide the target word in an example-sentence clue. No LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..vocabulary.text import strip_anki_html

BLANK = "_____"
_TAGGED = re.compile(
    r"<(b|strong|mark|em)(\s[^>]*)?>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)
_HL_WRAP = re.compile(
    r"<(span|font)(\s[^>]*?(?:background|highlight|hlite)[^>]*)>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True)
class MaskResult:
    """Clue HTML after attempting to hide the crossword answer."""

    html: str
    masked: bool
    warning: str = ""


def mask_target_in_clue(
    clue_html: str,
    *,
    answer_text: str,
    extra_targets: tuple[str, ...] = (),
) -> MaskResult:
    """Replace the answer (and close variants) with a blank.

    If no reliable match is found, the clue is returned unchanged with a warning.
    """
    if not clue_html or not strip_anki_html(clue_html):
        return MaskResult(html=clue_html, masked=False, warning="")

    visible = strip_anki_html(clue_html).strip()
    visible_key = visible.casefold()
    if visible_key == strip_anki_html(answer_text).strip().casefold():
        return MaskResult(html=clue_html, masked=False, warning="")

    extras = tuple(
        item
        for item in extra_targets
        if strip_anki_html(item).strip().casefold() != visible_key
    )
    targets = _targets(answer_text, extras)
    if not targets:
        return MaskResult(
            html=clue_html,
            masked=False,
            warning="Fill-in-the-gap clues are on, but the answer is empty.",
        )

    updated, count = _replace_wrapped(clue_html, _TAGGED, targets)
    updated, extra_count = _replace_wrapped(updated, _HL_WRAP, targets)
    count += extra_count
    updated, plain_count = _replace_plain(updated, targets)
    count += plain_count
    if count:
        leftover = strip_anki_html(updated).replace("_", "").strip()
        if not leftover:
            return MaskResult(html=clue_html, masked=False, warning="")
        return MaskResult(html=updated, masked=True)

    visible = strip_anki_html(clue_html)
    looks_like_example = " " in visible and len(visible) > max(20, len(answer_text) + 5)
    warning = ""
    if looks_like_example:
        warning = (
            "Could not find the target word in the clue; left the sentence unchanged."
        )
    return MaskResult(html=clue_html, masked=False, warning=warning)


def _targets(answer_text: str, extra: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for raw in (answer_text, *extra):
        text = strip_anki_html(raw).strip()
        if not text:
            continue
        key = text.casefold()
        if key not in seen:
            seen.add(key)
            found.append(text)
        stripped = _strip_infinitive(text)
        if stripped and stripped.casefold() not in seen:
            seen.add(stripped.casefold())
            found.append(stripped)
    found.sort(key=len, reverse=True)
    return found


def _strip_infinitive(text: str) -> str:
    lowered = text.strip()
    if lowered.casefold().startswith("to ") and len(lowered) > 3:
        rest = lowered[3:].strip()
        if rest:
            return rest
    return ""


def _replace_wrapped(
    html: str, pattern: re.Pattern[str], targets: list[str]
) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        inner = match.group(3)
        if _inner_matches(strip_anki_html(inner), targets):
            count += 1
            tag = match.group(1)
            attrs = match.group(2) or ""
            return f"<{tag}{attrs}>{BLANK}</{tag}>"
        return match.group(0)

    return pattern.sub(repl, html), count


def _inner_matches(text: str, targets: list[str]) -> bool:
    folded = text.casefold()
    for target in targets:
        needle = target.casefold()
        if folded == needle or needle in folded:
            return True
        if _stem_match(folded, needle):
            return True
    return False


def _replace_plain(html: str, targets: list[str]) -> tuple[str, int]:
    count = 0
    result = html
    for target in targets:
        pattern = re.compile(re.escape(target), re.IGNORECASE)
        result, n = pattern.subn(BLANK, result)
        count += n
        if len(target) >= 3 and target.isascii():
            result, extra = _replace_inflected(result, target)
            count += extra
    return result, count


def _replace_inflected(html: str, stem: str) -> tuple[str, int]:
    """Mask a whole word when it starts with the native-language stem."""
    count = 0
    stem_folded = stem.casefold()

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        word = match.group(0)
        if word.casefold().startswith(stem_folded) and len(word) >= len(stem):
            count += 1
            return BLANK
        return word

    return _TOKEN.sub(repl, html), count


def _stem_match(text: str, stem: str) -> bool:
    if len(stem) < 3:
        return False
    return any(token.startswith(stem) for token in _TOKEN.findall(text))
