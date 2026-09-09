"""Provider base types and exceptions."""

from __future__ import annotations


class SearchError(Exception):
    """Base search error."""


class NetworkError(SearchError):
    """Connection/timeout failure."""


class ParseError(SearchError):
    """Failed to parse provider response."""


class RateLimitError(SearchError):
    """Provider rate-limited us."""


class AuthError(SearchError):
    """Missing or invalid API key."""
