# Contributing

Thanks for helping improve ESTOFEX for Home Assistant.

## Development

1. Fork the repository.
2. Create a branch for a focused change.
3. Keep API access, parsing, coordinator logic, entities, and diagnostics separated.
4. Avoid live ESTOFEX requests in tests; mock external responses.
5. Run the local checks before opening a pull request:

   ```bash
   ruff check .
   ruff format --check .
   pytest
   python3 -m compileall custom_components/estofex
   ```

## Scope

Version `0.4.x` is focused on release quality and bug fixes. Larger features such as AI summaries, Mesoscale Discussions, LightningMaps, KNMI, DWD, ESWD, and a custom Lovelace card should target a later release.

## Privacy

Do not add diagnostics, logs, or attributes that expose credentials, tokens, precise Home Assistant location, private URLs, or local filesystem paths.
