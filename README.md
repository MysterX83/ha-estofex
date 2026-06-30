# ESTOFEX for Home Assistant

A small Home Assistant custom integration that monitors the latest ESTOFEX storm forecast and downloads the latest forecast map for use in a Home Assistant storm dashboard.

This is an early v0.1 integration.

## Features

- Fetches the latest ESTOFEX `stormforecast.xml` forecast id
- Downloads the latest ESTOFEX forecast map to `/config/www/estofex/latest.png`
- Adds a camera entity for the latest map
- Adds sensors for:
  - Forecast ID
  - Issued At
  - Valid Until
  - Forecast Number
  - Local Map URL

## Installation manually

Copy the folder:

```text
custom_components/estofex
```

to:

```text
/config/custom_components/estofex
```

Restart Home Assistant.

Then add the integration via:

```text
Settings -> Devices & services -> Add integration -> ESTOFEX
```

## Docker example

If your Home Assistant config is mounted at:

```text
/mnt/safe/homeassistant/config:/config
```

then copy the integration to:

```text
/mnt/safe/homeassistant/config/custom_components/estofex
```

Restart the Home Assistant container afterwards.

## Dashboard examples

### Camera card

```yaml
type: picture-entity
entity: camera.estofex_map
show_name: false
show_state: false
```

### Picture card

```yaml
type: picture
image: /local/estofex/latest.png
tap_action:
  action: url
  url_path: https://www.estofex.org
```

### Entity card

```yaml
type: entities
entities:
  - entity: sensor.estofex_forecast_id
  - entity: sensor.estofex_issued_at
  - entity: sensor.estofex_valid_until
  - entity: sensor.estofex_forecast_number
  - entity: sensor.estofex_map_url
```

## Notes

This integration scrapes the public ESTOFEX forecast listing page. If ESTOFEX changes the HTML structure, the forecast id extraction may need to be adjusted.

## Roadmap

- Parse warning levels from forecast text
- Add Mesoscale Discussion support
- Add notification-friendly binary sensor for new forecasts
- Add options flow for update interval
- Add region filtering, e.g. Benelux / Netherlands
