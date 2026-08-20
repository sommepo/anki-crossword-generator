# SPDX-License-Identifier: GPL-3.0-or-later
"""Crossword-engine errors. Independent of Anki and Qt."""


class GenerationError(Exception):
    """The engine could not produce a usable puzzle from this vocabulary."""
