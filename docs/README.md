# Documentation

This documentation describes the implementation in this repository. Start with
high-level design to understand the system, then use the low-level documents when
changing or debugging it. Installation, entity names, event payloads and dashboard
examples remain in the [project README](../README.md).

## Reading paths

| Question | Document |
| --- | --- |
| What does the integration do, and what are its boundaries? | [System overview](high-level/overview.md) |
| How do the main parts work together, and why? | [Architecture](high-level/architecture.md) |
| Which modules and data contracts should I change? | [Components and data](low-level/components-and-data.md) |
| What happens during refresh, failure, expiry and cleanup? | [Runtime behavior](low-level/runtime.md) |
| How do I verify a change? | [Development and testing](low-level/development.md) |
| How do I install or operate it? | [User guide](../README.md#installation) |
| What changed between releases? | [Changelog](../CHANGELOG.md) |

## Diagrams

Mermaid diagrams are embedded directly in the Markdown source:

- [System structure and entry lifecycle](high-level/architecture.md)
- [Forecast snapshot relationships](low-level/components-and-data.md#core-data-contracts)
- [Refresh decisions](low-level/runtime.md#refresh-decision-flow)
- [Combined warning transitions](low-level/runtime.md#combined-warning-transitions)

Use a Markdown viewer with Mermaid support to render them. The surrounding prose
and tables also explain the behavior when a viewer only displays the diagram code.
Update diagrams together with the behavior they describe.

## Structure and maintenance

```text
docs/
├── README.md
├── high-level/
│   ├── overview.md
│   └── architecture.md
├── low-level/
│   ├── components-and-data.md
│   ├── runtime.md
│   └── development.md
└── images/
```

High-level documents explain purpose, boundaries and design decisions. Low-level
documents describe implementation contracts and edge cases, with links to source
and tests. Function-by-function reference documentation belongs in the code.

Update the relevant document in the same change as the behavior it describes.
Keep installation and public entity/event examples in the project README rather
than maintaining duplicate lists here. Record release changes in the changelog;
keep planned features separate from implemented behavior. Add a separate design
decision document only when a substantial change needs alternatives and rationale.
