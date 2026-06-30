"""Optional translation and summarization hooks for ESTOFEX."""
from __future__ import annotations

from homeassistant.core import HomeAssistant


async def async_translate_to_dutch(
    hass: HomeAssistant, text: str | None
) -> str | None:
    """Return a Dutch translation when an optional provider is configured."""
    if not text:
        return None
    return None


async def async_summarize_to_dutch(
    hass: HomeAssistant, text: str | None
) -> str | None:
    """Return a Dutch practical storm summary when a provider is configured."""
    if not text:
        return None
    return None
