"""Dataset card (``README.md``) of the Hugging Face release, generated from the release manifests."""

from __future__ import annotations

from typing import Any

HF_LICENSE_IDS = {"MIT": "mit", "Apache-2.0": "apache-2.0", "CC-BY-4.0": "cc-by-4.0", "GPL-3.0-only": "gpl-3.0", "CC0-1.0": "cc0-1.0",
                  "CC-BY-SA-4.0": "cc-by-sa-4.0", "BSD-3-Clause": "bsd-3-clause", "ODbL-1.0": "odbl"}


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024
    return str(n)


INSTALL = 'pip install "aipe-magnetics-database @ git+https://github.com/AIPE-Labs/AIPE-Magnetics-Database.git"'


def _table_rows(counts: dict[str, int]) -> int:
    """Rows of measurement tables in an index ``table_rows`` mapping (waveform samples and sequences are not table rows)."""
    return sum(v for k, v in counts.items() if not k.startswith("waveform_"))


def _size_category(rows: int) -> str:
    for limit, label in ((1_000, "n<1K"), (10_000, "1K<n<10K"), (100_000, "10K<n<100K"), (1_000_000, "100K<n<1M"), (10_000_000, "1M<n<10M")):
        if rows < limit:
            return label
    return "10M<n<100M"


def _configs_yaml(tabular: dict[str, Any] | None) -> list[str]:
    """``configs:`` front matter: one config per tabular table, each a glob over its per-source Parquet files."""
    if not tabular or not tabular["configs"]:
        return ["viewer: false"]
    lines = ["configs:"]
    for name in tabular["configs"]:
        lines += [f"- config_name: {name}", "  data_files:", "  - split: train", f"    path: {tabular['prefix']}{name}/*.parquet"]
        if name == tabular.get("default_config"):
            lines.append("  default: true")
    return lines


def _tabular_section(tabular: dict[str, Any] | None, repo_id: str) -> list[str]:
    if not tabular or not tabular["configs"]:
        return []
    example = tabular.get("default_config") or next(iter(tabular["configs"]))
    lines = ["## Load it", "",
             "The tabular view holds the same values as named, typed Parquet columns in SI units, one config per table. It needs no",
             "AIPE code:", "", "```python", "from datasets import load_dataset",
             f'rows = load_dataset("{repo_id}", "{example}", split="train")',
             f'index = load_dataset("{repo_id}", "measurements", split="train")   # what exists, with condition ranges',
             "```", "",
             "Every row names its `measurement_id`, `source_id`, `data_class` and `license`. Filter on `data_class` to keep experimental",
             "measurements apart from manufacturer datasheet curves, and on `status == \"primary\"` to avoid counting a table twice",
             "(`duplicate` and `derived_view` rows repeat or derive from another record). A column that a record does not report is null.",
             "", "| Config | Rows | Content | Columns (SI unit) |", "| --- | --- | --- | --- |"]
    keys = {"measurement_id", "material_id", "material", "data_class", "status", "source_id", "license"}
    for name, config in tabular["configs"].items():
        shown = [c for c in config["columns"] if c["name"] not in keys or name in ("materials", "material_properties", "cores", "measurements")]
        cols = ", ".join(f"`{c['name']}`" + (f" ({c['unit']})" if c["unit"] and c["unit"] != "1" else "") for c in shown)
        lines.append(f"| `{name}` | {config['rows']:,} | {config['description']} | {cols} |")
    lines += ["", "The quantity configs also carry `measurement_id`, `material_id`, `material`, `data_class`, `status`, `source_id` and `license`.",
              "Each file `" + tabular["prefix"] + "<config>/<source-id>.parquet` holds the rows of one source and keeps that source's licence.", ""]
    return lines


