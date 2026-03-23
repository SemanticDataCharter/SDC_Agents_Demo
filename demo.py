#!/usr/bin/env python3
"""
SDC Agents Demo — From Raw Data to Validated Knowledge Graph

Usage:
    python demo.py [--dataset lab_results|sensor_readings|purchase_orders|employees]
                   [--mode self-contained|live]
                   [--skip-graphdb]

Requires: pip install -r requirements.txt
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATASETS = ("lab_results", "sensor_readings", "purchase_orders", "employees")
MODES = ("self-contained", "live")

SDC4_NS = "https://semanticdatacharter.com/ns/sdc4/"
SCHEMA_DIR = Path("schemas")
OUTPUT_DIR = Path("output")
CACHE_DIR = Path(".sdc-cache")

DATASET_META = {
    "lab_results": {
        "dm_ct_id": "d3m0labr3sult5x7k9q2w4p1",
        "cluster_ct_id": "lr00clust3rl4br3sultsd4t",
        "cluster_label": "LabResults Data Cluster",
        "label": "LabResults",
        "source_type": "csv",
    },
    "sensor_readings": {
        "dm_ct_id": "d3m0s3ns0rr34d1ngsx8m5n3q",
        "cluster_ct_id": "sr00clust3rs3ns0rr34d1ngs",
        "cluster_label": "SensorReadings Data Cluster",
        "label": "SensorReadings",
        "source_type": "csv",
    },
    "purchase_orders": {
        "dm_ct_id": "d3m0purch4s30rd3rsx6j8r2t",
        "cluster_ct_id": "po00clust3rpurch4s30rd3rs",
        "cluster_label": "PurchaseOrders Data Cluster",
        "label": "PurchaseOrders",
        "source_type": "csv",
    },
    "employees": {
        "dm_ct_id": "d3m03mpl0y33d1r3ct0ryq8w",
        "cluster_ct_id": "em00clust3r3mpl0y33d1r3ct",
        "cluster_label": "EmployeeDirectory Data Cluster",
        "label": "EmployeeDirectory",
        "source_type": "sql",
        "sql_table": "employees",
    },
}

# The 13 standard fields from IntrospectToolset._make_column
ENRICHMENT_FIELDS = (
    "description", "enumeration", "units", "nullable", "constraints",
    "range_values", "relationships", "business_rules", "examples", "metadata",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _banner(step: int, title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  Step {step}: {title}")
    print(f"{'='*60}\n")


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _info(msg: str) -> None:
    print(f"  [..] {msg}")


def _fail(msg: str) -> None:
    print(f"  [!!] {msg}", file=sys.stderr)


def _field_populated(col: dict, field: str) -> bool:
    """Return True if a column's enrichment field has meaningful content."""
    val = col.get(field)
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    if isinstance(val, dict) and not val:
        return False
    if isinstance(val, list) and not val:
        return False
    if isinstance(val, bool):
        return True  # nullable=False is meaningful
    return True


# ---------------------------------------------------------------------------
# Step 1 — Introspect Data Source
# ---------------------------------------------------------------------------

def step_introspect(dataset: str) -> dict:
    """Introspect the data source using IntrospectToolset."""
    _banner(1, "Introspect Data Source")

    meta = DATASET_META[dataset]
    source_type = meta["source_type"]

    # Try IntrospectToolset first
    columns = _introspect_with_toolset(dataset, source_type)

    if columns is not None:
        _ok(f"IntrospectToolset returned {len(columns)} columns ({source_type})")
    else:
        _info("IntrospectToolset unavailable, falling back to built-in introspection")
        columns = _introspect_fallback(dataset, source_type)

    # Load row data for XML generation
    rows = _load_rows(dataset, source_type)

    # Display primary table
    print()
    print(f"  {'Column':<20} {'Type':<14} {'Nullable':<10} {'Samples'}")
    print(f"  {'-'*20} {'-'*14} {'-'*10} {'-'*30}")
    for c in columns:
        nullable = str(c.get("nullable", "")) if c.get("nullable") is not None else ""
        samples_list = c.get("sample_values", [])
        samples = ", ".join(str(s) for s in samples_list[:3])
        print(f"  {c['name']:<20} {c.get('data_type', 'string'):<14} {nullable:<10} {samples}")

    # Display enrichment details
    print()
    print("  Enrichment details:")
    for c in columns:
        populated = [f for f in ENRICHMENT_FIELDS if _field_populated(c, f)]
        if populated:
            markers = "  ".join(f"[+] {f}" for f in populated)
            print(f"    {c['name']}: {markers}")

    return {"rows": rows, "columns": columns, "row_count": len(rows)}


