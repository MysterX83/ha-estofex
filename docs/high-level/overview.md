# System overview

[Documentation index](../README.md) · [Architecture](architecture.md)

## Purpose

ESTOFEX for Home Assistant brings public convective forecasts into Home Assistant.
Users can view forecast maps, read forecast discussions and build automations
around risks at their configured home location.

The integration is independent of ESTOFEX. It presents a convective forecast
product; it does not replace official warnings from national meteorological
services or calculate its own weather forecast.

## Inputs and outputs

| Input | Use |
| --- | --- |
| Public ESTOFEX forecast list | Discover potentially active forecasts |
| Forecast source and optional HTML discussion | Extract times, polygons, levels and hazards |
| ESTOFEX map images | Display locally cached forecast maps |
| Home Assistant latitude and longitude | Evaluate whether the location falls inside polygons |

Outputs are sensors, binary sensors, cameras, a refresh button, Home Assistant
events and diagnostics. See the [entity reference](../../README.md#entities) and
[event reference](../../README.md#events) for their public interface.

## Main behavior

- One integration instance uses Home Assistant's location; no YAML or credentials
  are required.
- Refresh runs hourly and can also be requested manually.
- Multiple active forecasts coexist. The newest by issue time is the primary
  forecast used by the existing metadata sensors and primary camera.
- Local warnings combine all active forecasts, so an older overlapping forecast
  can still contribute a warning even when it is not primary.
- A verified absence of active forecasts clears the active data and cached maps.
- An outage or invalid response preserves still-valid previous forecasts. Expiry
  is evaluated during refresh, not by a separate timer at the exact expiry time.

For example, if forecasts A and B overlap and only A covers the home location,
B becoming primary does not clear A's local warning. The warning clears when no
remaining active forecast covers the location.

## Boundaries and limitations

The integration has no external database or background service. Parsed forecasts
live in memory; map images are cached in Home Assistant's configuration directory.
After a restart or reload, forecast metadata is fetched again and existing map
files can be reused.

Hazards are extracted from bulletin text and associated with polygons on a
best-effort basis. Local thunderstorm risk means a matching level 1–3 polygon;
it is not an exact probability percentage.

Dutch translation and summary functions are extension hooks returning no result
in the current implementation. No AI provider is included. Mesoscale Discussion
models do not imply an implemented ingestion feature. Other weather services and
a custom dashboard card are outside the current implementation.

## Operational considerations

Map files are served under `/local/estofex/`; treat this as public static content.
Diagnostics omit precise home coordinates and local filesystem paths. Public
forecast URLs may be included. Network availability and upstream document format
remain external dependencies.

Use the [troubleshooting guide](../../README.md#troubleshooting) for user-facing
checks and [runtime behavior](../low-level/runtime.md) for failure details.
