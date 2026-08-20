# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
from pathlib import Path

from anki_jp_crossword_generator.settings import AddonSettings


def test_shipped_config_json_loads() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "anki_jp_crossword_generator"
        / "config.json"
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    settings = AddonSettings.from_dict(raw)
    assert settings.search_query == ""
    assert settings.selection_mode == "random"
    assert settings.answer_field == ""
    assert settings.clue_field == ""
    assert settings.target_word_count == 20
    assert settings.minimum_answer_length == 3
    assert settings.answer_language == "japanese"
    assert settings.candidate_count == 250