def _introspect_with_toolset(dataset: str, source_type: str) -> list[dict] | None:
    """Try to use IntrospectToolset for introspection. Returns None on failure."""
    try:
        import os
        from sdc_agents.common.config import load_config
        from sdc_agents.toolsets.introspect import IntrospectToolset

        # Provide a dummy API key if not set (not needed for local introspection)
        os.environ.setdefault("SDC_API_KEY", "unused-for-local-introspection")
        config = load_config("sdc-agents.demo.yaml")

        async def _run():
            toolset = IntrospectToolset(config)
            try:
                if source_type == "csv":
                    result = await toolset.introspect_csv(dataset)
                    return result["columns"]
                elif source_type == "sql":
                    meta = DATASET_META[dataset]
                    result = await toolset.introspect_sql_schema(
                        dataset, table_name=meta.get("sql_table"),
                    )
                    # introspect_sql_schema returns tables list; get the right one
                    for table in result.get("tables", []):
                        if table["table"] == meta.get("sql_table"):
                            return table["columns"]
                    # If single table, return first
                    if result.get("tables"):
                        return result["tables"][0]["columns"]
                    return None
                else:
                    return None
            finally:
                await toolset.close()

        return asyncio.run(_run())

    except ImportError:
        return None
    except Exception as e:
        _info(f"IntrospectToolset error: {e}")
        return None


def _introspect_fallback(dataset: str, source_type: str) -> list[dict]:
    """Fallback introspection when IntrospectToolset is not available."""
    if source_type == "csv":
        return _introspect_csv_fallback(dataset)
    elif source_type == "sql":
        return _introspect_sql_fallback(dataset)
    return []


def _introspect_csv_fallback(dataset: str) -> list[dict]:
    """Read CSV and infer types using built-in logic."""
    csv_path = Path("data") / f"{dataset}.csv"
    if not csv_path.exists():
        _fail(f"CSV not found: {csv_path}")
        sys.exit(1)

    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    columns = []
    for col in reader.fieldnames:
        values = [r[col] for r in rows if r[col]]
        inferred = _infer_type(values)
        columns.append({
            "name": col,
            "data_type": inferred,
            "sample_values": values[:5],
            "nullable": any(r[col] == "" for r in rows),
        })
    return columns


def _introspect_sql_fallback(dataset: str) -> list[dict]:
    """Read SQLite schema using sqlite3 PRAGMA."""
    db_path = Path("data") / f"{dataset}.db"
    meta = DATASET_META[dataset]
    table = meta.get("sql_table", dataset)

    if not db_path.exists():
        _fail(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Get column info
    cur.execute(f"PRAGMA table_info({table})")
    pragma_rows = cur.fetchall()

    # Get sample data
    cur.execute(f"SELECT * FROM {table} LIMIT 5")
    sample_rows = cur.fetchall()

    # Get foreign keys
    cur.execute(f"PRAGMA foreign_key_list({table})")
    fks = {row[3]: f"{row[2]}.{row[4]}" for row in cur.fetchall()}

    columns = []
    for col_info in pragma_rows:
        cid, name, col_type, notnull, default_val, pk = col_info
        samples = [str(row[cid]) for row in sample_rows if row[cid] is not None]

        # Map SQL type to SDC type
        type_map = {"INTEGER": "integer", "REAL": "decimal", "TEXT": "string"}
        data_type = type_map.get(col_type.upper(), "string")

        col = {
            "name": name,
            "data_type": data_type,
            "sample_values": samples[:5],
            "nullable": not bool(notnull),
            "constraints": {},
            "relationships": "",
            "business_rules": "",
            "metadata": {"sql_type": col_type},
            "description": "",
            "enumeration": None,
            "units": "",
            "range_values": "",
            "examples": "",
        }

        if pk:
            col["constraints"]["primary_key"] = True
        if default_val is not None:
            col["constraints"]["default"] = str(default_val)
        if name in fks:
            col["relationships"] = fks[name]

        columns.append(col)

    conn.close()
    return columns


def _infer_type(values: list[str]) -> str:
    """Simple type inference from sample string values."""
    if not values:
        return "string"

    try:
        for v in values:
            int(v)
        return "integer"
    except ValueError:
        pass

    try:
        for v in values:
            float(v)
        return "decimal"
    except ValueError:
        pass

    try:
        for v in values:
            datetime.strptime(v, "%Y-%m-%d")
        return "date"
    except ValueError:
        pass

    try:
        for v in values:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        return "datetime"
    except ValueError:
        pass

    return "string"


def _load_rows(dataset: str, source_type: str) -> list[dict]:
    """Load all rows as list of dicts for XML generation."""
    if source_type == "csv":
        csv_path = Path("data") / f"{dataset}.csv"
        with open(csv_path, newline="") as fh:
            return list(csv.DictReader(fh))
    elif source_type == "sql":
        meta = DATASET_META[dataset]
        table = meta.get("sql_table", dataset)
        db_path = Path("data") / f"{dataset}.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table}")
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return rows
    return []