def dataset_card(index: dict[str, Any], sources: list[dict[str, Any]]) -> str:
    published = index["sources"]
    licences = sorted({s["license"] for s in published})
    totals = index["totals"]
    described = totals.get("table_rows_described", _table_rows(totals["table_rows"]))
    rows = totals.get("table_rows_published", described)
    withheld = totals.get("tables_not_published", 0)
    rows_text = f"{rows:,} table rows"
    if rows != described:
        rows_text += (f" ({described:,} are described by the records; the rows of {withheld:,} large regenerated tables are not in this release"
                      " and are marked `rows_published = false`)")
    sequences = totals["table_rows"].get("waveform_sequences")
    if sequences and not totals.get("waveform_files_not_published"):
        rows_text += f", {sequences:,} sampled waveform sequences ({totals['table_rows'].get('waveform_samples', 0):,} samples, HDF5)"
    tabular = index.get("tabular")
    repo_id = index.get("repo_id", "AIPE-Labs/AIPE-Magnetics-Dataset")
    q = index["quality_summary"]
    lines = [
        "---",
        "license: other",
        "license_name: per-source-licences",
        "license_link: LICENSE.md",
        "pretty_name: AIPE Magnetics Dataset",
        "language:",
        "- en",
        "tags:",
        "- magnetics", "- power-electronics", "- core-loss", "- ferrite", "- magnetic-materials", "- physics",
        "size_categories:",
        f"- {_size_category(rows)}",
        *_configs_yaml(tabular),
        "---",
        "",
        "# AIPE Magnetics Dataset",
        "",
        "Original files and standardised records of open soft-magnetic material and core data for power electronics: material",
        "properties, core shapes and parts, and measured core loss, complex permeability, permittivity and B-H tables. This",
        "repository is the storage layer; it is built, validated and published by the",
        "[AIPE Magnetics Database](https://github.com/AIPE-Labs/AIPE-Magnetics-Database) (Python API, CLI, MCP tools,",
        "[Data Explorer](https://aipe-labs.github.io/AIPE-Magnetics-Database/)).",
        "",
        f"This release: {len(published)} sources, " + ", ".join(f"{v:,} {k.replace('_', ' ')}" for k, v in totals["record_counts"].items())
        + f" records, {rows_text}; raw {_fmt_bytes(totals['raw_bytes'])}, normalised {_fmt_bytes(totals['normalized_bytes'])}.",
        f"Built by `aipe-magnetics-database` {index['builder']['version']} from commit `{(index['builder'].get('commit') or 'unknown')[:12]}`.",
        "",
        *_tabular_section(tabular, repo_id),
        "## Layout",
        "",
        "| Path | Content |",
        "| --- | --- |",
        *([f"| `{tabular['prefix']}<config>/<source-id>.parquet` | tabular view of the normalised records: named, typed columns in SI units |"]
          if tabular and tabular["configs"] else []),
        "| `raw/<source-id>/files/` | original files, byte-for-byte, as published upstream (immutable) |",
        "| `raw/<source-id>/SOURCES.json` | pinned URL, version and SHA-256 of every original file; upstream LICENSE / NOTICE alongside |",
        "| `normalized/v0.2/<source-id>/` | AIPE Magnetic Data Schema v0.2 records: `index.json`, JSONL shards, `datasets/`, table sidecars (`tables/`, `tables-local/`) |",
        "| `manifests/sources.json` | every investigated source, its licence, status, and what is (not) published and why |",
        "| `manifests/dataset-index.json` | per-source record counts, table rows, sizes, formats, licence and citation |",
        "| `manifests/checksums.json` | SHA-256 and size of every file in the release |",
        "| `manifests/quality-report.json` | automated consistency and plausibility checks |",
        "",
        "## Records",
        "",
        "One JSON record per line, SI units with the published unit kept as `original`; a missing value is omitted, never",
        "zero. `extensions[\"aipe.data\"][\"data_class\"]` keeps experimental measurements, manufacturer datasheet curves,",
        "manufacturer-tool exports, derived views and fitted parameters apart. Tables (`extensions[\"aipe.table\"]`) list",
        "their columns (SI unit, original unit, definition); rows are JSON arrays in a sidecar named by `rows_file` and",
        "verified by `rows_sha256`. Schema: [docs/data-standard-v0.2.md](https://github.com/AIPE-Labs/AIPE-Magnetics-Database/blob/main/docs/data-standard-v0.2.md).",
        "",
        "The Python package adds unit-checked queries, provenance lookups, a CLI and MCP tools for AI agents (not on PyPI yet):",
        "",
        "```python",
        f"# {INSTALL}",
        "import aipe_magnetics_database.api as db",
        "rows = db.get_table(\"measurement.princeton-magnet-n87-core-loss\", frequency=\"100 kHz\", temperature=\"90 degC\")",
        "```",
        "",
        f"A single file: `huggingface_hub.hf_hub_download(\"{repo_id}\", \"normalized/v0.2/princeton_magnet/index.json\", repo_type=\"dataset\")`.",
        "",
        "## Sources and licences",
        "",
        "Each source keeps its own licence; nothing is relicensed. Cite the original work.",
        "",
        "| Source | Licence | Version | Records | Table rows | Raw | Citation |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in published:
        version = str(s.get("version") or "-")
        version = version[:12] if len(version) == 40 else version
        rec = ", ".join(f"{k} {v:,}" for k, v in s["record_counts"].items())
        total = s.get("table_rows_described", _table_rows(s["table_rows"]))
        shown = s.get("table_rows_published", total)
        cell = f"{shown:,}" if shown == total else f"{shown:,} of {total:,}"
        if s["table_rows"].get("waveform_sequences"):
            cell = (f"{cell}; " if total else "") + f"{s['table_rows']['waveform_sequences']:,} waveform sequences"
        lines.append(f"| [{s['title']}]({s['url']}) (`{s['id']}`) | {s['license']} | {version} | {rec} | {cell} | "
                     f"{s['raw_files']} files, {_fmt_bytes(s['raw_bytes'])} | {(s.get('citation') or '-').replace('|', '/')} |")
    excluded = [s for s in sources if not s.get("huggingface", {}).get("published")]
    lines += ["", f"{len(excluded)} further investigated sources are listed in `manifests/sources.json` as metadata only (licence does not",
              "permit redistribution, not established, or no pinnable download). Public availability is not redistribution permission.",
              "", "## Quality", "",
              f"Automated checks over {q['records_checked']:,} records and {q['rows_checked']:,} table rows: {q['errors']:,} errors, "
              f"{q['warnings']:,} warnings ({', '.join(q['checks_flagged']) or 'none flagged'}). Flags mark values to review; no",
              "observation is changed. Schema validity is not proof of experimental accuracy.", "",
              "## Licence summary", "", "Licences present: " + ", ".join(f"`{x}`" for x in licences) + ". See `LICENSE.md`.", ""]
    return "\n".join(lines)


def licence_file(index: dict[str, Any]) -> str:
    lines = ["# Licences", "", "This dataset aggregates files under different licences. Each `raw/<source-id>/` and",
             "`normalized/v0.2/<source-id>/` subtree and each `tabular/v0.2/<config>/<source-id>.parquet` file is licensed by",
             "its source as listed below; the upstream licence text is kept next to the original files where the source",
             "provides one.", "", "| Source | Licence | Redistribution |", "| --- | --- | --- |"]
    for s in index["sources"]:
        lines.append(f"| `{s['id']}` | {s['license']} | {s.get('redistribution') or 'permitted'} |")
    lines += ["", "GPL-3.0 subtrees: modified (normalised) forms of the upstream files; the original files are included under",
              "`raw/<source-id>/files/` as the corresponding source.", "",
              "AIPE's own contribution (selection, arrangement, normalisation, quality flags, manifests and this card) is offered",
              "under CC BY 4.0 to the extent that AIPE holds rights in it; this adds no restriction to the upstream data.", ""]
    return "\n".join(lines)


__all__ = ["dataset_card", "licence_file"]
