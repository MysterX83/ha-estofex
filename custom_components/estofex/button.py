"""Button platform for ESTOFEX."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EstofexCoordinator
from .entity import EstofexEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ESTOFEX buttons."""
    coordinator: EstofexCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EstofexUpdateNowButton(coordinator)])


class EstofexUpdateNowButton(EstofexEntity, ButtonEntity):
    """Button to request an immediate ESTOFEX update."""

    _attr_name = "Update Now"
    _attr_unique_id = "estofex_update_now"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Request an immediate ESTOFEX update."""
        await self.coordinator.async_force_refresh()