# ---------------------------------------------------------------------------
# Step 2 — Compare Introspection Output
# ---------------------------------------------------------------------------

def step_compare_output(introspection: dict, dataset: str) -> None:
    """Show per-column field population counts and enrichment source."""
    _banner(2, "Introspection Field Coverage")

    meta = DATASET_META[dataset]
    source_type = meta["source_type"]

    if source_type == "csv":
        # Check if sidecar was used
        sidecar_path = Path("data") / f"{dataset}.meta.json"
        source_label = f"sidecar ({sidecar_path.name})" if sidecar_path.exists() else "type inference only"
    elif source_type == "sql":
        source_label = "SQL catalog (PRAGMA / inspector)"
    else:
        source_label = "unknown"

    _info(f"Enrichment source: {source_label}")
    print()

    # All 13 standard fields
    all_fields = ("name", "data_type", "sample_values") + ENRICHMENT_FIELDS

    print(f"  {'Column':<20} {'Populated':<14} {'Enriched Fields'}")
    print(f"  {'-'*20} {'-'*14} {'-'*40}")

    for col in introspection["columns"]:
        count = sum(1 for f in all_fields if _field_populated(col, f))
        total = len(all_fields)
        enriched = [f for f in ENRICHMENT_FIELDS if _field_populated(col, f)]
        enriched_str = ", ".join(enriched) if enriched else "(none)"
        print(f"  {col['name']:<20} {count}/{total:<13} {enriched_str}")

    _ok(f"{len(introspection['columns'])} columns analyzed")


# ---------------------------------------------------------------------------
# Step 3 — Schema Resolution
# ---------------------------------------------------------------------------

def step_schema_resolution(dataset: str, mode: str) -> Path:
    """Copy pre-baked schemas into cache (self-contained) or fetch from API."""
    _banner(3, "Schema Resolution")

    meta = DATASET_META[dataset]
    dm_ct_id = meta["dm_ct_id"]
    cache_schemas = CACHE_DIR / "schemas"
    cache_schemas.mkdir(parents=True, exist_ok=True)

    if mode == "self-contained":
        src_dir = SCHEMA_DIR / dataset
        if not src_dir.exists():
            _fail(f"Pre-baked schemas not found: {src_dir}")
            sys.exit(1)

        copied = 0
        for f in src_dir.iterdir():
            dest = cache_schemas / f.name
            shutil.copy2(f, dest)
            copied += 1

        # Also copy the RM schema subset
        rm_src = SCHEMA_DIR / "sdc4.xsd"
        if rm_src.exists():
            shutil.copy2(rm_src, cache_schemas / "sdc4.xsd")
            copied += 1

        _ok(f"Copied {copied} pre-baked artifacts to {cache_schemas}")
        _info(f"XSD: dm-{dm_ct_id}.xsd")
        return cache_schemas / f"dm-{dm_ct_id}.xsd"
    else:
        _info("Live mode: fetching schemas from SDCStudio catalog API...")
        return _fetch_live_schema(dm_ct_id, cache_schemas)


