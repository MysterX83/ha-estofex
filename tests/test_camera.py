"""Dynamic ESTOFEX forecast-camera lifecycle tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from .helpers import install_homeassistant_stubs, load_estofex_module

install_homeassistant_stubs()
load_estofex_module("const")
models = load_estofex_module("models")
load_estofex_module("exceptions")
load_estofex_module("api")
load_estofex_module("geometry")
load_estofex_module("parser")
load_estofex_module("translator")
load_estofex_module("map_cache")
load_estofex_module("coordinator")
load_estofex_module("entity")
camera_module = load_estofex_module("camera")


def _forecast(forecast_id: str, hour: int):
    return models.EstofexForecast(
        id=forecast_id,
        issued_at=datetime(2026, 7, 1, hour, tzinfo=UTC),
        valid_from=None,
        valid_until=datetime(2026, 7, 2, tzinfo=UTC),
        forecaster="TEST",
        forecast_number=str(hour),
        discussion=None,
        discussion_nl=None,
        summary_nl=None,
        map_url=f"remote:{forecast_id}",
        local_map_url=f"local:{forecast_id}",
        local_map_path=None,
        source_url=f"source:{forecast_id}",
    )


class FakeCoordinator:
    def __init__(self, data) -> None:
        self.data = data
        self._listeners = []
        self.last_update_success = True

    @property
    def primary_forecast(self):
        return self.data.primary_forecast

    @property
    def has_forecast_map(self):
        return False

    def async_add_listener(self, listener):
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()


class FakeEntry:
    entry_id = "entry-1"

    def __init__(self) -> None:
        self.unload_callbacks = []

    def async_on_unload(self, callback) -> None:
        self.unload_callbacks.append(callback)


class FakeHass:
    def __init__(self, coordinator, root: Path) -> None:
        self.data = {"estofex": {"entry-1": coordinator}}
        self.config = SimpleNamespace(path=lambda relative: str(root / relative))
        self.tasks = []

    async def async_add_executor_job(self, function, *args):
        return function(*args)

    def async_create_task(self, coroutine, name=None):
        task = asyncio.create_task(coroutine, name=name)
        self.tasks.append(task)
        return task


def test_dynamic_cameras_add_once_remove_and_switch_primary(tmp_path) -> None:
    """Runtime camera synchronization avoids duplicates and removes expiry."""

    async def scenario() -> None:
        older = _forecast("older", 1)
        newer = _forecast("newer", 6)
        coordinator = FakeCoordinator(models.EstofexUpdateData(forecasts=(older,)))
        hass = FakeHass(coordinator, tmp_path)
        entry = FakeEntry()
        entities = []

        def add_entities(new_entities) -> None:
            for entity in new_entities:
                entity.entity_id = f"camera.test_{len(entities)}"
                entity.hass = hass
                entities.append(entity)

        await camera_module.async_setup_entry(hass, entry, add_entities)
        assert len(entities) == 2  # primary camera plus one forecast camera

        coordinator.notify()
        assert len(entities) == 2

        coordinator.data = models.EstofexUpdateData(forecasts=(newer, older))
        coordinator.notify()
        assert len(entities) == 3
        newer_camera = next(
            entity
            for entity in entities
            if getattr(entity, "forecast_id", None) == "newer"
        )
        assert newer_camera.extra_state_attributes["is_primary"] is True

        coordinator.data = models.EstofexUpdateData(forecasts=(newer,))
        coordinator.notify()
        await asyncio.gather(*hass.tasks)
        older_camera = next(
            entity
            for entity in entities
            if getattr(entity, "forecast_id", None) == "older"
        )
        assert older_camera.removed
        assert len(coordinator._listeners) == 1

        entry.unload_callbacks[0]()
        assert not coordinator._listeners

    asyncio.run(scenario())
