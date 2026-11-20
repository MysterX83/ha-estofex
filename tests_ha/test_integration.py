"""Exercise config flow, platforms, events and lifecycle in real Home Assistant."""

from homeassistant.components.camera import async_get_image
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.estofex.api import EstofexApiTextResponse
from custom_components.estofex.exceptions import EstofexConnectionError

from .conftest import EMPTY_LIST, FORECAST_ID


async def setup_entry(hass):
    entry = MockConfigEntry(domain="estofex", title="ESTOFEX", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry, hass.data["estofex"][entry.entry_id]


def entity_id(hass, platform, unique_id):
    result = er.async_get(hass).async_get_entity_id(platform, "estofex", unique_id)
    assert result is not None
    return result


async def test_config_flow_and_single_instance(hass, forecast_api):
    result = await hass.config_entries.flow.async_init(
        "estofex", context={"source": "user"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    duplicate = await hass.config_entries.flow.async_init(
        "estofex", context={"source": "user"}
    )
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "single_instance_allowed"


async def test_platforms_refresh_and_unload(hass, forecast_api):
    entry, coordinator = await setup_entry(hass)
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert {item.domain for item in entities} == {
        "sensor",
        "binary_sensor",
        "camera",
        "button",
    }
    warning_id = entity_id(hass, "binary_sensor", "estofex_local_warning")
    assert hass.states.get(warning_id).state == "on"
    camera_id = entity_id(
        hass, "camera", f"{entry.entry_id}_forecast_map_{FORECAST_ID}"
    )
    assert hass.states.get(camera_id) is not None
    camera_image = await async_get_image(hass, camera_id)
    assert camera_image.content == forecast_api[2].return_value.body
    events = []
    remove = hass.bus.async_listen("estofex_warning_cleared", events.append)
    listing, _, _ = forecast_api
    listing.return_value = EstofexApiTextResponse(
        EMPTY_LIST, 200, len(EMPTY_LIST), "https://example.test/list"
    )
    button_id = entity_id(hass, "button", "estofex_update_now")
    await hass.services.async_call(
        "button", "press", {"entity_id": button_id}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(warning_id).state == "off"
    assert registry.async_get(camera_id) is None
    assert hass.states.get(camera_id) is None
    assert len(events) == 1
    remove()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data["estofex"]
    assert not list(coordinator.async_contexts())


async def test_invalid_response_and_expiry(hass, forecast_api, freezer):
    entry, coordinator = await setup_entry(hass)
    warning_id = entity_id(hass, "binary_sensor", "estofex_local_warning")
    listing, _, _ = forecast_api
    listing.return_value = EstofexApiTextResponse(
        "<html>Unavailable</html>", 200, 24, "https://example.test/list"
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.status == "Error"
    assert hass.states.get(warning_id).state == "on"
    freezer.move_to("2026-07-02 12:00:00+00:00")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(warning_id).state == "off"
    assert not coordinator.data.forecasts
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_invalid_source_recovers_on_refresh(hass, forecast_api):
    _, source, image = forecast_api
    valid_source = source.return_value
    source.return_value = EstofexApiTextResponse(
        "<html>Unavailable</html>", 200, 24, "https://example.test/source"
    )
    entry, coordinator = await setup_entry(hass)
    assert coordinator.status == "Error"
    assert not coordinator.data.forecasts
    image.assert_not_awaited()
    registry = er.async_get(hass)
    unique_id = f"{entry.entry_id}_forecast_map_{FORECAST_ID}"
    assert registry.async_get_entity_id("camera", "estofex", unique_id) is None

    source.return_value = valid_source
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.status == "OK"
    assert (
        hass.states.get(entity_id(hass, "binary_sensor", "estofex_local_warning")).state
        == "on"
    )
    assert hass.states.get(entity_id(hass, "camera", unique_id)) is not None
    assert source.await_count == 2


async def test_offline_retains_warning_and_reload_reuses_entities(hass, forecast_api):
    entry, coordinator = await setup_entry(hass)
    listing, _, image = forecast_api
    registry = er.async_get(hass)
    original_ids = {
        item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    listing.side_effect = EstofexConnectionError("timeout")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.status == "Offline"
    assert (
        hass.states.get(entity_id(hass, "binary_sensor", "estofex_local_warning")).state
        == "on"
    )
    listing.side_effect = None
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert {
        item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    } == original_ids
    assert hass.data["estofex"][entry.entry_id] is not coordinator
    assert image.await_count == 1
