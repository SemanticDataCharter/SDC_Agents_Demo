#!/usr/bin/env bash
# Load RDF triples into local GraphDB instance
# Usage: ./scripts/load_triples.sh

set -euo pipefail

GRAPHDB_URL="http://localhost:7200"
REPO_NAME="sdc4_demo"

echo "Checking GraphDB availability..."
until curl -sf "${GRAPHDB_URL}/rest/repositories" > /dev/null 2>&1; do
  echo "Waiting for GraphDB..."
  sleep 2
done

# Create repository if it doesn't exist
if ! curl -sf "${GRAPHDB_URL}/rest/repositories/${REPO_NAME}" > /dev/null 2>&1; then
  echo "Creating repository: ${REPO_NAME}"
  # TODO: Add repository creation with OWL 2 RL reasoning config
  echo "Repository creation — requires config template (TBD)"
fi

# Load all TTL files from schemas/
for ttl_file in schemas/dm-*.ttl; do
  [ -f "$ttl_file" ] || continue
  echo "Loading: ${ttl_file}"
  curl -X POST \
    -H "Content-Type: text/turtle" \
    --data-binary "@${ttl_file}" \
    "${GRAPHDB_URL}/repositories/${REPO_NAME}/statements"
done

echo "Done. Open ${GRAPHDB_URL} to query the knowledge graph."
