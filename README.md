# SDC Agents Demo

**From a raw CSV to a validated, reasoned knowledge graph in 5 minutes.**

This demo walks you through the [SDC Agents](https://github.com/Axius-SDC/SDC_Agents) and [sdcvalidator](https://pypi.org/project/sdcvalidator/) pipeline: introspect a CSV, map columns to SDC4 schema components, generate XML instances, validate them, and load RDF triples into GraphDB with OWL 2 RL reasoning.

## What You'll Get

- SDC4 schema artifacts (XSD, HTML, JSON-LD, SHACL, GQL, RDF)
- Validated XML instances generated from your CSV data
- A knowledge graph with OWL 2 RL inference in GraphDB
- SPARQL queries that demonstrate cross-domain semantic connections

## Prerequisites

- Python 3.11+
- [Docker](https://docs.docker.com/engine/install/) or [Podman](https://podman.io/getting-started/installation) (only needed for GraphDB — optional with `--skip-graphdb`)

## Quick Start

### Self-Contained Mode (No Docker/Podman, No SDCStudio)

```bash
git clone https://github.com/Axius-SDC/SDC_Agents_Demo.git
cd SDC_Agents_Demo

pip install -r requirements.txt

python demo.py --dataset lab_results --mode self-contained --skip-graphdb
```

This runs the full pipeline using pre-baked schemas and local validation. No network access required.

### Full Pipeline with GraphDB

```bash
docker compose up -d                  # Start GraphDB (~30s to initialize)
python demo.py --dataset lab_results  # Process, validate, load triples
```

Podman users: substitute `podman compose` for `docker compose` throughout.

Open [http://localhost:7200](http://localhost:7200) to explore the knowledge graph.

## Sample Datasets

| Dataset | Domain | Columns | SDC4 Types Used |
|---|---|---|---|
| `lab_results` | Healthcare | patient_id, test_name, result_value, units, collection_date, lab_name | XdString, XdQuantity, XdTemporal |
| `sensor_readings` | IoT | sensor_id, location, temperature, humidity, reading_time, status | XdString, XdQuantity, XdTemporal |
| `purchase_orders` | Supply Chain | po_number, vendor, item_description, quantity, unit_price, order_date | XdString, XdCount, XdQuantity, XdTemporal |

Run any dataset:

```bash
python demo.py --dataset sensor_readings --skip-graphdb
python demo.py --dataset purchase_orders --skip-graphdb
```

## Pipeline Steps

The demo executes seven steps:

1. **Introspect** — Read the CSV file, infer column types (string, decimal, date, datetime, integer)
2. **Schema Resolution** — Copy pre-baked SDC4 schemas into the local cache (self-contained) or fetch from SDCStudio catalog API (live mode)
3. **Mapping** — Load column-to-component field mappings, display the mapping table
4. **Generate** — Create SDC4 XML instances from each CSV row using the schema and mappings
5. **Validate** — Validate instances against the XSD schema using sdcvalidator (structural + semantic checks)
6. **Load to GraphDB** — Load RDF triples into GraphDB with OWL 2 RL reasoning enabled
7. **Summary** — Print artifact paths, validation results, and GraphDB URLs

## Modes

### Self-Contained (default)

Uses pre-baked schemas in `schemas/` and validates locally with `sdcvalidator`. Works completely offline.

```bash
python demo.py --dataset lab_results --mode self-contained --skip-graphdb
```

### Live

Connects to a running SDCStudio instance for catalog lookups and VaaS validation. Requires `SDC_API_KEY` environment variable.

```bash
export SDC_API_KEY="your-api-key"
python demo.py --dataset lab_results --mode live
```

## Exploring the Knowledge Graph

After running the pipeline with GraphDB:

1. Open [http://localhost:7200](http://localhost:7200)
2. Select the `sdc4_demo` repository
3. Go to **SPARQL** and paste queries from [`sparql/demo_queries.md`](sparql/demo_queries.md)

### Example: Cross-Domain Quantity Components

This query finds all components that represent quantities — spanning healthcare (lab results), IoT (sensor readings), and supply chain (purchase orders):

```sparql
PREFIX rdfs:      <http://www.w3.org/2000/01/rdf-schema#>
PREFIX sdc4:      <https://semanticdatacharter.com/ns/sdc4/>
PREFIX sdc4-meta: <https://semanticdatacharter.com/ontology/sdc4-meta/>

SELECT ?dmLabel ?componentLabel ?comment
WHERE {
  ?dm a sdc4-meta:DataModel ;
      rdfs:label ?dmLabel ;
      sdc4-meta:hasCluster ?cluster .
  ?cluster sdc4-meta:hasComponent ?component .
  ?component sdc4-meta:isConstrainedByRmComponent sdc4:XdQuantityType ;
             rdfs:label ?componentLabel .
  OPTIONAL { ?component rdfs:comment ?comment }
}
ORDER BY ?dmLabel
```

Result: "Result Value" (healthcare), "Temperature"/"Humidity" (IoT), and "Unit Price" (supply chain) share the same semantic type.

## Project Structure

```
SDC_Agents_Demo/
  README.md                   # This file
  demo.py                     # Main orchestration script
  requirements.txt            # Python dependencies
  sdc-agents.demo.yaml        # SDC Agents configuration
  docker-compose.yml          # GraphDB service
  data/                       # Sample CSV datasets
    lab_results.csv
    sensor_readings.csv
    purchase_orders.csv
  schemas/                    # Pre-baked SDC4 schema artifacts
    sdc4.xsd                  # Minimal RM schema subset
    field_mappings/            # Column-to-component mappings
    lab_results/               # XSD, XML, TTL, HTML, JSON-LD, SHACL, GQL
    sensor_readings/
    purchase_orders/
  scripts/                    # Helper scripts
    graphdb-repo-config.ttl   # GraphDB OWL 2 RL repository config
    load_triples.sh           # Standalone triple loading script
  sparql/                     # SPARQL demo queries
    demo_queries.md
  output/                     # Generated artifacts (gitignored)
```

## Troubleshooting

**sdcvalidator not installed**:
```bash
pip install sdcvalidator>=4.1.0
```

**GraphDB not reachable**:
```bash
docker compose up -d           # or: podman compose up -d
docker compose ps              # Verify healthy
docker compose logs graphdb    # Check logs
```

**Schema validation errors**: The pre-baked schemas are a minimal subset for demo purposes. For full validation, use live mode with a running SDCStudio instance.

**Port conflicts**: If port 7200 is in use, edit `docker-compose.yml` to map to a different host port.

## Learn More

- [Semantic Data Charter](https://semanticdatacharter.com/specs/index.html) — The SDC4 specification
- [SDCStudio](https://sdcstudio.axius-sdc.com/) — Cloud platform for building SDC4 schemas
- [SDC Agents](https://github.com/Axius-SDC/SDC_Agents) — The agent toolkit powering this demo
- [sdcvalidator](https://pypi.org/project/sdcvalidator/) — SDC4 XML schema validation library
