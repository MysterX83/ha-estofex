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
    HAZARD_LABELS,
    HAZARD_LARGE_HAIL,
    HAZARD_SEVERE_WIND,
    HAZARD_TORNADO,
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
            EstofexThunderstormRiskBinarySensor(coordinator),
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
        forecast = next(
            (
                item
                for item in data.forecasts
                if item.id in warning.matching_forecast_ids
            ),
            data.primary_forecast,
        )
        polygon = warning.polygon.as_attribute() if warning.polygon else None
        return {
            "level": warning.level,
            "hazards": warning.hazard_labels,
            "matching_forecast_ids": list(warning.matching_forecast_ids),
            "polygon": polygon,
            "issued_at": _format_timestamp(forecast.issued_at if forecast else None),
            "valid_until": _format_timestamp(
                forecast.valid_until if forecast else None
            ),
        }


class EstofexThunderstormRiskBinarySensor(EstofexEntity, BinarySensorEntity):
    """Whether any active ESTOFEX level 1-3 polygon affects the location."""

    _attr_name = "Thunderstorm Risk"
    _attr_unique_id = "estofex_thunderstorm_risk"
    _attr_translation_key = "thunderstorm_risk"
    _attr_icon = "mdi:weather-lightning"

    @property
    def is_on(self) -> bool:
        """Return the combined local convective risk state."""
        return bool(self.coordinator.data and self.coordinator.data.thunderstorm_risk)

    @property
    def extra_state_attributes(self):
        """Return combined risk context from all matching forecasts."""
        data = self.coordinator.data
        if not data:
            return {
                "highest_level": None,
                "matching_forecast_ids": [],
                "forecast_count": 0,
                "hazards": [],
                "issued_at": None,
                "valid_until": None,
                "summary": "No local ESTOFEX thunderstorm risk.",
            }

        matching = data.thunderstorm_forecasts
        primary_matching = matching[0] if matching else None
        level = data.highest_thunderstorm_level
        until = primary_matching.valid_until if primary_matching else None
        summary = "No local ESTOFEX thunderstorm risk."
        if level:
            until_text = f" until {until:%H:%M} UTC" if until else ""
            summary = f"Thunderstorm risk: ESTOFEX {level.lower()}{until_text}"
        return {
            "highest_level": level,
            "matching_forecast_ids": [
                forecast.id for forecast in matching if forecast.id
            ],
            "forecast_count": len(matching),
            "hazards": [hazard.label for hazard in data.thunderstorm_hazards],
            "issued_at": _format_timestamp(
                primary_matching.issued_at if primary_matching else None
            ),
            "valid_until": _format_timestamp(until),
            "summary": summary,
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
        matching = tuple(
            forecast
            for forecast in data.forecasts
            if forecast.local_warning.active
            and self._hazard_type in forecast.local_warning.hazard_types
        )
        primary_matching = matching[0] if matching else data.primary_forecast
        return {
            "hazard": HAZARD_LABELS.get(self._hazard_type, self._hazard_type),
            "level": data.local_warning.level,
            "forecast_id": primary_matching.id if primary_matching else None,
            "matching_forecast_ids": [
                forecast.id for forecast in matching if forecast.id
            ],
            "valid_until": _format_timestamp(
                primary_matching.valid_until if primary_matching else None
            ),
        }