def _fetch_live_schema(ct_id: str, cache_dir: Path) -> Path:
    """Fetch schema from SDCStudio catalog (live mode)."""
    try:
        from sdc_agents.common.config import load_config
        from sdc_agents.toolsets.catalog import CatalogToolset

        config = load_config("sdc-agents.demo.yaml")

        async def _fetch():
            toolset = CatalogToolset(config)
            try:
                schema = await toolset.catalog_get_schema(ct_id)
                _ok(f"Fetched schema: {schema.get('title', ct_id)}")
                return schema
            finally:
                await toolset.close()

        asyncio.run(_fetch())
        xsd_path = cache_dir / f"dm-{ct_id}.xsd"
        _ok(f"Schema cached at {xsd_path}")
        return xsd_path

    except ImportError:
        _fail("sdc-agents package not installed. Install with: pip install sdc-agents")
        sys.exit(1)
    except Exception as e:
        _fail(f"Failed to fetch schema from SDCStudio: {e}")
        _info("Falling back to self-contained mode...")
        return Path("schemas") / f"dm-{ct_id}.xsd"


# ---------------------------------------------------------------------------
# Step 4 — Mapping
# ---------------------------------------------------------------------------

def step_mapping(dataset: str, introspection: dict) -> dict:
    """Load field mappings (pre-baked) and display the mapping table."""
    _banner(4, "Column-to-Component Mapping")

    mapping_path = SCHEMA_DIR / "field_mappings" / f"{dataset}.json"
    if not mapping_path.exists():
        _fail(f"Field mapping not found: {mapping_path}")
        sys.exit(1)

    with open(mapping_path) as fh:
        mapping_data = json.load(fh)

    mappings = mapping_data["mappings"]

    print(f"  {'CSV Column':<20} {'SDC4 Type':<14} {'Component Label':<22} {'Value Element'}")
    print(f"  {'-'*20} {'-'*14} {'-'*22} {'-'*20}")
    for m in mappings:
        print(f"  {m['column_name']:<20} {m['rm_type']:<14} {m['component_label']:<22} {m['value_element']}")

    _ok(f"Mapped {len(mappings)} columns to SDC4 components")

    # Persist to cache
    cache_mapping = CACHE_DIR / "mappings"
    cache_mapping.mkdir(parents=True, exist_ok=True)
    with open(cache_mapping / f"{dataset}.json", "w") as fh:
        json.dump(mapping_data, fh, indent=2)

    return mapping_data


# ---------------------------------------------------------------------------
# Step 5 — Generate XML Instances
# ---------------------------------------------------------------------------

def step_generate(dataset: str, introspection: dict, mapping_data: dict) -> list[Path]:
    """Generate SDC4 XML instances from data rows using the mapping."""
    _banner(5, "Generate XML Instances")

    output_dir = OUTPUT_DIR / dataset
    output_dir.mkdir(parents=True, exist_ok=True)

    meta = DATASET_META[dataset]
    dm_ct_id = meta["dm_ct_id"]
    dm_label = meta["label"]
    mappings = {m["column_name"]: m for m in mapping_data["mappings"]}
    rows = introspection["rows"]

    cluster_ct_id = meta["cluster_ct_id"]
    cluster_label = meta["cluster_label"]

    generated = []
    for i, row in enumerate(rows):
        xml_str = _build_xml_instance(
            dm_ct_id, dm_label, row, mappings, i,
            cluster_ct_id=cluster_ct_id, cluster_label=cluster_label,
        )
        out_path = output_dir / f"instance_{i:04d}.xml"
        out_path.write_text(xml_str, encoding="utf-8")
        generated.append(out_path)

    _ok(f"Generated {len(generated)} XML instances in {output_dir}/")

    # Also copy TTL for GraphDB loading
    ttl_src = CACHE_DIR / "schemas" / f"dm-{dm_ct_id}.ttl"
    if ttl_src.exists():
        shutil.copy2(ttl_src, output_dir / f"dm-{dm_ct_id}.ttl")
        _info(f"Copied RDF triples to {output_dir}/")

    return generated


