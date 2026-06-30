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
    _attr_icon = "mdi:map"

    def __init__(self, coordinator: EstofexCoordinator, hass: HomeAssistant) -> None:
        """Initialize the camera."""
        EstofexEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._hass = hass

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return bytes of camera image."""
        image_path = Path(self._hass.config.path(WWW_DIR)) / LATEST_IMAGE_FILENAME
        if not image_path.exists():
            return None
        return await self._hass.async_add_executor_job(image_path.read_bytes)
