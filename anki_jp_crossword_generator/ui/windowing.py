# SPDX-License-Identifier: GPL-3.0-or-later
"""Modeless Anki windows that stay in front without freezing Browse.

Crossword windows are QWidgets with Qt.Window flags, not QDialogs. Never
close Anki's Add-ons manager: it stays registered in aqt.dialogs, and
done()/close() on it leaves Tools → Add-ons and Exit broken while Review
and Browse still work.

If Config is used while Add-ons is open, parent this window to that
dialog so it stacks above it.
"""

from __future__ import annotations

from typing import Any

from aqt.qt import QApplication, Qt, QTimer


def crossword_window_flags():
    """Real window chrome, not a modal dialog frame."""
    return (
        Qt.WindowType.Window
        | Qt.WindowType.WindowTitleHint
        | Qt.WindowType.WindowSystemMenuHint
        | Qt.WindowType.WindowMinMaxButtonsHint
        | Qt.WindowType.WindowCloseButtonHint
    )


def anki_window_parent(explicit: Any | None = None) -> Any | None:
    """Prefer an explicit parent; otherwise Anki's main window."""
    if explicit is not None:
        return explicit
    try:
        from aqt import mw
    except Exception:
        return None
    return mw


def parent_for_new_window(fallback: Any | None) -> Any | None:
    """Stack above Add-ons when Config opened it; otherwise use fallback."""
    addons = _find_addons_dialog()
    if addons is not None:
        return addons
    return fallback


def prepare_crossword_window(widget: Any) -> None:
    widget.setProperty("anki_crossword_window", True)
    widget.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    widget.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
    try:
        widget.setModal(False)
    except Exception:
        pass
    widget.setWindowModality(Qt.WindowModality.NonModal)


def restore_anki() -> None:
    """Keep mw enabled. Do not close or finish Anki's own dialogs."""
    _restore_anki_now()
    QTimer.singleShot(0, _restore_anki_now)


def _restore_anki_now() -> None:
    try:
        from aqt import mw
    except Exception:
        return
    if mw is None:
        return
    try:
        mw.setEnabled(True)
    except Exception:
        pass


def bring_crossword_window_to_front(widget: Any) -> None:
    """Show this window. If Add-ons is open, stack above it — never close it."""
    addons = _find_addons_dialog()
    if addons is not None and widget.parentWidget() is not addons:
        try:
            widget.setParent(addons, crossword_window_flags())
        except Exception:
            pass
    _raise_widget(widget)
    QTimer.singleShot(0, lambda: _raise_widget(widget))
    QTimer.singleShot(50, lambda: _raise_widget(widget))


def _raise_widget(widget: Any) -> None:
    try:
        if not widget.isVisible():
            widget.show()
        widget.raise_()
        widget.activateWindow()
        QApplication.setActiveWindow(widget)
    except Exception:
        pass


def _find_addons_dialog() -> Any | None:
    try:
        from aqt.addons import AddonsDialog
    except Exception:
        AddonsDialog = None
    for widget in QApplication.topLevelWidgets():
        try:
            if not widget.isVisible() or widget.property("anki_crossword_window"):
                continue
        except Exception:
            continue
        if AddonsDialog is not None and isinstance(widget, AddonsDialog):
            return widget
        if type(widget).__name__ == "AddonsDialog":
            return widget
    return None
