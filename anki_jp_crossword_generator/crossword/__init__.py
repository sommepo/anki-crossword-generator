# SPDX-License-Identifier: GPL-3.0-or-later
"""Crossword engines. Japanese and Native placement are separate entry points.

The shared placer operates on opaque cell tokens. It does not branch on
language. Engines filter CrosswordInput and choose scoring weights.
"""

from .errors import GenerationError
from .japanese import generate_japanese
from .models import CrosswordEntry, CrosswordInput
from .native import generate_native
from .options import GenerateOptions, parse_grid_size
from .puzzle import PlacedEntry, Puzzle

__all__ = [
    "CrosswordEntry",
    "CrosswordInput",
    "GenerateOptions",
    "GenerationError",
    "PlacedEntry",
    "Puzzle",
    "generate_japanese",
    "generate_native",
    "parse_grid_size",
]
