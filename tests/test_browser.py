# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from anki_jp_crossword_generator.anki.browser import (
    browse_note,
    note_browser_query,
    open_note_in_browser,
    parse_note_id,
)


def test_note_browser_query() -> None:
    assert note_browser_query(1000) == "nid:1000"
    assert note_browser_query("42") == "nid:42"


def test_parse_note_id() -> None:
    assert parse_note_id(1000) == 1000
    assert parse_note_id("42") == 42
    assert parse_note_id("0") is None
    assert parse_note_id("") is None
    assert parse_note_id(None) is None
    assert parse_note_id("nid:1000") is None


def test_open_note_in_browser_without_anki_returns_false() -> None:
    assert open_note_in_browser(None, 1000) is False
    assert open_note_in_browser(object(), "nope") is False
    assert browse_note("nope") is False
