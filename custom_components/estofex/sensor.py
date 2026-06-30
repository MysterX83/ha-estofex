"""Sensor platform for ESTOFEX."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EstofexCoordinator
from .entity import EstofexEntity


def _format_timestamp(value: datetime | None) -> str | None:
    """Format a timestamp for entity attributes."""
    return value.isoformat() if value else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ESTOFEX sensors."""
    coordinator: EstofexCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            EstofexForecastIdSensor(coordinator),
            EstofexIssuedAtSensor(coordinator),
            EstofexValidUntilSensor(coordinator),
            EstofexForecastNumberSensor(coordinator),
            EstofexMapUrlSensor(coordinator),
            EstofexLastCheckedSensor(coordinator),
            EstofexLastSuccessfulUpdateSensor(coordinator),
            EstofexLastChangedSensor(coordinator),
            EstofexImageDownloadedSensor(coordinator),
            EstofexHttpStatusSensor(coordinator),
            EstofexStatusSensor(coordinator),
        ]
    )


class EstofexForecastIdSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast id."""

    _attr_name = "Forecast ID"
    _attr_unique_id = "estofex_forecast_id"
    _attr_icon = "mdi:weather-lightning-rainy"

    @property
    def native_value(self) -> str | None:
        """Return forecast id."""
        return self.coordinator.data.fcstfile if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        """Return forecast attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "image_url": self.coordinator.data.image_url,
            "local_image_url": self.coordinator.data.local_image_url,
            "changed": self.coordinator.data.changed,
            "map_available": self.coordinator.data.map_available,
        }


class EstofexIssuedAtSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast issue timestamp."""

    _attr_name = "Issued At"
    _attr_unique_id = "estofex_issued_at"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return issued timestamp."""
        return self.coordinator.data.issued_at if self.coordinator.data else None


class EstofexValidUntilSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast valid-until timestamp."""

    _attr_name = "Valid Until"
    _attr_unique_id = "estofex_valid_until"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return valid-until timestamp."""
        return self.coordinator.data.valid_until if self.coordinator.data else None


class EstofexForecastNumberSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast number."""

    _attr_name = "Forecast Number"
    _attr_unique_id = "estofex_forecast_number"
    _attr_icon = "mdi:numeric"

    @property
    def native_value(self) -> str | None:
        """Return forecast number."""
        return self.coordinator.data.forecast_number if self.coordinator.data else None


class EstofexMapUrlSensor(EstofexEntity, SensorEntity):
    """Local ESTOFEX map url."""

    _attr_name = "Map URL"
    _attr_unique_id = "estofex_map_url"
    _attr_icon = "mdi:map"

    @property
    def native_value(self) -> str | None:
        """Return local image url."""
        return self.coordinator.data.local_image_url if self.coordinator.data else None


class EstofexLastCheckedSensor(EstofexEntity, SensorEntity):
    """Timestamp of the last ESTOFEX update attempt."""

    _attr_name = "Last Checked"
    _attr_unique_id = "estofex_last_checked"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Return last checked timestamp."""
        return self.coordinator.last_checked


class EstofexLastSuccessfulUpdateSensor(EstofexEntity, SensorEntity):
    """Timestamp of the last successful ESTOFEX update."""

    _attr_name = "Last Successful Update"
    _attr_unique_id = "estofex_last_successful_update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Return last successful update timestamp."""
        return self.coordinator.last_successful_update


class EstofexLastChangedSensor(EstofexEntity, SensorEntity):
    """Timestamp of the last detected forecast change."""

    _attr_name = "Last Changed"
    _attr_unique_id = "estofex_last_changed"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Return last changed timestamp."""
        return self.coordinator.last_changed


class EstofexImageDownloadedSensor(EstofexEntity, SensorEntity):
    """Whether the latest update downloaded a map image."""

    _attr_name = "Image Downloaded"
    _attr_unique_id = "estofex_image_downloaded"
    _attr_icon = "mdi:image-sync"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return whether an image was downloaded during the latest update."""
        return "yes" if self.coordinator.image_downloaded else "no"

    @property
    def extra_state_attributes(self):
        """Return image download diagnostics."""
        return {
            "last_image_downloaded": _format_timestamp(
                self.coordinator.last_image_downloaded
            ),
        }


class EstofexHttpStatusSensor(EstofexEntity, SensorEntity):
    """HTTP status from the latest ESTOFEX request."""

    _attr_name = "HTTP Status"
    _attr_unique_id = "estofex_http_status"
    _attr_icon = "mdi:web-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int | None:
        """Return last HTTP status."""
        return self.coordinator.last_http_status

    @property
    def extra_state_attributes(self):
        """Return detailed HTTP status diagnostics."""
        return {
            "list_http_status": self.coordinator.last_list_http_status,
            "image_http_status": self.coordinator.last_image_http_status,
        }


class EstofexStatusSensor(EstofexEntity, SensorEntity):
    """Status of the latest ESTOFEX update."""

    _attr_name = "Status"
    _attr_unique_id = "estofex_status"
    _attr_icon = "mdi:cloud-sync"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return update status."""
        return self.coordinator.status

    @property
    def extra_state_attributes(self):
        """Return update diagnostics."""
        return {
            "last_error": self.coordinator.last_error,
            "last_checked": _format_timestamp(self.coordinator.last_checked),
            "last_successful_update": _format_timestamp(
                self.coordinator.last_successful_update
            ),
            "last_changed": _format_timestamp(self.coordinator.last_changed),
            "image_downloaded": self.coordinator.image_downloaded,
            "last_image_downloaded": _format_timestamp(
                self.coordinator.last_image_downloaded
            ),
            "last_http_status": self.coordinator.last_http_status,
            "list_http_status": self.coordinator.last_list_http_status,
            "image_http_status": self.coordinator.last_image_http_status,
        }
