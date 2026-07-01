"""Tests for ESTOFEX parser helpers."""
from __future__ import annotations

from .helpers import load_estofex_module

load_estofex_module("models")
parser = load_estofex_module("parser")


def test_parse_latest_forecast_id() -> None:
    """The newest storm forecast id is extracted from the list page."""
    html = """
    <a href="/cgi-bin/polygon/showforecast.cgi?text=yes&fcstfile=2026070106_202606291259_1_stormforecast.xml">Storm Forecast</a>
    <a href="/cgi-bin/polygon/showforecast.cgi?text=yes&fcstfile=2026062906_202606271607_2_stormforecast.xml">Storm Forecast</a>
    """

    assert (
        parser.parse_latest_forecast_id(html)
        == "2026070106_202606291259_1_stormforecast.xml"
    )


def test_parse_estofex_xml_forecast() -> None:
    """ESTOFEX XML-ish source is parsed into a rich forecast model."""
    source = """
    <?xml version="1.0"?>
    <forecast>
      <forecast_type>Storm Forecast</forecast_type>
      <start_time value="2026063006"/>
      <expiry_time value="2026070106"/>
      <issue_time value="202606291259"/>
      <forecaster>TUSCHY</forecaster>
      <text>A level 2 was issued for the test area mainly for very large hail, severe gusts, excessive rain and tornadoes.<BR><BR>DISCUSSION<BR><BR>Heavy rainfall and flash flooding are possible.</text>
      <area risktype="level 2">
        <point lat="0" lon="0"/>
        <point lat="0" lon="2"/>
        <point lat="2" lon="2"/>
        <point lat="2" lon="0"/>
        <point lat="0" lon="0"/>
      </area>
    </forecast>
    """

    forecast = parser.parse_estofex_forecast(
        source,
        "2026070106_202606291259_2_stormforecast.xml",
        map_url="https://example.test/map.png",
    )

    assert forecast.id == "2026070106_202606291259_2_stormforecast.xml"
    assert forecast.forecaster == "TUSCHY"
    assert forecast.forecast_number == "2"
    assert forecast.highest_level == "Level 2"
    assert len(forecast.polygons) == 1
    assert {hazard.type for hazard in forecast.hazards} >= {
        "large_hail",
        "severe_wind",
        "excessive_rain",
        "tornado",
        "flash_flood",
    }
