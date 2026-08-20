# SPDX-License-Identifier: GPL-3.0-or-later
"""Package for Anki collection access. Does not import aqt at package level."""

from .errors import CollectionUnavailableError, CrosswordError, SearchQueryError
from .gateway import CollectionGateway, NoteSnapshot

__all__ = [
    "CollectionGateway",
    "CollectionUnavailableError",
    "CrosswordError",
    "NoteSnapshot",
    "SearchQueryError",
]
