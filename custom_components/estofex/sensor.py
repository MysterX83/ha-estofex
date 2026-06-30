"""Sensor platform for ESTOFEX."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EstofexCoordinator
from .entity import EstofexEntity


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
