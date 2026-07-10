"""Tests for ESTOFEX domain models."""

from __future__ import annotations

from datetime import UTC, datetime

from .helpers import load_estofex_module

models = load_estofex_module("models")


def _forecast(valid_until: datetime | None):
    """Return a minimal forecast model for expiry checks."""
    return models.EstofexForecast(
        id="2026070106_202606291259_1_stormforecast.xml",
        issued_at=None,
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
