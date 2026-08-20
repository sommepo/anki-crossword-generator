# SPDX-License-Identifier: GPL-3.0-or-later
"""Errors raised by the Anki collection gateway."""

from __future__ import annotations


class CrosswordError(Exception):
    """Base class for user-facing add-on errors."""


class SearchQueryError(CrosswordError):
    """The Anki search expression could not be executed."""


class CollectionUnavailableError(CrosswordError):
    """No open Anki collection / profile is available."""
