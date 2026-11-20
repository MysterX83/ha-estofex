"""Real Home Assistant fixtures; never import the stub-based unit helpers."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.estofex.api import (
    EstofexApiBytesResponse,
    EstofexApiTextResponse,
)

FORECAST_ID = "2026070212_202607010600_2_stormforecast.xml"
LIST = f'<a href="?fcstfile={FORECAST_ID}">Storm Forecast</a>'
EMPTY_LIST = "<table><tr><td>forecast</td><td>threat level</td><td>period</td><td>forecaster</td></tr></table>"
SOURCE = """<forecast>
<issue_time value="202607010600"/><expiry_time value="2026070212"/>
<text>A level 2 was issued mainly for large hail.</text>
<area risktype="level 2"><point lat="0" lon="0"/><point lat="0" lon="2"/>
<point lat="2" lon="2"/><point lat="2" lon="0"/></area>
</forecast>"""


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Load the repository integration through Home Assistant's loader."""


@pytest.fixture
def forecast_api(hass, freezer, tmp_path):
    """Mock only external ESTOFEX I/O, retaining the real coordinator."""
    freezer.move_to("2026-07-01 12:00:00+00:00")
    hass.config.latitude = 1
    hass.config.longitude = 1
    hass.config.config_dir = str(tmp_path)
    png = (
        Path(__file__).resolve().parents[1]
        / "custom_components/estofex/assets/no_forecast.png"
    ).read_bytes()
    with (
        patch(
            "custom_components.estofex.api.EstofexApiClient.async_fetch_forecast_list",
            new_callable=AsyncMock,
        ) as listing,
        patch(
            "custom_components.estofex.api.EstofexApiClient.async_fetch_forecast_source",
            new_callable=AsyncMock,
        ) as source,
        patch(
            "custom_components.estofex.api.EstofexApiClient.async_fetch_forecast_map",
            new_callable=AsyncMock,
        ) as image,
    ):
        listing.return_value = EstofexApiTextResponse(
            LIST, 200, len(LIST), "https://example.test/list"
        )
        source.return_value = EstofexApiTextResponse(
            SOURCE, 200, len(SOURCE), "https://example.test/source"
        )
        image.return_value = EstofexApiBytesResponse(
            png, 200, len(png), "https://example.test/map"
        )
        yield listing, source, image