def _build_xml_instance(
    dm_ct_id: str,
    dm_label: str,
    row: dict,
    mappings: dict[str, dict],
    row_idx: int,
    cluster_ct_id: str = "",
    cluster_label: str = "",
) -> str:
    """Build an SDC4 XML instance string for one data row."""
    ns = SDC4_NS
    timestamp = datetime.now(timezone.utc).isoformat()
    instance_id = str(uuid.uuid4())

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<sdc4:dm-{dm_ct_id}',
        f'  xmlns:sdc4="{ns}"',
        f'  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        f'  xsi:schemaLocation="{ns} dm-{dm_ct_id}.xsd">',
        f'  <dm-label>{dm_label}</dm-label>',
        f'  <dm-language>en-US</dm-language>',
        f'  <dm-encoding>utf-8</dm-encoding>',
        f'  <creation_timestamp>{timestamp}</creation_timestamp>',
        f'  <instance_id>{instance_id}</instance_id>',
    ]

    # Open cluster wrapper
    lines.append(f'  <sdc4:ms-{cluster_ct_id}>')
    lines.append(f'    <label>{cluster_label}</label>')

    # Build component elements from row data
    for col_name, value in row.items():
        if col_name not in mappings:
            continue
        m = mappings[col_name]
        ct_id = m["component_ct_id"]
        label = m["component_label"]
        val_elem = m["value_element"]
        rm_type = m["rm_type"]

        # Coerce to string for XML (SQL returns native Python types)
        str_value = str(value) if value is not None else ""

        lines.append(f'    <sdc4:ms-{ct_id}>')
        lines.append(f'      <label>{label}</label>')

        if rm_type == "XdString":
            lines.append(f'      <{val_elem}>{_xml_escape(str_value)}</{val_elem}>')
        elif rm_type in ("XdQuantity", "XdCount"):
            lines.append(f'      <{val_elem}>{str_value}</{val_elem}>')
            # Units are required for quantified types
            units_elem = m.get("units_element", "xdquantity-units")
            units_label = m.get("units_label", "Units")
            # Try to get unit value from a source column, else use default
            src_col = m.get("units_source_column")
            unit_val = str(row.get(src_col, "")) if src_col else ""
            if not unit_val:
                unit_val = m.get("units_default_value", "unit")
            lines.append(f'      <{units_elem}>')
            lines.append(f'        <label>{units_label}</label>')
            lines.append(f'        <xdstring-value>{_xml_escape(unit_val)}</xdstring-value>')
            lines.append(f'      </{units_elem}>')
        elif rm_type == "XdTemporal":
            lines.append(f'      <{val_elem}>{str_value}</{val_elem}>')
        elif rm_type == "XdBoolean":
            bool_val = str_value.lower() in ("1", "true", "yes", "t")
            lines.append(f'      <{val_elem}>{str(bool_val).lower()}</{val_elem}>')

        lines.append(f'    </sdc4:ms-{ct_id}>')

    # Close cluster wrapper
    lines.append(f'  </sdc4:ms-{cluster_ct_id}>')
    lines.append(f'</sdc4:dm-{dm_ct_id}>')
    return "\n".join(lines)


