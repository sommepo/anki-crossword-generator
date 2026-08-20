# SPDX-License-Identifier: GPL-3.0-or-later
"""Read currently selected notes from the Anki Browser, if it is open."""

from __future__ import annotations

from typing import Any


def selected_note_ids(mw: Any) -> list[int]:
    """Return note ids selected in an open Browser window.

    Returns an empty list when Browse is not open.
    """
    browser = _find_browser(mw)
    if browser is None:
        return []
    try:
        return [int(nid) for nid in browser.selected_notes()]
    except Exception:
        return []


def note_browser_query(note_id: int | str) -> str:
    """Anki search that shows a single note in Browse."""
    return f"nid:{int(note_id)}"


def parse_note_id(value: int | str | None) -> int | None:
    """Return a positive note id, or None if ``value`` is not one."""
    try:
        nid = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return nid if nid > 0 else None


def browse_note(note_id: int | str) -> bool:
    """Open the current profile's Browse window on ``note_id``."""
    try:
        from aqt import mw
    except Exception:
        return False
    return open_note_in_browser(mw, note_id)


def open_note_in_browser(mw: Any, note_id: int | str) -> bool:
    """Open Browse and search for ``note_id``. Returns False if that failed."""
    try:
        nid = int(note_id)
    except (TypeError, ValueError):
        return False
    if mw is None:
        return False
    try:
        from aqt import dialogs
    except Exception:
        return False
    try:
        browser = dialogs.open("Browser", mw)
    except Exception:
        return False
    if browser is None:
        return False
    query = note_browser_query(nid)
    try:
        browser.search_for(query)
    except TypeError:
        try:
            browser.search_for(query, True)
        except Exception:
            return False
    except Exception:
        return False
    _unfreeze_anki_for_browser(mw, browser)
    _raise_browser_after_crossword(browser)
    return True


def _unfreeze_anki_for_browser(mw: Any, browser: Any) -> None:
    """Crossword QDialogs must not leave mw or Browse disabled/modal."""
    try:
        from aqt.qt import QApplication, Qt
    except Exception:
        QApplication = None  # type: ignore[assignment]
        Qt = None
    if mw is not None:
        try:
            mw.setEnabled(True)
        except Exception:
            pass
    if QApplication is not None and Qt is not None:
        try:
            for widget in QApplication.topLevelWidgets():
                if not widget.property("anki_crossword_window"):
                    continue
                try:
                    widget.setModal(False)
                    widget.setWindowModality(Qt.WindowModality.NonModal)
                except Exception:
                    pass
        except Exception:
            pass
    try:
        browser.setEnabled(True)
        if hasattr(browser, "setWindowModality") and Qt is not None:
            browser.setWindowModality(Qt.WindowModality.NonModal)
        if hasattr(browser, "setModal"):
            browser.setModal(False)
        browser.raise_()
        browser.activateWindow()
        if QApplication is not None:
            QApplication.setActiveWindow(browser)
    except Exception:
        pass


def _raise_browser_after_crossword(browser: Any) -> None:
    """Bring Browse above modeless add-on windows after Anki finishes opening it."""
    try:
        from aqt.qt import QApplication, QTimer
    except Exception:
        return

    def raise_browser() -> None:
        try:
            if not browser.isVisible():
                browser.show()
            browser.raise_()
            browser.activateWindow()
            QApplication.setActiveWindow(browser)
            browser.setFocus()
        except Exception:
            pass

    # Browser applies its search and window state asynchronously. Re-raising
    # after those events preserves the crossword window's modeless behaviour.
    raise_browser()
    QTimer.singleShot(0, raise_browser)
    QTimer.singleShot(75, raise_browser)
    QTimer.singleShot(250, raise_browser)


def _find_browser(mw: Any) -> Any | None:
    try:
        from aqt.browser.browser import Browser
    except Exception:
        try:
            from aqt.browser import Browser  # type: ignore[attr-defined]
        except Exception:
            return None
    app = getattr(mw, "app", None)
    if app is None:
        return None
    for widget in app.topLevelWidgets():
        if isinstance(widget, Browser):
            return widget
    return None
