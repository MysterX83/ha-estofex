"""Diagnostics support for ESTOFEX."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EstofexCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EstofexCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if coordinator is None:
        return {"loaded": False}

    forecast = coordinator.data
    return {
        "loaded": True,
        "status": coordinator.status,
        "forecast_id": forecast.id if forecast else None,
        "forecast_number": forecast.forecast_number if forecast else None,
        "issued_at": _format_datetime(forecast.issued_at if forecast else None),
        "valid_from": _format_datetime(forecast.valid_from if forecast else None),
        "valid_until": _format_datetime(forecast.valid_until if forecast else None),
        "last_checked": _format_datetime(coordinator.last_checked),
        "last_successful_update": _format_datetime(
            coordinator.last_successful_update
        ),
        "last_changed": _format_datetime(coordinator.last_changed),
        "forecast_source_url": coordinator.forecast_source_url,
        "last_http_status": coordinator.last_http_status,
        "last_list_http_status": coordinator.last_list_http_status,
        "last_forecast_http_status": coordinator.last_forecast_http_status,
        "last_image_http_status": coordinator.last_image_http_status,
        "last_update_duration": coordinator.last_update_duration,
        "last_download_size": coordinator.last_download_size,
        "image_downloaded": coordinator.image_downloaded,
        "map_available": forecast.map_available if forecast else False,
        "polygons": len(forecast.polygons) if forecast else 0,
        "hazards": [hazard.type for hazard in forecast.hazards] if forecast else [],
        "local_warning": (
            forecast.local_warning.active if forecast else False
        ),
        "parser_version": (
            forecast.diagnostics.parser_version if forecast else None
        ),
        "last_error": coordinator.last_error,
    }


def _format_datetime(value: datetime | None) -> str | None:
    """Format a datetime for diagnostics."""
    return value.isoformat() if value else None
