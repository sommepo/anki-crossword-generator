# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_session_imports_when_loaded_first() -> None:
    """Anki opens the dialog by importing session before vocabulary.

    A circular clues ↔ vocabulary import only shows up in that order.
    """
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from anki_jp_crossword_generator.session import CrosswordSession",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
