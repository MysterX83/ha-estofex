"""Tests for ESTOFEX domain models."""

from __future__ import annotations

from datetime import UTC, datetime

from .helpers import load_estofex_module

models = load_estofex_module("models")


def _forecast(
    valid_until: datetime | None,
    *,
    forecast_id: str = "2026070106_202606291259_1_stormforecast.xml",
    issued_at: datetime | None = None,
    warning=None,
):
    """Return a minimal forecast model for expiry checks."""
    return models.EstofexForecast(
        id=forecast_id,
        issued_at=issued_at,
        valid_from=None,
        valid_until=valid_until,
        forecaster=None,
        forecast_number=None,
        discussion=None,
        discussion_nl=None,
        summary_nl=None,
        map_url=None,
        local_map_url=None,
        local_map_path=None,
        local_warning=warning or models.EstofexLocalWarning(),
    )


def test_forecast_is_expired_at_valid_until() -> None:
    """A forecast is no longer active once its valid-until time is reached."""
    forecast = _forecast(datetime(2026, 7, 1, 6, tzinfo=UTC))

    assert forecast.is_expired(datetime(2026, 7, 1, 6, tzinfo=UTC))


def test_forecast_is_not_expired_before_valid_until() -> None:
    """A forecast remains active before its valid-until time."""
    forecast = _forecast(datetime(2026, 7, 1, 6, tzinfo=UTC))

    assert not forecast.is_expired(datetime(2026, 7, 1, 5, 59, tzinfo=UTC))


def test_forecast_without_valid_until_is_not_expired() -> None:
    """Missing validity data should not clear a forecast by itself."""
    forecast = _forecast(None)

    assert not forecast.is_expired(datetime(2026, 7, 1, 6, tzinfo=UTC))


def test_forecast_activity_uses_issued_and_valid_until() -> None:
    """Activity is inclusive at issue time and exclusive at expiry time."""
    forecast = _forecast(
        datetime(2026, 7, 2, tzinfo=UTC),
        issued_at=datetime(2026, 7, 1, tzinfo=UTC),
    )

    assert not forecast.is_active(datetime(2026, 6, 30, 23, 59, tzinfo=UTC))
    assert forecast.is_active(datetime(2026, 7, 1, tzinfo=UTC))
    assert not forecast.is_active(datetime(2026, 7, 2, tzinfo=UTC))


def test_forecast_without_issued_at_can_be_active() -> None:
    """A parseable forecast without issue time uses its expiry time."""
    forecast = _forecast(datetime(2026, 7, 2, tzinfo=UTC))

    assert forecast.is_active(datetime(2026, 7, 1, tzinfo=UTC))


def test_update_data_sorts_and_selects_primary_forecast() -> None:
    """The newest active forecast is primary regardless of input order."""
    older = _forecast(
        datetime(2026, 7, 2, tzinfo=UTC),
        forecast_id="older",
        issued_at=datetime(2026, 7, 1, 0, tzinfo=UTC),
    )
    newer = _forecast(
        datetime(2026, 7, 2, tzinfo=UTC),
        forecast_id="newer",
        issued_at=datetime(2026, 7, 1, 6, tzinfo=UTC),
    )

    data = models.EstofexUpdateData(forecasts=(older, newer))

    assert data.forecasts == (newer, older)
    assert data.primary_forecast is newer
    assert data.primary_forecast_id == "newer"
    assert data.get_forecast("older") is older
    assert data.forecast_count == 2


def test_thunderstorm_risk_combines_non_primary_forecast_hazards() -> None:
    """A locally matching older level forecast contributes risk and hazards."""
    hail = models.EstofexHazard(type="large_hail")
    wind = models.EstofexHazard(type="severe_wind")
    newer = _forecast(
        datetime(2026, 7, 2, tzinfo=UTC),
        forecast_id="newer",
        issued_at=datetime(2026, 7, 1, 6, tzinfo=UTC),
        warning=models.EstofexLocalWarning(active=False),
    )
    older = _forecast(
        datetime(2026, 7, 2, tzinfo=UTC),
        forecast_id="older",
        issued_at=datetime(2026, 7, 1, 0, tzinfo=UTC),
        warning=models.EstofexLocalWarning(
            active=True,
            level="Level 2",
            hazards=(hail, wind),
        ),
    )

    data = models.EstofexUpdateData(forecasts=(newer, older))

    assert data.thunderstorm_risk
    assert data.highest_thunderstorm_level == "Level 2"
    assert [forecast.id for forecast in data.thunderstorm_forecasts] == ["older"]
    assert {hazard.type for hazard in data.thunderstorm_hazards} == {
        "large_hail",
        "severe_wind",
    }
    assert data.local_warning.matching_forecast_ids == ("older",)
