# SPDX-License-Identifier: GPL-3.0-or-later
"""Load and save add-on settings through Anki's config mechanism."""

from __future__ import annotations

from typing import Any

from ..settings import AddonSettings


def load_settings(addon_module: str, mw: Any) -> AddonSettings:
    """Read persisted config, or defaults if none is stored."""
    manager = getattr(mw, "addonManager", None)
    if manager is None:
        return AddonSettings()
    raw = manager.getConfig(addon_module)
    return AddonSettings.from_dict(raw if isinstance(raw, dict) else None)


def save_settings(addon_module: str, mw: Any, settings: AddonSettings) -> None:
    """Write the current settings back to Anki."""
    manager = getattr(mw, "addonManager", None)
    if manager is None:
        return
    manager.writeConfig(addon_module, settings.to_dict())
