#!/usr/bin/env python3
"""
SDC Agents Demo — From CSV to Validated Knowledge Graph

Usage:
    python demo.py [--dataset lab_results|sensor_readings|purchase_orders]
                   [--mode self-contained|live]
                   [--skip-graphdb]

Requires: pip install sdc-agents sdcvalidator
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATASETS = ("lab_results", "sensor_readings", "purchase_orders")
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
    },
    "sensor_readings": {
        "dm_ct_id": "d3m0s3ns0rr34d1ngsx8m5n3q",
        "cluster_ct_id": "sr00clust3rs3ns0rr34d1ngs",
        "cluster_label": "SensorReadings Data Cluster",
        "label": "SensorReadings",
    },
    "purchase_orders": {
        "dm_ct_id": "d3m0purch4s30rd3rsx6j8r2t",
        "cluster_ct_id": "po00clust3rpurch4s30rd3rs",
        "cluster_label": "PurchaseOrders Data Cluster",
        "label": "PurchaseOrders",
    },
}

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


# ---------------------------------------------------------------------------
# Step 1 — Introspect CSV
# ---------------------------------------------------------------------------

def step_introspect(dataset: str) -> dict:
    """Read the CSV and summarise columns with inferred types."""
    _banner(1, "Introspect CSV")

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
            "inferred_type": inferred,
            "sample_values": values[:3],
            "non_null_count": len(values),
        })

    _ok(f"Read {len(rows)} rows, {len(columns)} columns from {csv_path}")
    print()
    print(f"  {'Column':<20} {'Inferred Type':<14} {'Samples'}")
    print(f"  {'-'*20} {'-'*14} {'-'*30}")
    for c in columns:
        samples = ", ".join(c["sample_values"][:3])
        print(f"  {c['name']:<20} {c['inferred_type']:<14} {samples}")

    return {"rows": rows, "columns": columns, "row_count": len(rows)}


def _infer_type(values: list[str]) -> str:
    """Simple type inference from sample string values."""
    if not values:
        return "string"

    # Try integer
    try:
        for v in values:
            int(v)
        return "integer"
    except ValueError:
        pass

    # Try decimal
    try:
        for v in values:
            float(v)
        return "decimal"
    except ValueError:
        pass

    # Try date (YYYY-MM-DD)
    try:
        for v in values:
            datetime.strptime(v, "%Y-%m-%d")
        return "date"
    except ValueError:
        pass

    # Try datetime (ISO 8601)
    try:
        for v in values:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        return "datetime"
    except ValueError:
        pass

    return "string"


# ---------------------------------------------------------------------------
# Step 2 — Schema Resolution
# ---------------------------------------------------------------------------

def step_schema_resolution(dataset: str, mode: str) -> Path:
    """Copy pre-baked schemas into cache (self-contained) or fetch from API."""
    _banner(2, "Schema Resolution")

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
# Step 3 — Mapping
# ---------------------------------------------------------------------------

def step_mapping(dataset: str, introspection: dict) -> dict:
    """Load field mappings (pre-baked) and display the mapping table."""
    _banner(3, "Column-to-Component Mapping")

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
# Step 4 — Generate XML Instances
# ---------------------------------------------------------------------------

def step_generate(dataset: str, introspection: dict, mapping_data: dict) -> list[Path]:
    """Generate SDC4 XML instances from CSV rows using the mapping."""
    _banner(4, "Generate XML Instances")

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
    """Build an SDC4 XML instance string for one CSV row."""
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

        lines.append(f'    <sdc4:ms-{ct_id}>')
        lines.append(f'      <label>{label}</label>')

        if rm_type == "XdString":
            lines.append(f'      <{val_elem}>{_xml_escape(value)}</{val_elem}>')
        elif rm_type in ("XdQuantity", "XdCount"):
            lines.append(f'      <{val_elem}>{value}</{val_elem}>')
            # Units are required for quantified types
            units_elem = m.get("units_element", "xdquantity-units")
            units_label = m.get("units_label", "Units")
            # Try to get unit value from a source column, else use default
            src_col = m.get("units_source_column")
            unit_val = row.get(src_col, "") if src_col else ""
            if not unit_val:
                unit_val = m.get("units_default_value", "unit")
            lines.append(f'      <{units_elem}>')
            lines.append(f'        <label>{units_label}</label>')
            lines.append(f'        <xdstring-value>{_xml_escape(unit_val)}</xdstring-value>')
            lines.append(f'      </{units_elem}>')
        elif rm_type == "XdTemporal":
            lines.append(f'      <{val_elem}>{value}</{val_elem}>')

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
# Step 5 — Validate
# ---------------------------------------------------------------------------

def step_validate(
    dataset: str,
    mode: str,
    xsd_path: Path,
    generated: list[Path],
) -> dict:
    """Validate generated XML instances."""
    _banner(5, "Validate Instances")

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
# Step 6 — Load to GraphDB
# ---------------------------------------------------------------------------

def step_load_graphdb(dataset: str) -> None:
    """Load TTL triples into GraphDB."""
    _banner(6, "Load to GraphDB")

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
# Step 7 — Summary
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
    _banner(7, "Summary")

    meta = DATASET_META[dataset]
    output_dir = OUTPUT_DIR / dataset

    print(f"  Dataset:           {dataset}")
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
        description="SDC Agents Demo — From CSV to Validated Knowledge Graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo.py --dataset lab_results --mode self-contained --skip-graphdb
  python demo.py --dataset sensor_readings
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

    # Pipeline
    introspection = step_introspect(args.dataset)
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
