# Demo SPARQL Queries

These queries demonstrate the value of OWL 2 RL reasoning over SDC4 validated data. Run them in the GraphDB Workbench at [http://localhost:7200](http://localhost:7200).

## Query 1: Basic — List All Schema Components

A flat lookup to verify data loaded correctly.

```sparql
# TODO: Query TBD — depends on dataset and generated schemas
PREFIX sdc4: <https://semanticdatacharter.com/sdc4/>

SELECT ?component ?label ?type
WHERE {
  ?component a ?type ;
             sdc4:label ?label .
}
ORDER BY ?type ?label
```

## Query 2: Reasoning Payoff — Inferred Relationships

This query returns results that **only exist because the OWL 2 RL reasoner derived them**. These relationships were not in the original CSV — they were inferred from the semantic definitions in the SDC4 schemas.

```sparql
# TODO: Query TBD — must demonstrate inference, not flat lookup
# The specific query depends on the dataset and ontology structure
```

## Query 3: Cross-Domain — Connecting Concepts

Demonstrates how SDC4's semantic links connect concepts across domain boundaries.

```sparql
# TODO: Query TBD — depends on which domains are represented in the demo data
```
