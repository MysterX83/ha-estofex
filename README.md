# ESTOFEX for Home Assistant

A small Home Assistant custom integration that monitors the latest ESTOFEX storm forecast and downloads the latest forecast map for use in a Home Assistant storm dashboard.

This is an early v0.1 integration.

## Features

- Fetches the latest ESTOFEX `stormforecast.xml` forecast id
- Fetches and parses the original ESTOFEX forecast discussion text
- Downloads the latest ESTOFEX forecast map to `/config/www/estofex/latest.png`
- Adds a camera entity for the latest map
- Polls ESTOFEX every hour
- Adds an update button to manually run the same coordinator refresh
- Adds sensors for:
  - Forecast ID
  - Issued At
  - Valid Until
  - Forecast Number
  - Local Map URL
  - Discussion
  - Summary NL
  - Discussion NL
  - Status
  - Last Checked
  - Last Successful Update
  - Last Changed
  - Image Downloaded
  - HTTP Status

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
  - entity: sensor.estofex_discussion
  - entity: sensor.estofex_summary_nl
  - entity: sensor.estofex_discussion_nl
```

### Update button and diagnostics

```yaml
type: entities
entities:
  - entity: button.estofex_update_now
  - entity: sensor.estofex_status
  - entity: sensor.estofex_last_checked
  - entity: sensor.estofex_last_successful_update
  - entity: sensor.estofex_last_changed
  - entity: sensor.estofex_image_downloaded
  - entity: sensor.estofex_http_status
```

## Notes

This integration scrapes the public ESTOFEX forecast listing page. If ESTOFEX changes the HTML structure, the forecast id extraction may need to be adjusted.

When no active forecast exists, the cached map is removed, the camera becomes unavailable, and discussion text attributes are cleared. If ESTOFEX is temporarily unreachable, the previous map and discussion may remain available while `sensor.estofex_status` reports `Offline`.

`sensor.estofex_discussion` has a short state (`Available`, `No forecast`, or `Unavailable`) and exposes the original English discussion text through the `original_text` attribute. It also exposes parsed metadata such as `level_texts`, `forecaster`, `issued_at`, `valid_from`, and `valid_until`.

`sensor.estofex_summary_nl` and `sensor.estofex_discussion_nl` are prepared for future Dutch summarization and translation. They currently do not call any AI service and report `Unavailable` when no optional provider has produced Dutch text.

`sensor.estofex_status` can report `OK`, `Updating`, `No forecast`, `Offline`, or `Error`.

## Roadmap

- Add optional Dutch AI/provider configuration for summaries and translations
- Add Mesoscale Discussion support
- Add notification-friendly binary sensor for new forecasts
- Add options flow for update interval
- Add region filtering, e.g. Benelux / Netherlands
