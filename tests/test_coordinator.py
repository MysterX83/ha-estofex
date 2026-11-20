"""Coordinator tests with mocked ESTOFEX responses."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from .helpers import install_homeassistant_stubs, load_estofex_module

install_homeassistant_stubs()
load_estofex_module("const")
load_estofex_module("exceptions")
load_estofex_module("api")
models = load_estofex_module("models")
load_estofex_module("geometry")
load_estofex_module("parser")
load_estofex_module("translator")
load_estofex_module("map_cache")
coordinator_module = load_estofex_module("coordinator")
exceptions = load_estofex_module("exceptions")

NOW = datetime(2026, 7, 1, 12, tzinfo=UTC)
OLDER_ID = "2026070206_202606300600_1_stormforecast.xml"
NEWER_ID = "2026070212_202607010600_2_stormforecast.xml"
EXPIRED_ID = "2026070106_202606300600_3_stormforecast.xml"


def _source(forecast_id: str, level: int = 1) -> str:
    """Return a parseable response whose dates match its filename."""
    valid_until, issued_at, *_ = forecast_id.split("_")
    return f"""
    <forecast>
      <expiry_time value="{valid_until}"/>
      <issue_time value="{issued_at}"/>
      <forecaster>TEST</forecaster>
      <text>A level {level} was issued mainly for large hail.</text>
      <area risktype="level {level}">
        <point lat="0" lon="0"/><point lat="0" lon="2"/>
        <point lat="2" lon="2"/><point lat="2" lon="0"/>
      </area>
    </forecast>
    """


class FakeBus:
    """Collect fired Home Assistant events."""

    def __init__(self) -> None:
        self.events = []

    def async_fire(self, event_type, payload) -> None:
        self.events.append((event_type, payload))


class FakeHass:
    """Minimal executor, config, and event-bus surface."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self.config = SimpleNamespace(
            latitude=1.0,
            longitude=1.0,
            path=lambda relative: str(root / relative),
        )
        self.bus = FakeBus()

    async def async_add_executor_job(self, function, *args):
        return function(*args)


class FakeApi:
    """Return deterministic forecast-list, source, and map responses."""

    def __init__(self, forecast_ids: tuple[str, ...]) -> None:
        self.forecast_ids = forecast_ids
        self.map_calls = []
        self.list_error = None

    async def async_fetch_forecast_list(self):
        if self.list_error:
            raise self.list_error
        body = "".join(
            f'<a href="?fcstfile={item}">forecast</a>' for item in self.forecast_ids
        )
        body = (
            "<table><tr><td>forecast</td><td>threat level</td><td>period</td><td>forecaster</td></tr>"
            + body
            + "</table>"
        )
        return SimpleNamespace(body=body, status=200)

    async def async_fetch_forecast_source(self, forecast_id):
        return SimpleNamespace(
            body=_source(forecast_id, 2 if forecast_id == NEWER_ID else 1),
            status=200,
            url=self.forecast_source_url(forecast_id),
        )

    async def async_fetch_forecast_page(self, forecast_id):
        return SimpleNamespace(body="", status=200, url=f"page:{forecast_id}")

    async def async_fetch_forecast_map(self, forecast_id):
        self.map_calls.append(forecast_id)
        body = f"map:{forecast_id}".encode()
        return SimpleNamespace(body=body, status=200, size=len(body))

    @staticmethod
    def forecast_source_url(forecast_id):
        return f"source:{forecast_id}"

    @staticmethod
    def forecast_map_url(forecast_id):
        return f"map:{forecast_id}"


def _coordinator(tmp_path: Path, api: FakeApi):
    instance = coordinator_module.EstofexCoordinator(FakeHass(tmp_path))
    instance._api = api
    instance._utcnow = lambda: NOW
    return instance


def test_two_overlapping_forecasts_are_loaded_and_primary_is_newest(tmp_path) -> None:
    """All active forecasts load while an expired list entry is ignored."""
    api = FakeApi((OLDER_ID, EXPIRED_ID, NEWER_ID))
    coordinator = _coordinator(tmp_path, api)

    data = asyncio.run(coordinator._async_update_data())

    assert data.active_forecast_ids == (NEWER_ID, OLDER_ID)
    assert data.primary_forecast_id == NEWER_ID
    assert data.forecast_count == 2
    assert api.map_calls == [OLDER_ID, NEWER_ID]
    assert coordinator._latest_image_path().read_bytes() == f"map:{NEWER_ID}".encode()


def test_no_active_forecast_clears_active_state(tmp_path) -> None:
    """An authoritative list containing only expired data yields no forecast."""
    api = FakeApi((EXPIRED_ID,))
    coordinator = _coordinator(tmp_path, api)

    data = asyncio.run(coordinator._async_update_data())

    assert data.forecast_count == 0
    assert data.primary_forecast is None
    assert coordinator.status == coordinator_module.STATUS_NO_FORECAST
    assert not api.map_calls


def test_existing_cached_map_is_reused_while_new_map_downloads(tmp_path) -> None:
    """Only a missing active map is downloaded."""
    api = FakeApi((OLDER_ID, NEWER_ID))
    coordinator = _coordinator(tmp_path, api)
    old_path = coordinator._forecast_image_path(OLDER_ID)
    old_path.parent.mkdir(parents=True)
    old_path.write_bytes(b"cached old map")

    data = asyncio.run(coordinator._async_update_data())

    assert data.forecast_count == 2
    assert api.map_calls == [NEWER_ID]
    assert old_path.read_bytes() == b"cached old map"


