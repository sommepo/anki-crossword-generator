# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.vocabulary.text import (
    anki_html_for_preview,
    normalize_for_dedupe,
    strip_anki_html,
    truncate,
)


def test_strips_html_and_sound() -> None:
    raw = '<div>to <b>postpone</b></div>[sound:foo.mp3]'
    assert strip_anki_html(raw) == "to postpone"


def test_preserves_japanese() -> None:
    assert strip_anki_html("<span>えんきする</span>") == "えんきする"


def test_scripts_are_removed() -> None:
    raw = 'hello<script>alert(1)</script> world'
    assert strip_anki_html(raw) == "hello world"


def test_dedupe_uses_nfc() -> None:
    composed = "が"
    decomposed = "か\u3099"
    assert normalize_for_dedupe(composed) == normalize_for_dedupe(decomposed)


def test_truncate() -> None:
    assert truncate("abcdef", 4) == "abc…"
    assert truncate("short", 10) == "short"


def test_preview_html_keeps_bold_and_highlight() -> None:
    raw = 'The <b>meeting</b> was <span style="background-color: yellow;">postponed</span>.'
    html = anki_html_for_preview(raw, mark_color="theme", mark_text="auto")
    compact = html.replace(" ", "").lower()
    assert "<b" in html
    assert "meeting" in html
    assert "background-color:#ffe082" in compact
    assert "color:#1a1a1a" in compact
    assert strip_anki_html(raw) == "The meeting was postponed."


def test_preview_html_maps_mark_to_a_highlight_span() -> None:
    html = anki_html_for_preview(
        "the <mark>target</mark> word", mark_color="theme", mark_text="auto"
    )
    assert "<mark" not in html.lower()
    assert "#ffe082" in html
    assert "target" in html


def test_preview_html_converts_anki_rgb_highlights() -> None:
    raw = '<span style="background-color: rgb(255, 255, 0);">word</span>'
    html = anki_html_for_preview(raw, mark_color="theme", mark_text="auto")
    compact = html.replace(" ", "").lower()
    assert "background-color:#ffe082" in compact
    assert "rgb(" not in html.lower()


def test_dark_preview_uses_dusty_gold_not_neon_yellow() -> None:
    raw = '<span style="background-color: rgb(255, 255, 0);">word</span>'
    html = anki_html_for_preview(raw, dark=True, mark_color="theme", mark_text="auto")
    compact = html.replace(" ", "").lower()
    assert "background-color:#bfa14a" in compact
    assert "color:#1a1408" in compact
    assert "#ffff00" not in compact


def test_dark_preview_maps_anki_pale_yellow() -> None:
    raw = '<span style="background-color: rgb(255, 255, 127);">word</span>'
    html = anki_html_for_preview(raw, dark=True, mark_color="theme", mark_text="auto")
    assert "#bfa14a" in html.replace(" ", "").lower()


def test_preview_paints_bold_as_highlight() -> None:
    html = anki_html_for_preview(
        "the <b>word</b>", dark=True, mark_color="theme", mark_text="auto"
    )
    compact = html.replace(" ", "").lower()
    assert "<b" in compact
    assert "background-color:#bfa14a" in compact
    assert "word" in html


def test_preview_defaults_to_red_text_on_black() -> None:
    html = anki_html_for_preview("the <mark>養子</mark> word", dark=True)
    compact = html.replace(" ", "").lower()
    assert "background-color:#000000" in compact
    assert "color:#ff2d2d" in compact
    assert "養子" in html


def test_preview_mark_text_can_override_colour() -> None:
    raw = '<span style="background-color: yellow;">word</span>'
    html = anki_html_for_preview(raw, dark=True, mark_color="black", mark_text="white")
    compact = html.replace(" ", "").lower()
    assert "background-color:#000000" in compact
    assert "color:#f5f5f5" in compact


def test_preview_mark_color_green() -> None:
    raw = '<span style="background-color: yellow;">word</span>'
    html = anki_html_for_preview(
        raw, dark=True, mark_color="green", mark_text="auto"
    )
    compact = html.replace(" ", "").lower()
    assert "#6a9e73" in compact
    assert "#bfa14a" not in compact


def test_preview_html_paints_highlight_classes() -> None:
    raw = '<span class="highlighted">word</span>'
    html = anki_html_for_preview(raw, mark_color="theme", mark_text="auto")
    assert "background-color:#ffe082" in html.replace(" ", "")


def test_preview_html_strips_script_and_sound() -> None:
    raw = 'hello<script>alert(1)</script>[sound:foo.mp3] <b>world</b>'
    html = anki_html_for_preview(raw)
    assert "script" not in html.lower()
    assert "sound" not in html.lower()
    assert "<b" in html
    assert "world" in html
