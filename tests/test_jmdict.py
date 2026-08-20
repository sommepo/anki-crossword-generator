from __future__ import annotations

from anki_jp_crossword_generator.answers.jmdict import JmdictIndex


def test_uses_reading_to_choose_the_right_dictionary_entry(tmp_path) -> None:
    path = tmp_path / "jmdict-eng-test.json"
    path.write_text(
        '{"words":[{"kanji":[{"text":"上げる"}],"kana":[{"text":"あげる"}],"sense":[{"gloss":[{"lang":"eng","text":"to raise"}]}]},{"kanji":[{"text":"上げる"}],"kana":[{"text":"あがる"}],"sense":[{"gloss":[{"lang":"eng","text":"to rise"}]}]}]}',
        encoding="utf-8",
    )
    index = JmdictIndex()
    index.load_json_file(path)
    assert index.lookup_glosses("上げる", "あがる") == "to rise"