def test_primary_latest_alias_switches_when_newer_forecast_appears(tmp_path) -> None:
    """The backwards-compatible primary camera alias follows the newest forecast."""
    api = FakeApi((OLDER_ID,))
    coordinator = _coordinator(tmp_path, api)
    previous = asyncio.run(coordinator._async_update_data())
    coordinator.data = previous
    assert coordinator._latest_image_path().read_bytes() == f"map:{OLDER_ID}".encode()

    api.forecast_ids = (OLDER_ID, NEWER_ID)
    current = asyncio.run(coordinator._async_update_data())

    assert current.primary_forecast_id == NEWER_ID
    assert current.added_forecast_ids == (NEWER_ID,)
    assert coordinator._latest_image_path().read_bytes() == f"map:{NEWER_ID}".encode()


def test_one_forecast_parse_failure_does_not_discard_other(tmp_path) -> None:
    """A per-forecast parse failure is isolated from usable active data."""
    api = FakeApi((OLDER_ID, NEWER_ID))
    coordinator = _coordinator(tmp_path, api)
    original_parse = coordinator._parse_forecast_source

    def parse(source, forecast_id, map_url, source_url):
        if forecast_id == OLDER_ID:
            raise exceptions.EstofexParseError("broken fixture")
        return original_parse(source, forecast_id, map_url, source_url)

    coordinator._parse_forecast_source = parse

    data = asyncio.run(coordinator._async_update_data())

    assert data.active_forecast_ids == (NEWER_ID,)
    assert coordinator.status == coordinator_module.STATUS_OK
    assert OLDER_ID in coordinator.last_error


def test_list_timeout_preserves_previous_forecasts(tmp_path) -> None:
    """Offline updates retain useful previously fetched forecast data."""
    api = FakeApi((NEWER_ID,))
    coordinator = _coordinator(tmp_path, api)
    previous = asyncio.run(coordinator._async_update_data())
    coordinator.data = previous
    api.list_error = exceptions.EstofexConnectionError("timeout")

    current = asyncio.run(coordinator._async_update_data())

    assert current.active_forecast_ids == previous.active_forecast_ids
    assert current.primary_forecast.discussion == previous.primary_forecast.discussion
    assert (
        current.primary_forecast.local_map_url
        == previous.primary_forecast.local_map_url
    )
    assert not current.changed
    assert coordinator.status == coordinator_module.STATUS_OFFLINE


def test_warning_is_not_cleared_while_another_forecast_still_matches(tmp_path) -> None:
    """Combined warning transitions do not clear on one forecast expiring."""
    coordinator = _coordinator(tmp_path, FakeApi(()))
    warning = models.EstofexLocalWarning(active=True, level="Level 1")
    base = models.EstofexForecast(
        id=OLDER_ID,
        issued_at=NOW,
        valid_from=None,
        valid_until=datetime(2026, 7, 2, tzinfo=UTC),
        forecaster=None,
        forecast_number="1",
        discussion=None,
        discussion_nl=None,
        summary_nl=None,
        map_url=None,
        local_map_url=None,
        local_map_path=None,
        local_warning=warning,
    )
    other = models.EstofexForecast(
        id=NEWER_ID,
        issued_at=NOW,
        valid_from=None,
        valid_until=datetime(2026, 7, 2, tzinfo=UTC),
        forecaster=None,
        forecast_number="2",
        discussion=None,
        discussion_nl=None,
        summary_nl=None,
        map_url=None,
        local_map_url=None,
        local_map_path=None,
        local_warning=warning,
    )
    previous = models.EstofexUpdateData(forecasts=(base, other))
    current = models.EstofexUpdateData(forecasts=(other,))

    coordinator._fire_transition_events(previous, current)

    assert not coordinator.hass.bus.events


@pytest.mark.parametrize("expired", [False, True])
def test_invalid_list_preserves_only_unexpired_warnings(tmp_path, expired) -> None:
    async def scenario():
        api = FakeApi((NEWER_ID,))
        coordinator = _coordinator(tmp_path, api)
        coordinator.data = await coordinator._async_update_data()
        coordinator.hass.bus.events.clear()
        if expired:
            coordinator._utcnow = lambda: datetime(2026, 7, 2, 12, tzinfo=UTC)

        async def error_page():
            return SimpleNamespace(
                body="<html>Temporarily unavailable</html>", status=200
            )

        api.async_fetch_forecast_list = error_page
        data = await coordinator._async_update_data()
        assert coordinator.status == coordinator_module.STATUS_ERROR
        assert data.forecast_count == (0 if expired else 1)
        assert data.local_warning.active is not expired
        assert coordinator._latest_image_path().exists()
        assert [event for event, _ in coordinator.hass.bus.events] == (
            [coordinator_module.EVENT_WARNING_CLEARED] if expired else []
        )

    asyncio.run(scenario())


def test_bad_source_is_retried_after_recovery(tmp_path) -> None:
    async def scenario():
        api = FakeApi((NEWER_ID,))
        coordinator = _coordinator(tmp_path, api)
        original = api.async_fetch_forecast_source

        async def error_page(forecast_id):
            return SimpleNamespace(
                body="<html>Temporarily unavailable</html>", status=200, url="test"
            )

        api.async_fetch_forecast_source = error_page
        coordinator.data = await coordinator._async_update_data()
        assert coordinator.status == coordinator_module.STATUS_ERROR
        assert not coordinator.data.forecasts
        assert not api.map_calls
        api.async_fetch_forecast_source = original
        data = await coordinator._async_update_data()
        assert coordinator.status == coordinator_module.STATUS_OK
        assert data.local_warning.active
        assert data.forecast_count == 1

    asyncio.run(scenario())
