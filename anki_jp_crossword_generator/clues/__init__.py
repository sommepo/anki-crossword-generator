# SPDX-License-Identifier: GPL-3.0-or-later
"""Clue rendering. Independent of answer normalisation and the crossword engine."""

# Submodules are imported directly. This package init stays empty so
# ``clues.masking`` and ``vocabulary.builder`` cannot form a circular import
# when Anki loads ``session`` first.
