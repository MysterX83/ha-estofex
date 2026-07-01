"""Binary sensor platform for ESTOFEX."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EstofexCoordinator
from .entity import EstofexEntity
from .models import (
    HAZARD_EXCESSIVE_RAIN,
    HAZARD_FLASH_FLOOD,
    HAZARD_LARGE_HAIL,
    HAZARD_SEVERE_WIND,
    HAZARD_TORNADO,
    HAZARD_LABELS,
)


def _format_timestamp(value: datetime | None) -> str | None:
    """Format a timestamp for entity attributes."""
    return value.isoformat() if value else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ESTOFEX binary sensors."""
    coordinator: EstofexCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            EstofexLocalWarningBinarySensor(coordinator),
            EstofexForecastChangedBinarySensor(coordinator),
            EstofexHazardBinarySensor(
                coordinator,
                HAZARD_LARGE_HAIL,
                "Large Hail",
                "estofex_large_hail",
            ),
            EstofexHazardBinarySensor(
                coordinator,
                HAZARD_SEVERE_WIND,
                "Severe Wind",
                "estofex_severe_wind",
            ),
            EstofexHazardBinarySensor(
                coordinator,
                HAZARD_EXCESSIVE_RAIN,
                "Excessive Rain",
                "estofex_excessive_rain",
            ),
            EstofexHazardBinarySensor(
                coordinator,
                HAZARD_TORNADO,
                "Tornado",
                "estofex_tornado",
            ),
            EstofexHazardBinarySensor(
                coordinator,
                HAZARD_FLASH_FLOOD,
                "Flash Flood",
                "estofex_flash_flood",
            ),
        ]
    )


class EstofexLocalWarningBinarySensor(EstofexEntity, BinarySensorEntity):
    """Whether the configured Home Assistant location is inside a forecast polygon."""

    _attr_name = "Local Warning"
    _attr_unique_id = "estofex_local_warning"
    _attr_translation_key = "local_warning"
    _attr_icon = "mdi:map-marker-alert"

    @property
    def is_on(self) -> bool:
        """Return whether the local location is inside a warning polygon."""
        return self.coordinator.local_warning.active

    @property
    def extra_state_attributes(self):
        """Return local warning attributes."""
        data = self.coordinator.data
        if not data:
            return {}

        warning = data.local_warning
        polygon = warning.polygon.as_attribute() if warning.polygon else None
        return {
            "level": warning.level,
            "hazards": warning.hazard_labels,
            "polygon": polygon,
            "issued_at": _format_timestamp(data.issued_at),
            "valid_until": _format_timestamp(data.valid_until),
        }


class EstofexForecastChangedBinarySensor(EstofexEntity, BinarySensorEntity):
    """Whether the latest update detected a new forecast."""

    _attr_name = "Forecast Changed"
    _attr_unique_id = "estofex_forecast_changed"
    _attr_translation_key = "forecast_changed"
    _attr_icon = "mdi:file-sync"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return whether the latest cycle detected a new forecast."""
        return bool(self.coordinator.data and self.coordinator.data.changed)


class EstofexHazardBinarySensor(EstofexEntity, BinarySensorEntity):
    """Whether a local warning contains a specific hazard."""

    def __init__(
        self,
        coordinator: EstofexCoordinator,
        hazard_type: str,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize a hazard binary sensor."""
        super().__init__(coordinator)
        self._hazard_type = hazard_type
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_translation_key = hazard_type
        self._attr_icon = "mdi:alert-outline"

    @property
    def is_on(self) -> bool:
        """Return whether the local warning has this hazard."""
        warning = self.coordinator.local_warning
        return warning.active and self._hazard_type in warning.hazard_types

    @property
    def extra_state_attributes(self):
        """Return hazard context."""
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "hazard": HAZARD_LABELS.get(self._hazard_type, self._hazard_type),
            "level": data.local_warning.level,
            "forecast_id": data.id,
            "valid_until": _format_timestamp(data.valid_until),
        }
