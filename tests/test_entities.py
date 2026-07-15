"""Entity behavior tests for discussions and combined local risk."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

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
sensor_module = load_estofex_module("sensor")
binary_sensor_module = load_estofex_module("binary_sensor")


def _forecast(
    forecast_id: str,
    hour: int,
    *,
    level: str | None = None,
    hazards=(),
    discussion: str | None = None,
):
    warning = models.EstofexLocalWarning(
        active=level is not None,
        level=level,
        hazards=hazards,
    )
    return models.EstofexForecast(
        id=forecast_id,
        issued_at=datetime(2026, 7, 1, hour, tzinfo=UTC),
        valid_from=None,
        valid_until=datetime(2026, 7, 2, 18, tzinfo=UTC),
        forecaster="TEST",
        forecast_number=str(hour),
        discussion=discussion,
        discussion_nl=None,
        summary_nl=None,
        map_url=f"map:{forecast_id}",
        local_map_url=None,
        local_map_path=None,
        source_url=f"source:{forecast_id}",
        local_warning=warning,
    )


def _coordinator(data):
    return SimpleNamespace(
        data=data,
        primary_forecast=data.primary_forecast,
        local_warning=data.local_warning,
    )


def test_discussion_sensor_keeps_state_short_and_attribute_complete() -> None:
    """Long discussion text is never placed in the native sensor state."""
    discussion = "DISCUSSION\n\n" + "Detailed forecast. " * 2000
    data = models.EstofexUpdateData(
        forecasts=(_forecast("forecast", 6, discussion=discussion),)
    )
    entity = sensor_module.EstofexDiscussionSensor(_coordinator(data))

    assert entity.native_value == "Available"
    assert len(entity.native_value) <= 255
    assert entity.extra_state_attributes["discussion"] == discussion
    assert entity.extra_state_attributes["text"] == discussion
    assert entity.extra_state_attributes["character_count"] == len(discussion)


@pytest.mark.parametrize("level", ["Level 1", "Level 2", "Level 3"])
def test_thunderstorm_sensor_turns_on_for_local_convective_levels(level) -> None:
    """Every defined ESTOFEX convective warning level activates risk."""
    data = models.EstofexUpdateData(forecasts=(_forecast("forecast", 6, level=level),))
    entity = binary_sensor_module.EstofexThunderstormRiskBinarySensor(
        _coordinator(data)
    )

    assert entity.is_on
    assert entity.extra_state_attributes["highest_level"] == level
    assert entity.extra_state_attributes["forecast_count"] == 1


def test_thunderstorm_sensor_ignores_non_level_polygon() -> None:
    """A general or level-zero contour is not treated as convective risk."""
    data = models.EstofexUpdateData(
        forecasts=(_forecast("forecast", 6, level="Thunderstorm"),)
    )
    entity = binary_sensor_module.EstofexThunderstormRiskBinarySensor(
        _coordinator(data)
    )

    assert not entity.is_on
    assert entity.extra_state_attributes["matching_forecast_ids"] == []


def test_hazards_combine_across_primary_and_non_primary_forecasts() -> None:
    """Hazard sensors include matches from every locally affected forecast."""
    hail = models.EstofexHazard(type="large_hail")
    wind = models.EstofexHazard(type="severe_wind")
    data = models.EstofexUpdateData(
        forecasts=(
            _forecast("newer", 6, level="Level 1", hazards=(hail,)),
            _forecast("older", 1, level="Level 2", hazards=(wind,)),
        )
    )
    coordinator = _coordinator(data)
    wind_entity = binary_sensor_module.EstofexHazardBinarySensor(
        coordinator,
        "severe_wind",
        "Severe Wind",
        "estofex_severe_wind",
    )
    risk_entity = binary_sensor_module.EstofexThunderstormRiskBinarySensor(coordinator)

    assert wind_entity.is_on
    assert wind_entity.extra_state_attributes["matching_forecast_ids"] == ["older"]
    assert set(risk_entity.extra_state_attributes["hazards"]) == {
        "Large hail",
        "Severe wind gusts",
    }
