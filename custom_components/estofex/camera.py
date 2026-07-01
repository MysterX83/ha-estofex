"""Camera platform for ESTOFEX."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LATEST_IMAGE_FILENAME, WWW_DIR
from .coordinator import EstofexCoordinator
from .entity import EstofexEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ESTOFEX camera."""
    coordinator: EstofexCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EstofexMapCamera(coordinator, hass)])


class EstofexMapCamera(EstofexEntity, Camera):
    """Camera entity exposing the latest ESTOFEX forecast map."""

    _attr_name = "Map"
    _attr_unique_id = "estofex_map"
    _attr_translation_key = "map"
    _attr_icon = "mdi:map"

    def __init__(self, coordinator: EstofexCoordinator, hass: HomeAssistant) -> None:
        """Initialize the camera."""
        EstofexEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._hass = hass

    @property
    def available(self) -> bool:
        """Return whether the camera has a forecast map to expose."""
        return super().available and self.coordinator.has_forecast_map

    @property
    def extra_state_attributes(self):
        """Return forecast context for the camera image."""
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "forecast_id": data.id,
            "issued": data.issued_at.isoformat() if data.issued_at else None,
            "valid": {
                "from": data.valid_from.isoformat() if data.valid_from else None,
                "until": data.valid_until.isoformat() if data.valid_until else None,
            },
            "forecaster": data.forecaster,
            "highest_level": data.highest_level,
            "hazards": [hazard.label for hazard in data.hazards],
            "discussion_available": bool(data.discussion),
            "summary_available": bool(data.summary_nl),
        }

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return bytes of camera image."""
        if not self.coordinator.has_forecast_map:
            return None

        image_path = Path(self._hass.config.path(WWW_DIR)) / LATEST_IMAGE_FILENAME
        if not image_path.exists():
            return None
        return await self._hass.async_add_executor_job(image_path.read_bytes)
