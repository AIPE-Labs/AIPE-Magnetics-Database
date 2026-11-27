# Hugging Face dataset integration

The data live in three layers:

| Layer | Repository | Role |
| --- | --- | --- |
| 1 | [`FulongLi/AIPE-Magnetics-Dataset`](https://huggingface.co/datasets/FulongLi/AIPE-Magnetics-Dataset) (Hugging Face) | storage: original files, normalised v0.2 records, large tables, manifests, versioned releases |
| 2 | this repository | Database Manager: source registry, acquisition, importers, validation, quality checks, publishing, API / CLI / MCP, Data Explorer |
| 3 | [AIPE-Magnetics-Design](https://github.com/FulongLi/AIPE-Magnetics-Design) | engineering application; reads data only through this package |

GitHub keeps the code, the registry, the normalised records small enough for Git (bundled into the wheel for offline
use) and `data/huggingface.json`, which pins the published release. Large sidecars and the original files live on
Hugging Face only.

## Dataset layout

```
raw/<source-id>/files/...          original files, byte-for-byte (immutable)
raw/<source-id>/SOURCES.json       pinned URL, version and SHA-256 of every original; upstream LICENSE / NOTICE beside it
normalized/v0.2/<source-id>/       index.json, record shards, datasets/, tables/ and tables-local/ sidecars
tabular/v0.2/<config>/<source-id>.parquet   the same values as named, typed columns (see "Tabular view")
manifests/sources.json             every investigated source: licence, status, published or not and why
manifests/dataset-index.json       per-source counts, table rows, sizes, formats, licence, citation, retrieval date
manifests/checksums.json           SHA-256 and size of every file
manifests/quality-report.json      automated checks (see docs/quality-summary.md)
README.md, LICENSE.md              dataset card, per-source licences
```

`<source-id>` is the registry id (`princeton_magnet`, `openmagnetics_mas`, ...). Only sources whose status is
`integrated` and whose licence permits redistribution are staged (`hub.stage.publishable`); the rest appear in
`manifests/sources.json` as metadata only. Records are copied unchanged, so a record's `rows_file` resolves under its
source prefix on the Hub exactly as in `data/normalized/<directory>/`.

## Tabular view

The normalised records are the authoritative form, but their table rows are JSON arrays without column names, which
`datasets.load_dataset`, the Hugging Face dataset viewer, pandas and DuckDB cannot read. `hub stage` therefore also
writes the same values as Parquet (`hub/tabular.py`, layout `aipe.magnetics.tabular/0.1`), and the dataset card
declares one config per table:

| Config | One row per |
| --- | --- |
| `materials` | source material record: identity, class, the properties it reports |
| `material_properties` | property value with its conditions (temperature, frequency, field, flux density) |
| `cores` | core shape or manufacturer part |
| `measurements` | measurement record: quantity, data class, condition ranges, row count, `rows_published` |
| `core_loss`, `complex_permeability`, `bh_curve`, ... | row of the tables of that quantity |

```python
from datasets import load_dataset
rows = load_dataset("FulongLi/AIPE-Magnetics-Dataset", "core_loss", split="train")
```

- Values are the SI values of the records; nothing is computed, interpolated or dropped. Units and definitions are in
  the dataset card, in `manifests/dataset-index.json` (`tabular.configs`) and in the Parquet field metadata.
- Every row carries `measurement_id`, `material_id`, `material`, `data_class`, `status`, `source_id` and `license`.
  `status` is `primary`, `duplicate` or `derived_view`; keep `primary` to avoid counting a table twice.
- One file per source and config, so each file keeps the licence of its source.
- The columns of a quantity config are the union over every publishable source; a column that a record does not report
  is null.
- A table whose row sidecar is not in the release is listed in `measurements` with `rows_published = false`, and the
  card states the number of rows that are published.

The view needs `pyarrow` at staging time (extra `hub`); `hub stage --no-tabular` leaves it out.

## Publishing (GitHub Actions, Trusted Publisher)

`.github/workflows/publish-huggingface.yml` runs on manual dispatch only:

1. **stage** (no publishing rights): restores the large `tables-local/` sidecars from pinned transfer assets
   (`hub restore-tables`), validates every record, downloads the pinned raw inputs into the SHA-256 verifying cache,
   builds the release tree (`hub stage`), re-hashes it (`hub verify-stage`) and fails on quality errors.
2. **publish** (`permissions: id-token: write`, `HF_OIDC_RESOURCE=datasets/FulongLi/AIPE-Magnetics-Dataset`):
   `huggingface_hub` exchanges the GitHub OIDC token for a one-hour token scoped to the dataset. No HF token is
   stored in GitHub and none is printed. `hub publish` then
   * re-verifies the stage, lists the Hub files and skips identical ones (repeated runs upload nothing),
   * aborts if any `raw/` path exists on the Hub with different bytes (raw is immutable) and never deletes anything,
   * uploads with `upload_folder` (resumable: committed files are skipped, Xet deduplicates uploaded chunks),
   * verifies the SHA-256 (LFS/Xet) or Git blob id and size of every file at the resulting revision.

   Modes: `branch` (default) publishes the release to a Hub branch (`staging`) for review without touching `main`;
   `main` then publishes the same release to `main` (a repeat upload transfers almost nothing). `pr` opens a Hub pull
   request and works only with a user token: **Trusted Publisher tokens may write branches but are refused when
   opening pull requests** (403 on `preupload?create_pr=1`, 401 on the discussions endpoint; observed 2026-11-07).

Inputs: `mode` (`branch`, `main` or `pr`), `branch` (default `staging`), `merge` (pr mode), `sources` (subset), `dry_run`
(authenticate and plan only). A push to the branch `hf-publish/test` publishes only Zenodo 21626116 to the Hub branch
`ci-test` - the test publication; the first one succeeded at commit `3c9057f6` (20 files verified).

The Trusted Publisher on the dataset (Settings -> Trusted Publishers -> GitHub Actions) must match
`repository = FulongLi/AIPE-Magnetics-Database`, `workflow = publish-huggingface.yml` and, if a branch is set, the
branch the workflow is dispatched on (`main`). It must not be read-only. On a mismatch the token exchange fails with
`invalid_grant`; the job summary then lists the claims the run presented.

## Recording a release in GitHub

```sh
aipe-magnetics-db hub sync --revision main     # resolve to the exact commit, verify every file, write data/huggingface.json
aipe-magnetics-db hub status
```

`data/huggingface.json` holds the dataset repository, the exact commit, per-source prefixes and the SHA-256 of every
published file; it is bundled into the wheel. `aipe-magnetics-db quality` compares GitHub's normalised files with it
(`hub_consistency`).

## Reading published data

Bundled data work offline as before. A table that is only on Hugging Face (for example the 81 MAS B-H cycles in
`tables-local/`) is downloaded on request from `resolve/<exact commit>/<path>`, verified against the SHA-256 in
`data/huggingface.json` *and* the record's `rows_sha256`, and cached in `AIPE_MAGNETICS_CACHE` (default
`~/.cache/aipe-magnetics`). No account or `huggingface_hub` is needed.

```sh
AIPE_MAGNETICS_ALLOW_DOWNLOAD=1 aipe-magnetics-db measurements table measurement.mas-dmegc-dmr95-0400-bh-cycle --limit 5
aipe-magnetics-db hub fetch measurement.mas-dmegc-dmr95-0400-bh-cycle    # download once, then offline
```

```python
db.get_table("measurement.mas-dmegc-dmr95-0400-bh-cycle", allow_download=True)
```

## Local commands

| Command | Purpose |
| --- | --- |
| `hub stage --out DIR [--source ID] [--allow-download] [--no-tabular]` | build the release tree, including the tabular view |
| `hub verify-stage DIR` | re-hash a stage against its checksums |
| `hub publish DIR [--mode branch|main|pr] [--branch NAME] [--merge] [--dry-run]` | publish (needs Hub write access; normally run by the workflow) |
| `hub sync [--revision REV]` | record a verified release in `data/huggingface.json` |
| `hub restore-tables [--allow-download]` | restore `tables-local/` sidecars from pinned transfer assets |
| `quality` | run the quality checks; writes `data/reports/quality-report.json` and `docs/quality-summary.md` |