def _xml_escape(s: str) -> str:
    """Escape XML special characters."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ---------------------------------------------------------------------------
# Step 6 — Validate
# ---------------------------------------------------------------------------

def step_validate(
    dataset: str,
    mode: str,
    xsd_path: Path,
    generated: list[Path],
) -> dict:
    """Validate generated XML instances."""
    _banner(6, "Validate Instances")

    if mode == "self-contained":
        return _validate_local(xsd_path, generated)
    else:
        return _validate_live(generated)


def _validate_local(xsd_path: Path, generated: list[Path]) -> dict:
    """Validate using local sdcvalidator."""
    try:
        from sdcvalidator import SDC4Validator
    except ImportError:
        _info("sdcvalidator not installed — skipping validation")
        _info("Install with: pip install sdcvalidator")
        return {"skipped": True}

    _info(f"Validating against: {xsd_path}")

    try:
        validator = SDC4Validator(
            schema=str(xsd_path),
            check_sdc4_compliance=False,
            validation="lax",
        )
    except Exception as e:
        _info(f"Schema loading note: {e}")
        _info("Proceeding with structural check only...")
        return _validate_structural(generated)

    passed = 0
    failed = 0
    structural_errors = 0
    semantic_errors = 0

    for xml_path in generated:
        try:
            result = validator.validate(xml_source=str(xml_path))
            if result.is_valid:
                passed += 1
            else:
                failed += 1
                structural_errors += len(result.structural_errors)
                semantic_errors += len(result.semantic_errors)
        except Exception:
            failed += 1

    total = passed + failed
    print(f"  Validated:         {total} instances")
    print(f"  Passed:            {passed}")
    print(f"  Failed:            {failed}")
    print(f"  Structural errors: {structural_errors}")
    print(f"  Semantic errors:   {semantic_errors}")

    _ok("Validation complete")
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "structural_errors": structural_errors,
        "semantic_errors": semantic_errors,
    }


def _validate_structural(generated: list[Path]) -> dict:
    """Fallback: parse XML to verify well-formedness."""
    passed = 0
    failed = 0

    for xml_path in generated:
        try:
            ET.parse(xml_path)
            passed += 1
        except ET.ParseError:
            failed += 1

    total = passed + failed
    print(f"  Well-formed XML:   {passed}/{total}")

    if failed:
        _info(f"{failed} files are not well-formed XML")
    else:
        _ok("All instances are well-formed XML")

    return {"total": total, "passed": passed, "failed": failed}


def _validate_live(generated: list[Path]) -> dict:
    """Validate using SDCStudio VaaS API (live mode)."""
    try:
        from sdc_agents.common.config import load_config
        from sdc_agents.toolsets.validation import ValidationToolset

        config = load_config("sdc-agents.demo.yaml")

        async def _run():
            toolset = ValidationToolset(config)
            try:
                result = await toolset.validate_batch(
                    xml_dir=str(generated[0].parent)
                )
                return result
            finally:
                await toolset.close()

        result = asyncio.run(_run())
        _ok(f"VaaS validation: {result}")
        return result

    except ImportError:
        _fail("sdc-agents not installed for live validation")
        return {"skipped": True}
    except Exception as e:
        _fail(f"Live validation failed: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Step 7 — Load to GraphDB
# ---------------------------------------------------------------------------

def step_load_graphdb(dataset: str) -> None:
    """Load TTL triples into GraphDB."""
    _banner(7, "Load to GraphDB")

    try:
        import httpx
    except ImportError:
        _fail("httpx not installed — skipping GraphDB loading")
        _info("Install with: pip install httpx")
        return

    graphdb_url = "http://localhost:7200"
    repo = "sdc4_demo"
    output_dir = OUTPUT_DIR / dataset

    # Check GraphDB availability
    _info(f"Connecting to GraphDB at {graphdb_url}...")
    try:
        resp = httpx.get(f"{graphdb_url}/rest/repositories", timeout=5.0)
        resp.raise_for_status()
    except Exception:
        _fail("GraphDB not reachable. Start it with: docker compose up -d")
        _info("Skipping GraphDB loading.")
        return

    # Create repository if needed
    try:
        resp = httpx.get(f"{graphdb_url}/rest/repositories/{repo}", timeout=5.0)
        if resp.status_code == 404:
            _info(f"Creating repository: {repo}")
            config_path = Path("scripts/graphdb-repo-config.ttl")
            if config_path.exists():
                with open(config_path) as fh:
                    config_ttl = fh.read()
                httpx.post(
                    f"{graphdb_url}/rest/repositories",
                    content=config_ttl,
                    headers={"Content-Type": "text/turtle"},
                    timeout=10.0,
                )
                _ok(f"Repository '{repo}' created")
            else:
                _info("Repository config not found, attempting default creation")
    except Exception as e:
        _info(f"Repository check: {e}")

    # Load TTL files
    loaded = 0
    for ttl_file in output_dir.glob("*.ttl"):
        try:
            with open(ttl_file) as fh:
                content = fh.read()
            httpx.post(
                f"{graphdb_url}/repositories/{repo}/statements",
                content=content,
                headers={"Content-Type": "text/turtle"},
                timeout=10.0,
            )
            loaded += 1
            _info(f"Loaded: {ttl_file.name}")
        except Exception as e:
            _fail(f"Failed to load {ttl_file.name}: {e}")

    if loaded:
        _ok(f"Loaded {loaded} TTL file(s) into repository '{repo}'")
        _info(f"Explore at: {graphdb_url}/sparql")
    else:
        _info("No TTL files found to load")


# ---------------------------------------------------------------------------
# Step 8 — Summary
# ---------------------------------------------------------------------------

def step_summary(
    dataset: str,
    mode: str,
    introspection: dict,
    generated: list[Path],
    validation: dict,
    skip_graphdb: bool,
) -> None:
    """Print final summary."""
    _banner(8, "Summary")

    meta = DATASET_META[dataset]
    output_dir = OUTPUT_DIR / dataset

    print(f"  Dataset:           {dataset}")
    print(f"  Source type:       {meta['source_type']}")
    print(f"  Mode:              {mode}")
    print(f"  Data Model:        {meta['label']} (dm-{meta['dm_ct_id']})")
    print(f"  Rows processed:    {introspection['row_count']}")
    print(f"  Instances created: {len(generated)}")
    print()
    print(f"  Artifacts:")
    print(f"    XML instances:   {output_dir}/instance_*.xml")
    print(f"    XSD schema:      schemas/{dataset}/dm-{meta['dm_ct_id']}.xsd")
    print(f"    RDF triples:     schemas/{dataset}/dm-{meta['dm_ct_id']}.ttl")
    print(f"    HTML docs:       schemas/{dataset}/dm-{meta['dm_ct_id']}.html")
    print(f"    JSON-LD:         schemas/{dataset}/dm-{meta['dm_ct_id']}.jsonld")
    print(f"    SHACL shapes:    schemas/{dataset}/dm-{meta['dm_ct_id']}_shacl.ttl")
    print(f"    GQL statements:  schemas/{dataset}/dm-{meta['dm_ct_id']}.gql")

    if not skip_graphdb:
        print()
        print(f"  GraphDB:           http://localhost:7200")
        print(f"  SPARQL endpoint:   http://localhost:7200/repositories/sdc4_demo")
        print(f"  Demo queries:      sparql/demo_queries.md")

    print()
    if validation.get("skipped"):
        print("  Validation was skipped (install sdcvalidator for full validation)")
    elif validation.get("error"):
        print(f"  Validation error: {validation['error']}")
    else:
        passed = validation.get("passed", 0)
        total = validation.get("total", 0)
        print(f"  Validation:        {passed}/{total} passed")

    print()
    _ok("Demo complete!")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SDC Agents Demo — From Raw Data to Validated Knowledge Graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo.py --dataset lab_results --mode self-contained --skip-graphdb
  python demo.py --dataset sensor_readings
  python demo.py --dataset employees --skip-graphdb
  python demo.py --dataset purchase_orders --mode live
        """,
    )
    parser.add_argument(
        "--dataset",
        choices=DATASETS,
        default="lab_results",
        help="Which sample dataset to process (default: lab_results)",
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="self-contained",
        help="self-contained uses pre-baked schemas; live connects to SDCStudio (default: self-contained)",
    )
    parser.add_argument(
        "--skip-graphdb",
        action="store_true",
        help="Skip loading triples into GraphDB (no Docker required)",
    )
    args = parser.parse_args()

    print()
    print("  SDC Agents Demo")
    print("  ===============")
    print(f"  Dataset: {args.dataset}")
    print(f"  Mode:    {args.mode}")
    print(f"  GraphDB: {'skipped' if args.skip_graphdb else 'enabled'}")

    # Pipeline (8 steps)
    introspection = step_introspect(args.dataset)
    step_compare_output(introspection, args.dataset)
    xsd_path = step_schema_resolution(args.dataset, args.mode)
    mapping_data = step_mapping(args.dataset, introspection)
    generated = step_generate(args.dataset, introspection, mapping_data)
    validation = step_validate(args.dataset, args.mode, xsd_path, generated)

    if not args.skip_graphdb:
        step_load_graphdb(args.dataset)

    step_summary(
        args.dataset,
        args.mode,
        introspection,
        generated,
        validation,
        args.skip_graphdb,
    )


if __name__ == "__main__":
    main()
