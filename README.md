# SDC Agents Demo

**Build a Zero-Hallucination Knowledge Graph in 5 Minutes.**

This demo takes you from a raw CSV dataset to a validated, reasoned knowledge graph — using [SDC Agents](https://github.com/Axius-SDC/SDC_Agents) and the SDC4 semantic data modeling framework.

## What You'll Get

- A validated SDC4 schema (XSD) generated from real-world data
- Browsable HTML documentation for every schema component
- JSON-LD semantic descriptions for linked data integration
- RDF triples loaded into a local GraphDB instance with OWL 2 RL reasoning
- SHACL constraints for schema validation
- GQL CREATE statements for property graph databases
- A SPARQL query that demonstrates *inference* — answers that only exist because the reasoner derived them

## Prerequisites

- [Docker](https://docs.docker.com/engine/install/) or [Podman](https://podman.io/getting-started/installation)
- Python 3.11+
- ~3GB free RAM (this demo uses a lite stack)

## Quick Start

### 1. Clone and start the lite stack

```bash
git clone https://github.com/Axius-SDC/SDC_Agents_Demo.git
cd SDC_Agents_Demo
docker compose up -d
```

This starts GraphDB and PostgreSQL only. No Keycloak, no SirixDB — those are production concerns.

### 2. Install SDC Agents

```bash
pip install sdc-agents
```

### 3. Run the demo pipeline

```bash
# TODO: Exact command TBD — processes sample data against SDC catalog,
# validates, and generates all output artifacts
sdc-agents quickstart --data data/sample_dataset.csv
```

### 4. Explore the results

**Browse the schema documentation:**
Open `schemas/dm-*.html` in your browser to see the generated documentation for each schema component.

**Query the knowledge graph:**
Open GraphDB Workbench at [http://localhost:7200](http://localhost:7200) and paste the SPARQL queries from `sparql/demo_queries.md`.

**Inspect the artifacts:**
- `schemas/dm-*.xsd` — XML Schema definitions
- `schemas/dm-*.jsonld` — JSON-LD semantic descriptions
- `schemas/dm-*_shacl.ttl` — SHACL constraint shapes
- `schemas/dm-*.gql` — GQL CREATE statements for property graphs

## What Just Happened?

SDC Agents processed your CSV through a pipeline that:

1. **Introspected** the data structure, inferring types and constraints
2. **Mapped** columns to existing SDC4 catalog components (FHIR, NIEM, X12)
3. **Validated** the data against SDC4 schemas (structural validation, H=0)
4. **Generated** seven output formats from a single semantic definition
5. **Loaded** RDF triples into GraphDB with OWL 2 RL reasoning enabled

The knowledge graph doesn't just store your data — it *reasons* over it. The SPARQL demo queries show inferences the reasoner derived that weren't in your original CSV.

## Project Structure

```
SDC_Agents_Demo/
  README.md              # You are here
  docker-compose.yml     # Lite stack: GraphDB + PostgreSQL
  data/                  # Sample dataset(s)
  schemas/               # Generated SDCStudio outputs (XSD, HTML, TTL, JSONLD, SHACL, GQL)
  sparql/                # Demo SPARQL queries with explanations
  scripts/               # Helper scripts (triple loading, etc.)
```

## Next Steps

- **Full enterprise stack**: See the [SDCStudio AppGen](https://github.com/Axius-SDC/SDCStudio) for production deployment with SirixDB temporal versioning and Keycloak SSO
- **Build your own models**: Use [SDCStudio](https://axius-sdc.com) to create SDC4-compliant schemas for your domain
- **Integrate SDC Agents**: See the [SDC Agents documentation](https://github.com/Axius-SDC/SDC_Agents) for the full agent toolkit

## Learn More

- [Semantic Data Charter](https://semanticdatacharter.com) — The SDC4 specification
- [Axius SDC](https://axius-sdc.com) — SDCStudio cloud platform
- [SDC Agents](https://github.com/Axius-SDC/SDC_Agents) — The agent toolkit this demo uses
