"""Domain-specific exceptions for ESTOFEX."""
from __future__ import annotations


class EstofexError(Exception):
    """Base ESTOFEX integration error."""


class EstofexConnectionError(EstofexError):
    """ESTOFEX could not be reached or returned an HTTP error."""

    def __init__(self, message: str, status: int | None = None) -> None:
        """Initialize the connection error."""
        super().__init__(message)
        self.status = status


class EstofexParseError(EstofexError):
    """ESTOFEX response parsing failed."""


class EstofexNoForecastError(EstofexError):
    """ESTOFEX is reachable but no active forecast is available."""
