# Contributing

Contributions are made through pull requests. By opening one you agree that your code is released under the
[MIT licence](LICENSE) and that any data you add keeps the licence of its source ([LICENSING.md](LICENSING.md)).

## Adding or changing data

- Name the source: stable URL, commit or DOI, locator, licence and the SHA-256 of every original file. Public
  availability is not redistribution permission; a source without an established licence is added to the registry as a
  reference only ([docs/source-catalogue.md](docs/source-catalogue.md)).
- Convert values to SI and keep the published unit as `original`. Leave an unknown value out or `null`, never zero.
- State the operating conditions (frequency, temperature, flux density, waveform, DC bias) or flag their absence.
- Keep data classes apart: experimental measurements, manufacturer datasheet curves, derived tables and fitted
  parameters are separate records. No model prediction is stored here; models belong in
  [AIPE-Magnetics-Design](https://github.com/FulongLi/AIPE-Magnetics-Design).
- Do not edit `data/normalized`, `data/canonical` or `data/reports` by hand. Change the importer under
  `src/aipe_magnetics_database/ingest/sources/` and regenerate ([docs/ingestion.md](docs/ingestion.md)).
- Never change an observation to make a check pass. Suspect values are kept verbatim and flagged.
- Synthetic examples stay marked `synthetic` and out of the canonical catalogue.

## Checks to run

```sh
python -m pip install -e ".[dev]"
python -m pytest -q                 # unit, data, ingestion, interface and release tests
aipe-magnetics-db validate          # every committed record against schema v0.2, references, canonical layer
aipe-magnetics-db quality           # consistency and plausibility checks; rewrites the quality report
```

A re-import of a committed source must be byte-identical (`aipe-magnetics-db refresh --source <id>`); CI checks this.

## Schema and interfaces

A change to schema semantics needs a new schema version, a migration note and tests for valid and invalid input. The
v0.1 files (`schemas/magnetic-record.schema.json`, `scripts/validate.py`, `importers/json_record.py`,
`tests/test_records.py`, `examples/synthetic-transformer.json`) are frozen and kept byte-identical; do not edit them.
The Python API, CLI and MCP tools are read-only and return units and provenance with every value
([docs/api.md](docs/api.md)).

Published raw files on Hugging Face are immutable. Releases are reviewed by a person before they are merged or
published; nothing is auto-merged.
