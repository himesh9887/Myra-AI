"""Plug-and-play search add-on for MYRA.

Usage:
    from search import search
    response = search("kal delhi weather kaisa rahega")
"""

from .search_engine import SearchEngine, search

__all__ = ["SearchEngine", "search"]

