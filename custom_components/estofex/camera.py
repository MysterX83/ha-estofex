"""Camera platform for ESTOFEX."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LATEST_IMAGE_FILENAME, NO_FORECAST_IMAGE_FILENAME, WWW_DIR
from .coordinator import EstofexCoordinator
from .entity import EstofexEntity
from .models import EstofexForecast


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the primary and dynamic active-forecast cameras."""
    coordinator: EstofexCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EstofexMapCamera(coordinator, hass)])

    cameras: dict[str, EstofexForecastCamera] = {}

    def _sync_forecast_cameras() -> None:
        current_ids = set(
            coordinator.data.active_forecast_ids if coordinator.data else ()
        )
        new_ids = current_ids - cameras.keys()
        if new_ids:
            new_cameras = [
                EstofexForecastCamera(coordinator, hass, entry.entry_id, forecast_id)
                for forecast_id in sorted(new_ids)
            ]
            cameras.update({camera.forecast_id: camera for camera in new_cameras})
            async_add_entities(new_cameras)

        for forecast_id in set(cameras) - current_ids:
            camera = cameras.pop(forecast_id)
            hass.async_create_task(
                _async_remove_forecast_camera(hass, camera),
                f"Remove expired ESTOFEX camera {forecast_id}",
            )

    _sync_forecast_cameras()
    entry.async_on_unload(coordinator.async_add_listener(_sync_forecast_cameras))


async def _async_remove_forecast_camera(
    hass: HomeAssistant,
    camera: EstofexForecastCamera,
) -> None:
    """Remove an expired forecast camera from state and entity registry."""
    if camera.entity_id is not None:
        await camera.async_remove()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("camera", DOMAIN, camera.unique_id)
    if entity_id:
        registry.async_remove(entity_id)


class EstofexMapCamera(EstofexEntity, Camera):
    """Backwards-compatible camera exposing the primary forecast map."""

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
    def extra_state_attributes(self):
        """Return complete context for the primary forecast."""
        forecast = self.coordinator.primary_forecast
        if not forecast:
            return {}
        return _forecast_attributes(
            forecast,
            is_primary=True,
        )

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return primary map bytes or the packaged placeholder."""
        image_path = self._image_path()
        if not image_path.exists():
            return None
        return await self._hass.async_add_executor_job(image_path.read_bytes)

    def _image_path(self) -> Path:
        """Return the primary alias or the bundled no-forecast image."""
        if self.coordinator.has_forecast_map:
            image_path = Path(self._hass.config.path(WWW_DIR)) / LATEST_IMAGE_FILENAME
            if image_path.exists():
                return image_path
        return _placeholder_path()


class EstofexForecastCamera(EstofexEntity, Camera):
    """Camera exposing one specific active ESTOFEX forecast map."""

    _attr_icon = "mdi:map-outline"

    def __init__(
        self,
        coordinator: EstofexCoordinator,
        hass: HomeAssistant,
        entry_id: str,
        forecast_id: str,
    ) -> None:
        """Initialize a stable forecast-specific camera."""
        EstofexEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._hass = hass
        self.forecast_id = forecast_id
        self._attr_unique_id = f"{entry_id}_forecast_map_{forecast_id}"
        forecast = (
            coordinator.data.get_forecast(forecast_id) if coordinator.data else None
        )
        label = forecast.forecast_number if forecast else forecast_id
        self._attr_name = f"Map Forecast {label}"

    @property
    def available(self) -> bool:
        """Return whether this forecast remains active."""
        return super().available and self._forecast is not None

    @property
    def _forecast(self) -> EstofexForecast | None:
        """Return this camera's current forecast model."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get_forecast(self.forecast_id)

    @property
    def extra_state_attributes(self):
        """Return complete context for this forecast."""
        forecast = self._forecast
        if not forecast:
            return {}
        return _forecast_attributes(
            forecast,
            is_primary=(
                forecast.id == self.coordinator.data.primary_forecast_id
                if self.coordinator.data
                else False
            ),
        )

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return this forecast map or the packaged placeholder."""
        forecast = self._forecast
        image_path = (
            Path(forecast.local_map_path)
            if forecast and forecast.map_available and forecast.local_map_path
            else _placeholder_path()
        )
        if not image_path.exists():
            return None
        return await self._hass.async_add_executor_job(image_path.read_bytes)


def _forecast_attributes(
    forecast: EstofexForecast,
    *,
    is_primary: bool,
) -> dict[str, object]:
    """Return the common public camera metadata."""
    return {
        "forecast_id": forecast.id,
        "forecast_number": forecast.forecast_number,
        "issued_at": forecast.issued_at.isoformat() if forecast.issued_at else None,
        "valid_until": (
            forecast.valid_until.isoformat() if forecast.valid_until else None
        ),
        "forecaster": forecast.forecaster,
        "source_url": forecast.source_url,
        "map_url": forecast.map_url,
        "local_map_url": forecast.local_map_url,
        "is_primary": is_primary,
        "local_warning": forecast.local_warning.active,
        "local_level": forecast.local_level,
        "hazards": forecast.local_warning.hazard_labels,
        "levels_present": list(forecast.levels_present),
    }


def _placeholder_path() -> Path:
    """Return the packaged no-forecast image path."""
    return Path(__file__).with_name("assets") / NO_FORECAST_IMAGE_FILENAME
