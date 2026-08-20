# SPDX-License-Identifier: GPL-3.0-or-later
"""Anki Crossword Generator — add-on entry point.

Phase 6: generate and solve crosswords locally, export printable PDF/PNG/SVG
files, print through Qt, and retain profile-local puzzle snapshots.

Anki imports this module at startup. Tests import submodules; the aqt import
is therefore optional so pytest can run without Anki installed.
"""

from __future__ import annotations

from .version import ADDON_NAME

ADDON_MODULE = __name__
MENU_LABEL = ADDON_NAME

try:
    from aqt import gui_hooks, mw
    from aqt.qt import QAction, qconnect
    from aqt.utils import tooltip
except ImportError:  # running outside Anki (tests)
    gui_hooks = None
    mw = None
else:

    def _open_dialog() -> None:
        if mw is None or mw.col is None:
            tooltip("Open a profile first.")
            return

        from .anki.browser import selected_note_ids
        from .anki.config_store import load_settings, save_settings
        from .anki.live import LiveCollection
        from .session import CrosswordSession
        from .ui.main_dialog import MainDialog
        from .ui.windowing import (
            bring_crossword_window_to_front,
            parent_for_new_window,
            restore_anki,
        )

        # QWidget + Qt.Window. Parent to Add-ons when Config opened us so we
        # sit in front; never close Add-ons (Anki keeps it in aqt.dialogs).
        existing = getattr(mw, "_anki_crossword_dialog", None)
        if existing is not None:
            try:
                if existing.isVisible():
                    bring_crossword_window_to_front(existing)
                    return
            except Exception:
                pass

        settings = load_settings(ADDON_MODULE, mw)
        session = CrosswordSession(
            LiveCollection(mw.col),
            settings,
            selected_note_ids_fn=lambda: selected_note_ids(mw),
        )
        def _persist() -> None:
            save_settings(ADDON_MODULE, mw, session.settings)

        def _save() -> None:
            _persist()
            if getattr(mw, "_anki_crossword_dialog", None) is dialog:
                mw._anki_crossword_dialog = None
            restore_anki()

        dialog = MainDialog(
            session,
            parent=parent_for_new_window(mw),
            on_close=_save,
            on_settings_changed=_persist,
        )
        mw._anki_crossword_dialog = dialog
        bring_crossword_window_to_front(dialog)

    def _on_main_window() -> None:
        action = QAction(MENU_LABEL, mw)
        qconnect(action.triggered, _open_dialog)
        mw.form.menuTools.addAction(action)

    def _register_config() -> None:
        try:
            mw.addonManager.setConfigAction(ADDON_MODULE, _open_dialog)
        except Exception:
            pass

    gui_hooks.main_window_did_init.append(_on_main_window)
    try:
        _register_config()
    except Exception:
        pass
    gui_hooks.main_window_did_init.append(lambda: _register_config())
