#!/usr/bin/env bash
# Load RDF triples into local GraphDB instance
# Usage: ./scripts/load_triples.sh [output_dir]
#
# Waits for GraphDB, creates the sdc4_demo repository with OWL 2 RL
# reasoning, then loads all .ttl files from the output directory.

set -euo pipefail

GRAPHDB_URL="http://localhost:7200"
REPO_NAME="sdc4_demo"
OUTPUT_DIR="${1:-output}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_CONFIG="${SCRIPT_DIR}/graphdb-repo-config.ttl"
MAX_WAIT=60

echo "=== SDC4 Demo: Load Triples ==="
echo ""

# --- Wait for GraphDB ---
echo "[..] Waiting for GraphDB at ${GRAPHDB_URL}..."
elapsed=0
until curl -sf "${GRAPHDB_URL}/rest/repositories" > /dev/null 2>&1; do
  sleep 2
  elapsed=$((elapsed + 2))
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    echo "[!!] GraphDB not reachable after ${MAX_WAIT}s. Is it running?"
    echo "     Start with: docker compose up -d  (or: podman compose up -d)"
    exit 1
  fi
done
echo "[OK] GraphDB is ready."

# --- Create repository if it doesn't exist ---
repo_check=$(curl -sf -o /dev/null -w "%{http_code}" "${GRAPHDB_URL}/rest/repositories/${REPO_NAME}" 2>/dev/null || echo "404")

if [ "$repo_check" = "404" ] || [ "$repo_check" = "000" ]; then
  echo "[..] Creating repository: ${REPO_NAME} (OWL 2 RL reasoning)"
  if [ -f "$REPO_CONFIG" ]; then
    curl -sf -X POST \
      -H "Content-Type: text/turtle" \
      --data-binary "@${REPO_CONFIG}" \
      "${GRAPHDB_URL}/rest/repositories" \
      > /dev/null 2>&1
    echo "[OK] Repository '${REPO_NAME}' created with OWL 2 RL reasoning."
  else
    echo "[!!] Repository config not found: ${REPO_CONFIG}"
    echo "     Create it or manually create the repository in GraphDB Workbench."
    exit 1
  fi
else
  echo "[OK] Repository '${REPO_NAME}' already exists."
fi

# --- Load all TTL files ---
loaded=0
failed=0

find "${OUTPUT_DIR}" -name "*.ttl" -type f | sort | while read -r ttl_file; do
  echo "[..] Loading: ${ttl_file}"
  http_code=$(curl -sf -o /dev/null -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/turtle" \
    --data-binary "@${ttl_file}" \
    "${GRAPHDB_URL}/repositories/${REPO_NAME}/statements" 2>/dev/null || echo "000")

  if [ "$http_code" = "204" ] || [ "$http_code" = "200" ]; then
    echo "[OK] Loaded: $(basename "${ttl_file}")"
  else
    echo "[!!] Failed (HTTP ${http_code}): $(basename "${ttl_file}")"
  fi
done

# --- Print triple count ---
echo ""
echo "[..] Querying triple count..."
count_query="SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
result=$(curl -sf -G \
  --data-urlencode "query=${count_query}" \
  -H "Accept: application/sparql-results+json" \
  "${GRAPHDB_URL}/repositories/${REPO_NAME}" 2>/dev/null || echo '{"results":{"bindings":[]}}')

triple_count=$(echo "$result" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data['results']['bindings'][0]['count']['value'])
except (KeyError, IndexError, json.JSONDecodeError):
    print('unknown')
" 2>/dev/null || echo "unknown")

echo "[OK] Total triples in repository: ${triple_count}"
echo ""
echo "=== Done ==="
echo "Explore at: ${GRAPHDB_URL}"
echo "SPARQL endpoint: ${GRAPHDB_URL}/repositories/${REPO_NAME}"
echo "Demo queries: sparql/demo_queries.md"
