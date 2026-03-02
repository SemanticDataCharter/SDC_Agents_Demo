# Demo SPARQL Queries

Run these queries in the GraphDB Workbench at [http://localhost:7200](http://localhost:7200).
Select the `sdc4_demo` repository, then paste each query into the SPARQL editor.

---

## Query 1: List All Schema Components

A flat lookup showing every model component, its label, and its SDC4 reference model type.

```sparql
PREFIX rdf:       <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:      <http://www.w3.org/2000/01/rdf-schema#>
PREFIX sdc4-meta: <https://semanticdatacharter.com/ontology/sdc4-meta/>

SELECT ?component ?label ?rmType
WHERE {
  ?component a sdc4-meta:ModelComponent ;
             rdfs:label ?label ;
             sdc4-meta:isConstrainedByRmComponent ?rmType .
}
ORDER BY ?rmType ?label
```

**Expected**: One row per component across all loaded datasets. You'll see labels like "Patient ID", "Temperature", "PO Number" alongside their RM types (XdStringType, XdQuantityType, etc.).

---

## Query 2: Data Models and Their Clusters

Shows each data model with its cluster and the components within that cluster.

```sparql
PREFIX rdfs:      <http://www.w3.org/2000/01/rdf-schema#>
PREFIX sdc4-meta: <https://semanticdatacharter.com/ontology/sdc4-meta/>

SELECT ?dmLabel ?clusterLabel ?componentLabel ?rmType
WHERE {
  ?dm a sdc4-meta:DataModel ;
      rdfs:label ?dmLabel ;
      sdc4-meta:hasCluster ?cluster .

  ?cluster rdfs:label ?clusterLabel ;
           sdc4-meta:hasComponent ?component .

  ?component rdfs:label ?componentLabel ;
             sdc4-meta:isConstrainedByRmComponent ?rmType .
}
ORDER BY ?dmLabel ?componentLabel
```

**Expected**: A hierarchical view — each data model (LabResults, SensorReadings, PurchaseOrders) with its cluster and member components.

---

## Query 3: Reasoning Payoff — Components by RM Base Type

This query groups components by their reference model type. Because OWL 2 RL reasoning is enabled, the reasoner can infer that all `XdQuantityType` components share a common ancestor (`XdOrderedType` > `XdAnyType`), even though this relationship was never explicitly stated in the loaded triples.

```sparql
PREFIX rdfs:      <http://www.w3.org/2000/01/rdf-schema#>
PREFIX sdc4:      <https://semanticdatacharter.com/ns/sdc4/>
PREFIX sdc4-meta: <https://semanticdatacharter.com/ontology/sdc4-meta/>

SELECT ?rmType (GROUP_CONCAT(?label; SEPARATOR=", ") AS ?components) (COUNT(?component) AS ?count)
WHERE {
  ?component a sdc4-meta:ModelComponent ;
             rdfs:label ?label ;
             sdc4-meta:isConstrainedByRmComponent ?rmType .
}
GROUP BY ?rmType
ORDER BY DESC(?count)
```

**Expected**: Grouped view showing, for example, all XdString components together (Patient ID, Test Name, Units, Lab Name, Sensor ID, Location, Status, PO Number, Vendor, Item Description) and all XdQuantity components together (Result Value, Temperature, Humidity, Unit Price).

---

## Query 4: Cross-Domain — Shared Quantity Components

When multiple datasets are loaded, this query finds components that are all constrained by `XdQuantityType` — demonstrating that SDC4's type system creates a semantic bridge between lab results (Result Value), sensor data (Temperature, Humidity), and supply chain data (Unit Price).

```sparql
PREFIX rdfs:      <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dc:        <http://purl.org/dc/elements/1.1/>
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

**Expected**: Shows that "Result Value" (healthcare), "Temperature"/"Humidity" (IoT), and "Unit Price" (supply chain) all share the same semantic foundation — they are all quantities with units. This cross-domain connection is what makes SDC4 knowledge graphs powerful.

---

## Query 5: Cross-Domain — Temporal Components

Similarly, date/time components across all domains share `XdTemporalType`:

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

  ?component sdc4-meta:isConstrainedByRmComponent sdc4:XdTemporalType ;
             rdfs:label ?componentLabel .

  OPTIONAL { ?component rdfs:comment ?comment }
}
ORDER BY ?dmLabel
```

**Expected**: "Collection Date" (healthcare), "Reading Time" (IoT), and "Order Date" (supply chain) — three different domains, one semantic type. A SPARQL query can now find "all temporal events" across your entire knowledge graph regardless of domain.

---

## Query 6: Component Descriptions (Full Metadata)

Extract all component metadata including descriptions — useful for documentation generation.

```sparql
PREFIX rdfs:      <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dc:        <http://purl.org/dc/elements/1.1/>
PREFIX sdc4-meta: <https://semanticdatacharter.com/ontology/sdc4-meta/>

SELECT ?dmTitle ?dmDescription ?componentLabel ?componentComment ?rmType
WHERE {
  ?dm a sdc4-meta:DataModel ;
      dc:title ?dmTitle ;
      dc:description ?dmDescription ;
      sdc4-meta:hasCluster ?cluster .

  ?cluster sdc4-meta:hasComponent ?component .

  ?component rdfs:label ?componentLabel ;
             sdc4-meta:isConstrainedByRmComponent ?rmType .

  OPTIONAL { ?component rdfs:comment ?componentComment }
}
ORDER BY ?dmTitle ?componentLabel
```

**Expected**: Full metadata for every component, ready for reporting or downstream integration.
