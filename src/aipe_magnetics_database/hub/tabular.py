"""Tabular (Parquet) view of a Hugging Face release: ``tabular/v0.2/<config>/<source-id>.parquet``.

The normalised records are the authoritative form, but their table rows are JSON arrays without column names, which
generic tools (``datasets.load_dataset``, the Hugging Face dataset viewer, pandas, DuckDB) cannot read. This module
writes the same values as named, typed columns:

* ``materials``            one row per source material record (identity, class, which properties it reports)
* ``material_properties``  one row per property value with its conditions (long format)
* ``cores``                one row per core shape or part
* ``measurements``         one row per measurement record: quantity, data class, condition ranges, row count
* one config per table quantity (``core_loss``, ``complex_permeability``, ``bh_curve`` ...): the table rows

Rules:

* Nothing is computed, interpolated or dropped: every value is the SI value of the normalised record. A column
  that a record does not have is null.
* One file per source and config, so each file keeps the licence of its source (column ``license``).
* All files of a config share one schema: the union of the columns of that quantity over every publishable source
  of the checkout, independent of the sources selected for a release.
* A measurement whose row sidecar is not available is listed in ``measurements`` with ``rows_published = false``
  and contributes no rows.

Requires ``pyarrow`` (extra ``hub``); reading the files needs no AIPE code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterator

from aipe_magnetics_database.common.errors import DataIntegrityError, UnsupportedOperationError
from aipe_magnetics_database.hub.layout import SCHEMA_DIR

TABULAR_LAYOUT = "aipe.magnetics.tabular/0.1"
TABULAR_PREFIX = f"tabular/{SCHEMA_DIR}"

#: identity columns that precede the table columns of every quantity config
ROW_KEYS: tuple[tuple[str, str], ...] = (
    ("measurement_id", "measurement record that holds this row (see the measurements config and normalized/)"),
    ("material_id", "source material record of the specimen"),
    ("material", "material name shared by every source that measured the same manufacturer grade"),
    ("data_class", "experimental_measurement, manufacturer_datasheet, manufacturer_tool_export, derived_from_measurement ..."),
    ("status", "primary, duplicate (same rows as another record) or derived_view (computed from another record)"),
    ("source_id", "source of the record (manifests/sources.json)"),
    ("license", "licence of the source, which applies to this row"),
)
CONDITION_UNITS = {"temperature": "K", "frequency": "Hz", "field": "A/m", "flux_density_peak": "T"}
RANGE_COLUMNS = ("frequency", "temperature", "flux_density_peak", "dc_bias_field")
CONFIG_DESCRIPTIONS = {
    "materials": "one row per source material record",
    "material_properties": "one row per material property value with its conditions",
    "cores": "one row per core shape or manufacturer part",
    "measurements": "one row per measurement record: quantity, data class, condition ranges and row count",
}
CONFIG_ORDER = ("materials", "material_properties", "cores", "measurements")
DEFAULT_CONFIG = "core_loss"


def tabular_path(config: str, source_id: str) -> str:
    return f"{TABULAR_PREFIX}/{config}/{source_id}.parquet"


def _pyarrow() -> tuple[Any, Any]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise UnsupportedOperationError("the tabular (Parquet) view needs pyarrow: pip install 'aipe-magnetics-database[hub]', "
                                         "or stage with tabular=False / --no-tabular") from exc
    return pa, pq


def _jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _shards(base: Path, index: dict[str, Any], group: str) -> Iterator[dict[str, Any]]:
    for rel in index["shards"].get(group, []):
        yield from _jsonl(base / rel)


def _source_dir(root: Path, source: dict[str, Any]) -> tuple[Path, dict[str, Any]] | None:
    base = root / "data" / "normalized" / source["directory"]
    if not (base / "index.json").is_file():
        return None
    return base, json.loads((base / "index.json").read_text(encoding="utf-8"))


def _data(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("extensions", {}).get("aipe.data") or {}


def _other_extension(record: dict[str, Any]) -> dict[str, Any]:
    """The source-specific extension of a record (e.g. ``aipe.mas``), without ``aipe.data`` / ``aipe.table``."""
    merged: dict[str, Any] = {}
    for key, value in sorted(record.get("extensions", {}).items()):
        if key not in ("aipe.data", "aipe.table") and isinstance(value, dict):
            merged.update(value)
    return merged


def _flags(record: dict[str, Any]) -> list[str]:
    return list((record.get("quality") or {}).get("flags") or [])


def _number(value: Any, where: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataIntegrityError(f"{where}: expected a number, found {value!r}")
    return float(value)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)


def _canonical(root: Path) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    """``({source material record: shared material name}, {measurement id: canonical index entry})``."""
    names: dict[str, str] = {}
    measurements: dict[str, dict[str, Any]] = {}
    base = root / "data" / "canonical"
    if (base / "materials.jsonl").is_file():
        for record in _jsonl(base / "materials.jsonl"):
            for member in (record.get("extensions", {}).get("aipe.canonical") or {}).get("members", []):
                names[member["record"]] = record["name"]
    if (base / "measurements.jsonl").is_file():
        for entry in _jsonl(base / "measurements.jsonl"):
            measurements[entry["id"]] = entry
    return names, measurements


def quantity_schemas(root: Path, sources: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """``{quantity: [column spec]}``: the union of the table columns of each quantity over ``sources``, first seen first."""
    schemas: dict[str, dict[str, dict[str, Any]]] = {}
    for source in sources:
        found = _source_dir(root, source)
        if found is None:
            continue
        base, index = found
        for record in _shards(base, index, "measurements"):
            table = record.get("extensions", {}).get("aipe.table")
            if not table:
                continue
            spec = schemas.setdefault(table["quantity"], {})
            for col in table["columns"]:
                unit = col.get("unit") or ""
                known = spec.get(col["name"])
                if known is None:
                    spec[col["name"]] = {"name": col["name"], "unit": unit, "type": "double" if unit else "string",
                                         "definition": col.get("definition") or ""}
                elif known["unit"] != unit:
                    raise DataIntegrityError(f"{record['id']}: column {col['name']!r} has unit {unit!r} but {known['unit']!r} in another "
                                             f"{table['quantity']} table; one config cannot hold both")
    reserved = {name for name, _ in ROW_KEYS}
    for quantity, spec in schemas.items():
        clash = reserved & set(spec)
        if clash:
            raise DataIntegrityError(f"{quantity}: table column(s) {sorted(clash)} collide with the identity columns")
    return {quantity: list(spec.values()) for quantity, spec in schemas.items()}


def _rows(base: Path, record: dict[str, Any]) -> list[list[Any]] | None:
    """Rows of a measurement record, or ``None`` when its sidecar file is not in the data store."""
    table = record["extensions"]["aipe.table"]
    if table.get("rows") is not None:
        rows = table["rows"]
    else:
        path = base / table["rows_file"]
        if not path.is_file():
            return None
        with path.open(encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
    if len(rows) != table["row_count"]:
        raise DataIntegrityError(f"{record['id']}: {len(rows)} rows read, record declares {table['row_count']}")
    return rows


class _Writer:
    """Writes one Parquet file per (config, source) into ``out`` and keeps the per-config statistics."""

    def __init__(self, out: Path):
        self.pa, self.pq = _pyarrow()
        self.out = out
        self.files: list[str] = []
        self.configs: dict[str, dict[str, Any]] = {}

    def field(self, name: str, kind: str, unit: str = "", definition: str = "") -> Any:
        pa = self.pa
        types = {"string": pa.string(), "double": pa.float64(), "int": pa.int64(), "bool": pa.bool_(), "strings": pa.list_(pa.string())}
        meta = {k: v for k, v in (("unit", unit), ("definition", definition)) if v}
        return pa.field(name, types[kind], metadata=meta or None)

    def write(self, config: str, source: dict[str, Any], columns: list[tuple[str, str, str, str]], data: dict[str, list[Any]]) -> int:
        """``columns``: ``(name, kind, unit, definition)``; ``data``: one list per column. Returns the rows written (0 = no file)."""
        n = len(data[columns[0][0]])
        if n == 0:
            return 0
        pa = self.pa
        schema = pa.schema([self.field(*c) for c in columns],
                           metadata={"layout": TABULAR_LAYOUT, "config": config, "source_id": source["id"], "license": source["license"]})
        table = pa.Table.from_arrays([pa.array(data[c[0]], type=schema.field(c[0]).type) for c in columns], schema=schema)
        rel = tabular_path(config, source["id"])
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pq.write_table(table, path, compression="zstd", version="2.6", write_statistics=True)
        self.files.append(rel)
        entry = self.configs.setdefault(config, {"description": CONFIG_DESCRIPTIONS.get(config, f"rows of the {config} tables"), "rows": 0,
                                                 "files": {}, "columns": [{"name": c[0], "type": c[1], "unit": c[2], "definition": c[3]}
                                                                          for c in columns]})
        entry["rows"] += n
        entry["files"][rel] = n
        return n


def _material_tables(writer: _Writer, source: dict[str, Any], base: Path, index: dict[str, Any], names: dict[str, str]) -> None:
    common = [("data_class", "string", "", ROW_KEYS[3][1]), ("source_id", "string", "", ROW_KEYS[5][1]),
              ("license", "string", "", "licence of the source, which applies to this row")]
    mat_cols = [("material_id", "string", "", "source material record"), ("name", "string", "", "name as given by the source"),
                ("material", "string", "", ROW_KEYS[2][1]), ("manufacturer", "string", "", "manufacturer, where the source states it"),
                ("grade", "string", "", "material grade"), ("material_class", "string", "", "ferrite_mnzn, ferrite_nizn, nanocrystalline ..."),
                ("description", "string", "", ""), ("properties", "strings", "", "property names this record reports (see material_properties)"),
                ("quality_flags", "strings", "", "quality flags of the record"), *common]
    prop_cols = [("material_id", "string", "", "source material record"), ("material", "string", "", ROW_KEYS[2][1]),
                 ("property", "string", "", "property name (schema v0.2 material property)"),
                 ("value", "double", "", "value in the SI unit of column unit"), ("unit", "string", "", "SI unit of value"),
                 ("original_value", "double", "", "value as published"), ("original_unit", "string", "", "unit as published"),
                 ("temperature", "double", "K", "temperature the value applies to"), ("frequency", "double", "Hz", "frequency the value applies to"),
                 ("field", "double", "A/m", "magnetic field strength the value applies to"),
                 ("flux_density_peak", "double", "T", "peak flux density the value applies to"),
                 ("note", "string", "", "qualification stated by the source or the importer"), *common]
    mats: dict[str, list[Any]] = {c[0]: [] for c in mat_cols}
    props: dict[str, list[Any]] = {c[0]: [] for c in prop_cols}

    def add_value(record: dict[str, Any], name: str, item: dict[str, Any]) -> bool:
        value = item.get("value")
        if not isinstance(value, dict) or isinstance(value.get("value"), bool) or not isinstance(value.get("value"), (int, float)):
            return False
        original = value.get("original") or {}
        row = {"material_id": record["id"], "material": names.get(record["id"], record["name"]), "property": name,
               "value": float(value["value"]), "unit": value.get("unit"),
               "original_value": _number(original.get("value"), f"{record['id']}.{name}.original"), "original_unit": original.get("unit"),
               "note": item.get("note"), "data_class": _data(record).get("data_class"), "source_id": source["id"], "license": record["license"]}
        for cond, unit in CONDITION_UNITS.items():
            q = item.get(cond)
            if q is not None and q.get("unit") != unit:
                raise DataIntegrityError(f"{record['id']}.{name}: condition {cond} in {q.get('unit')!r}, expected {unit!r}")
            row[cond] = None if q is None else _number(q.get("value"), f"{record['id']}.{name}.{cond}")
        for key, values in props.items():
            values.append(row.get(key))
        return True

    for record in _shards(base, index, "materials"):
        reported = []
        for name, value in record["properties"].items():
            ok = False
            if isinstance(value, list):
                ok = any([add_value(record, name, item) for item in value if isinstance(item, dict)])
            elif isinstance(value, dict) and "value" in value:
                ok = add_value(record, name, value)
            elif isinstance(value, dict) and value.get("unit") and ("min" in value or "max" in value):
                for bound in ("min", "max"):
                    if value.get(bound) is not None:
                        ok = add_value(record, f"{name}_{bound}", {"value": {"value": value[bound], "unit": value["unit"]}}) or ok
            if ok:
                reported.append(name)
        row = {"material_id": record["id"], "name": record["name"], "material": names.get(record["id"], record["name"]),
               "manufacturer": _text(_other_extension(record).get("manufacturer")), "grade": record["properties"].get("grade"),
               "material_class": record["properties"].get("material_class"), "description": record["properties"].get("description"),
               "properties": reported, "quality_flags": _flags(record), "data_class": _data(record).get("data_class"),
               "source_id": source["id"], "license": record["license"]}
        for key, values in mats.items():
            values.append(row.get(key))
    writer.write("materials", source, mat_cols, mats)
    writer.write("material_properties", source, prop_cols, props)


def _core_table(writer: _Writer, source: dict[str, Any], base: Path, index: dict[str, Any]) -> None:
    cols = [("core_id", "string", "", "core record"), ("name", "string", "", ""), ("part_number", "string", "", ""),
            ("core_type", "string", "", "shape (dimensions of a core shape) or part (a manufacturer part: shape, material, gapping)"),
            ("family", "string", "", "shape family"), ("shape_type", "string", "", ""), ("manufacturer", "string", "", ""),
            ("material_id", "string", "", "material record of a part"), ("material_name", "string", "", "material name as given by the source"),
            ("shape_id", "string", "", "core record of the shape of a part"), ("shape_name", "string", "", ""),
            ("set_description", "string", "", ""), ("coating", "string", "", ""), ("number_stacks", "int", "", ""),
            ("production_status", "string", "", ""), ("gapping", "string", "", "JSON: gaps of a part, lengths in m"),
            ("dimensions_nominal_m", "string", "", "JSON: nominal dimensions in m, by dimension letter"),
            ("dimensions_range_m", "string", "", "JSON: tolerance range of each dimension in m"),
            ("description", "string", "", ""), ("quality_flags", "strings", "", "quality flags of the record"),
            ("data_class", "string", "", ROW_KEYS[3][1]), ("source_id", "string", "", ROW_KEYS[5][1]),
            ("license", "string", "", "licence of the source, which applies to this row")]
    data: dict[str, list[Any]] = {c[0]: [] for c in cols}
    for group, core_type in (("shapes", "shape"), ("cores", "part")):
        for record in _shards(base, index, group):
            p, ext = record["properties"], _other_extension(record)
            stacks = ext.get("number_stacks")
            row = {"core_id": record["id"], "name": record["name"], "part_number": p.get("part_number"), "core_type": core_type,
                   "family": ext.get("family"), "shape_type": ext.get("shape_type"), "manufacturer": ext.get("manufacturer"),
                   "material_id": (p.get("material_refs") or [None])[0], "material_name": ext.get("material_name"),
                   "shape_id": ext.get("shape_ref"), "shape_name": ext.get("shape_name"), "set_description": p.get("set_description"),
                   "coating": _text(ext.get("coating")), "number_stacks": stacks if isinstance(stacks, int) and not isinstance(stacks, bool) else None,
                   "production_status": _text(ext.get("status")),
                   "gapping": _text(ext["gapping"]) if ext.get("gapping") else None,
                   "dimensions_nominal_m": _text(ext["dimensions_nominal_m"]) if ext.get("dimensions_nominal_m") else None,
                   "dimensions_range_m": _text(ext["dimensions_range_m"]) if ext.get("dimensions_range_m") else None,
                   "description": p.get("description"), "quality_flags": _flags(record), "data_class": _data(record).get("data_class"),
                   "source_id": source["id"], "license": record["license"]}
            for key, values in data.items():
                values.append(row.get(key))
    writer.write("cores", source, cols, data)


def _measurement_tables(writer: _Writer, source: dict[str, Any], base: Path, index: dict[str, Any], names: dict[str, str],
                        canonical: dict[str, dict[str, Any]], schemas: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    idx_cols = [("measurement_id", "string", "", "measurement record"), ("name", "string", "", ""),
                ("quantity", "string", "", "table quantity; the rows are in the config of this name"),
                ("material_id", "string", "", ROW_KEYS[1][1]), ("material", "string", "", ROW_KEYS[2][1]),
                ("data_class", "string", "", ROW_KEYS[3][1]), ("status", "string", "", ROW_KEYS[4][1]),
                ("row_count", "int", "", "rows of the table"), ("rows_published", "bool", "", "false: the rows are not in this release"),
                ("columns", "strings", "", "table columns of this record"), ("units", "strings", "", "SI unit of each column ('' = text)"),
                *[(f"{c}_{b}", "double", {"frequency": "Hz", "temperature": "K", "flux_density_peak": "T", "dc_bias_field": "A/m"}[c],
                   f"{'lowest' if b == 'min' else 'highest'} {c.replace('_', ' ')} in the table") for c in RANGE_COLUMNS for b in ("min", "max")],
                ("method", "string", "", ""), ("specimen", "string", "", ""), ("description", "string", "", ""),
                ("quality_flags", "strings", "", "quality flags of the record"),
                ("source_id", "string", "", ROW_KEYS[5][1]), ("license", "string", "", "licence of the source, which applies to this row")]
    idx: dict[str, list[Any]] = {c[0]: [] for c in idx_cols}
    tables: dict[str, dict[str, list[Any]]] = {}
    stats = {"rows_published": 0, "rows_missing": 0, "tables_missing": 0}
    for record in _shards(base, index, "measurements"):
        table = record.get("extensions", {}).get("aipe.table")
        if not table:
            continue
        quantity, material_id = table["quantity"], record["properties"].get("material_ref")
        entry = canonical.get(record["id"], {})
        keys = {"measurement_id": record["id"], "material_id": material_id, "material": names.get(material_id), "data_class": _data(record).get("data_class"),
                "status": entry.get("status"), "source_id": source["id"], "license": record["license"]}
        rows = _rows(base, record)
        names_in = [c["name"] for c in table["columns"]]
        ranges: dict[str, float | None] = {}
        for c in RANGE_COLUMNS:
            cond = (entry.get("conditions") or {}).get(c) or {}
            lo, hi = cond.get("min"), cond.get("max")
            if lo is None and rows is not None and c in names_in:
                values = [r[names_in.index(c)] for r in rows if isinstance(r[names_in.index(c)], (int, float)) and not isinstance(r[names_in.index(c)], bool)]
                lo, hi = (min(values), max(values)) if values else (None, None)
            ranges[f"{c}_min"], ranges[f"{c}_max"] = lo, hi
        p = record["properties"]
        row = {**keys, "name": record["name"], "quantity": quantity, "row_count": table["row_count"], "rows_published": rows is not None,
               "columns": names_in, "units": [c.get("unit") or "" for c in table["columns"]], **ranges, "method": _text(p.get("method")),
               "specimen": _text(p.get("specimen")), "description": p.get("description"), "quality_flags": _flags(record)}
        for key, values in idx.items():
            values.append(row.get(key))
        if rows is None:
            stats["rows_missing"] += table["row_count"]
            stats["tables_missing"] += 1
            continue
        stats["rows_published"] += len(rows)
        spec = schemas[quantity]
        out = tables.setdefault(quantity, {name: [] for name in [k for k, _ in ROW_KEYS] + [c["name"] for c in spec]})
        position = {name: i for i, name in enumerate(names_in)}
        for key, value in keys.items():
            out[key].extend([value] * len(rows))
        for col in spec:
            i = position.get(col["name"])
            if i is None:
                out[col["name"]].extend([None] * len(rows))
            elif col["type"] == "double":
                where = f"{record['id']}.{col['name']}"
                out[col["name"]].extend(_number(r[i], where) for r in rows)
            else:
                out[col["name"]].extend(_text(r[i]) for r in rows)
    writer.write("measurements", source, idx_cols, idx)
    for quantity in sorted(tables):
        columns = [(name, "string", "", definition) for name, definition in ROW_KEYS]
        columns += [(c["name"], c["type"], c["unit"], c["definition"]) for c in schemas[quantity]]
        writer.write(quantity, source, columns, tables[quantity])
    return stats


def build_tabular(root: Path, sources: list[dict[str, Any]], out: Path, *, schema_sources: list[dict[str, Any]] | None = None,
                  log: Callable[[str], None] = print) -> dict[str, Any]:
    """Write the tabular view of ``sources`` (registry entries) below ``out``; returns its manifest section.

    ``schema_sources`` (default: ``sources``) are the sources whose columns define the schema of each quantity config.
    """
    writer = _Writer(Path(out))
    names, canonical = _canonical(root)
    schemas = quantity_schemas(root, schema_sources or sources)
    per_source: dict[str, dict[str, int]] = {}
    for source in sources:
        found = _source_dir(root, source)
        if found is None:
            continue
        base, index = found
        log(f"[{source['id']}] writing the tabular view ...")
        _material_tables(writer, source, base, index, names)
        _core_table(writer, source, base, index)
        per_source[source["id"]] = _measurement_tables(writer, source, base, index, names, canonical, schemas)
    order = [c for c in CONFIG_ORDER if c in writer.configs] + sorted(c for c in writer.configs if c not in CONFIG_ORDER)
    return {"layout": TABULAR_LAYOUT, "prefix": f"{TABULAR_PREFIX}/", "default_config": DEFAULT_CONFIG if DEFAULT_CONFIG in writer.configs else None,
            "configs": {c: writer.configs[c] for c in order}, "sources": per_source, "files": sorted(writer.files)}


__all__ = ["CONFIG_ORDER", "DEFAULT_CONFIG", "ROW_KEYS", "TABULAR_LAYOUT", "TABULAR_PREFIX", "build_tabular", "quantity_schemas", "tabular_path"]
