## Add your own just recipes here. This is imported by the main justfile.
## Note: .env is loaded via `set dotenv-load` in main justfile

# =============================================================================
# QA TARGETS
# =============================================================================

# Run all QA checks (linting, tests, schema, docs, smoke tests) - nothing runs twice
qa:
  uv run pre-commit run --all-files --hook-stage manual
  @echo "✓ Full QA complete"

# Alias for CI (same as qa)
ci: qa

# Run only linting checks (fast, skips tests/docs/schema)
lint-fast:
  uv run pre-commit run --all-files

# Run tests with verbose output and HTML coverage report
test-verbose:
  uv run pytest -m "" --cov --cov-report=term-missing --cov-report=html -v --durations=10

# =============================================================================
# FUNCTIONAL TARGETS - Data Pipeline Operations
# =============================================================================

# Clean KGX outputs only
# SAFE: Only removes KGX files, keeps other outputs
clean-kgx:
  rm -rf output/kgx/
  @echo "✓ Cleaned KGX outputs"

# Clean enrichment outputs (DuckDB store, KGX files, intermediate files)
# SAFE: Only removes generated files, not downloaded source data
clean-enrichment:
  rm -f data/enrichment.duckdb
  rm -rf output/
  @echo "✓ Cleaned enrichment outputs"

# Clean everything including downloaded sheets (full reset)
# WARNING: Will need to re-download from Google Sheets
clean-all: clean-enrichment
  rm -f data/private/*.tsv
  @echo "✓ Cleaned all data (sheets will be re-downloaded)"

# Full pipeline: download sheets → dedupe ingredients → enrich with spidering → export KGX
# REQUIRES: Google Sheets API, PubChem, ChEBI, CAS, Node Norm APIs
# NETWORK: yes, EXPENSIVE: many API calls
# WRITES: data/private/*.tsv, output/ingredients_unique.tsv, data/enrichment.duckdb, output/kgx/
ingredients-to-kgx:
  @echo "Step 1: Downloading sheets from Google..."
  uv run download-sheets
  @echo "Step 2: Extracting unique ingredients..."
  @mkdir -p output
  cut -f2 data/private/media_ingredients.tsv | tail -n +2 | sort -u | awk 'BEGIN{print "ingredient_name"}{print}' > output/ingredients_unique.tsv
  @echo "  Found $(wc -l < output/ingredients_unique.tsv | tr -d ' ') unique ingredients"
  @echo "Step 3: Enriching with iterative spidering and exporting KGX..."
  uv run enrich-to-store --input output/ingredients_unique.tsv --export-kgx --output output/kgx/ingredients --verbose
  @echo "✓ Pipeline complete: output/kgx/ingredients_nodes.tsv"

# Download all tabs from BER CMM Google Sheet as TSV files to data/private/
# REQUIRES: Google Sheets API credentials, NETWORK: yes, WRITES: data/private/*.tsv
download-sheets:
  uv run download-sheets

# Download specific tab(s) from Google Sheet
# REQUIRES: Google Sheets API credentials, NETWORK: yes, WRITES: data/private/{tab}.tsv
download-sheet tab:
  uv run download-sheets --tabs {{tab}}

# Enrich ingredients with PubChem data (optionally CAS)
# REQUIRES: PubChem API access, OPTIONAL: CAS API key, NETWORK: yes, WRITES: output file, CACHES: cache/*.json
enrich-ingredients input output:
  uv run enrich-ingredients --input {{input}} --output {{output}}

# Enrich ingredients with both PubChem and CAS data
# REQUIRES: PubChem + CAS API keys, NETWORK: yes, EXPENSIVE: CAS API has rate limits
enrich-ingredients-with-cas input output:
  uv run enrich-ingredients --input {{input}} --output {{output}}

# Load MediaDive data (media, solutions, ingredients) into MongoDB
# REQUIRES: MongoDB running on localhost:27017, NETWORK: yes, DESTRUCTIVE: drops/recreates collections
load-mediadive:
  uv run python -m cmm_ai_automation.scripts.load_mediadive_mongodb

# Load BacDive strain data into MongoDB
# REQUIRES: MongoDB, BacDive credentials in .env, NETWORK: yes, EXPENSIVE: many API calls, WRITES: MongoDB
load-bacdive:
  uv run python -m cmm_ai_automation.scripts.load_bacdive_mongodb

# Fetch detailed MediaDive data into MongoDB
# REQUIRES: MongoDB with mediadive.media collection, NETWORK: yes, EXPENSIVE: fetches details for all media
load-mediadive-details:
  uv run python -m cmm_ai_automation.scripts.load_mediadive_details

# Build NCBITaxon ChromaDB for semantic search
# REQUIRES: NCBITaxon OWL file, OpenAI API key, EXPENSIVE: OpenAI embeddings, WRITES: ChromaDB
build-ncbitaxon db_path:
  uv run python -m cmm_ai_automation.scripts.build_ncbitaxon_chromadb --db-path {{db_path}}

# Codify strains using NCBITaxon ChromaDB semantic search
# REQUIRES: ChromaDB built, input TSV, NETWORK: OpenAI API, WRITES: output TSV
codify-strains input output chroma_path:
  uv run python -m cmm_ai_automation.scripts.codify_strains --input {{input}} --output {{output}} --chroma-path {{chroma_path}}

# Enrich strains with BacDive, NCBI, and semantic data
# REQUIRES: Multiple APIs (BacDive, NCBI, OpenAI), ChromaDB, EXPENSIVE: many API calls, WRITES: output TSV
enrich-strains input output:
  uv run python -m cmm_ai_automation.scripts.enrich_strains --input {{input}} --output {{output}}

# Multi-source enrichment pipeline: enriches ingredients and stores in DuckDB
# REQUIRES: PubChem, ChEBI, CAS (optional), Node Normalization APIs, NETWORK: yes, WRITES: data/enrichment.duckdb
enrich-to-store:
  uv run enrich-to-store --input data/private/normalized/ingredients.tsv

# Multi-source enrichment with KGX export (complete pipeline)
# REQUIRES: Multiple APIs, NETWORK: yes, EXPENSIVE: many API calls, WRITES: DuckDB + KGX TSV files
enrich-and-export-kgx:
  uv run enrich-to-store --input data/private/normalized/ingredients.tsv --export-kgx --output output/kgx/ingredients

# Multi-source enrichment with limit for testing (first N ingredients)
# REQUIRES: Multiple APIs, NETWORK: yes, SAFE: limited scope, WRITES: DuckDB
enrich-to-store-test n='5':
  uv run enrich-to-store --input data/private/normalized/ingredients.tsv --limit {{n}} --verbose

# Export existing EnrichmentStore to KGX format (no API calls)
# REQUIRES: data/enrichment.duckdb exists, SAFE: read-only on APIs, WRITES: output/kgx/*.tsv
export-kgx:
  uv run python -c "from cmm_ai_automation.store.enrichment_store import EnrichmentStore; from pathlib import Path; store = EnrichmentStore(); store.export_to_kgx(Path('output/kgx/ingredients')); print('✓ KGX export complete')"

# =============================================================================
# KGX TARGETS - Knowledge Graph Exchange Operations
# =============================================================================

# Export strains to KGX format
# REQUIRES: data/private/strains.tsv, BacDive API, NCBI API, NETWORK: yes
# WRITES: output/kgx/strains_nodes.tsv, output/kgx/strains_edges.tsv
kgx-export-strains:
  @mkdir -p output/kgx
  uv run python -m cmm_ai_automation.scripts.export_strains_kgx
  @echo "✓ Strains export complete"

# Export growth preferences (strain-medium relationships) to KGX format
# REQUIRES: output/kgx/strains_nodes.tsv (run kgx-export-strains first), data/private/growth_*.tsv
# WRITES: output/kgx/growth_nodes.tsv, output/kgx/growth_edges.tsv
kgx-export-growth:
  @mkdir -p output/kgx
  uv run python -m cmm_ai_automation.scripts.export_growth_kgx
  @echo "✓ Growth export complete"

# Export media-ingredient composition edges to KGX format
# REQUIRES: data/private/media_ingredients.tsv
# WRITES: output/kgx/media_ingredients_nodes.tsv, output/kgx/media_ingredients_edges.tsv
kgx-export-media-ingredients:
  @mkdir -p output/kgx
  uv run python -m cmm_ai_automation.scripts.export_media_ingredients_kgx
  @echo "✓ Media ingredients export complete"

# Export all KGX files (strains, growth, media ingredients)
# REQUIRES: All source data files, NETWORK: API calls for strains
# WRITES: output/kgx/*.tsv
kgx-export-all: kgx-export-strains kgx-export-growth kgx-export-media-ingredients
  @echo "✓ All KGX exports complete"
  @ls -la output/kgx/

# Validate KGX files against Biolink Model
# NOTE: Validation errors for METPO/CMM prefixes are expected until they are
#       registered with Biolink. See GitHub issues:
#       - biolink/biolink-model#1666 (METPO prefix)
#       - biopragmatics/bioregistry#1794 (METPO in Bioregistry)
#       - biopragmatics/bioregistry#1795 (CMM in Bioregistry)
# WRITES: output/kgx/validation_report.json
kgx-validate:
  @echo "Validating KGX files (expected errors for unregistered METPO/CMM prefixes)..."
  uv run kgx validate -i tsv output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv \
    -o output/kgx/validation_report.json || true
  @echo "✓ Validation complete - see output/kgx/validation_report.json"

# Validate all KGX files
kgx-validate-all:
  @echo "Validating all KGX files..."
  uv run kgx validate -i tsv \
    output/kgx/strains_nodes.tsv output/kgx/strains_edges.tsv \
    output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv \
    -o output/kgx/validation_report.json || true
  @echo "✓ Validation complete - see output/kgx/validation_report.json"

# Transform KGX to N-Triples RDF format
# REQUIRES: KGX files exist, WRITES: output/kgx/*.nt
kgx-to-rdf:
  uv run kgx transform \
    -i tsv \
    -o output/kgx/cmm_graph \
    -f nt \
    output/kgx/strains_nodes.tsv output/kgx/strains_edges.tsv \
    output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv
  @echo "✓ RDF export complete: output/kgx/cmm_graph.nt"

# Transform KGX to JSONL format
# REQUIRES: KGX files exist, WRITES: output/kgx/*.jsonl
kgx-to-jsonl:
  uv run kgx transform \
    -i tsv \
    -o output/kgx/cmm_graph \
    -f jsonl \
    output/kgx/strains_nodes.tsv output/kgx/strains_edges.tsv \
    output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv
  @echo "✓ JSONL export complete: output/kgx/cmm_graph_nodes.jsonl, cmm_graph_edges.jsonl"

# Merge multiple KGX graphs into one
# REQUIRES: KGX files exist, WRITES: output/kgx/merged_*
kgx-merge:
  uv run kgx merge \
    -i tsv \
    -o output/kgx/merged \
    -f tsv \
    output/kgx/strains_nodes.tsv output/kgx/strains_edges.tsv \
    output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv
  @echo "✓ Merge complete: output/kgx/merged_nodes.tsv, merged_edges.tsv"

# Extract edge patterns from KGX files (unconstrained analysis)
# Unlike `kgx graph-summary`, this works without Biolink prefix registration.
# REQUIRES: KGX files exist, WRITES: output/kgx/edge_patterns.tsv
kgx-analyze:
  uv run python -m cmm_ai_automation.scripts.analyze_kgx_patterns output/kgx/ > output/kgx/edge_patterns.tsv
  @echo "✓ Analysis complete - see output/kgx/edge_patterns.tsv"

# =============================================================================
# NEO4J TARGETS - Local Graph Database
# =============================================================================

# Start local Neo4j instance (Docker)
# REQUIRES: Docker running, NETWORK: pulls neo4j image if needed
# ACCESS: http://localhost:7474 (browser), bolt://localhost:7687 (driver)
# CREDS: Set NEO4J_USER and NEO4J_PASSWORD in .env
neo4j-start:
  #!/usr/bin/env bash
  set -a; source .env; set +a
  echo "Starting Neo4j container..."
  docker run -d --name cmm-neo4j \
    -p 7474:7474 -p 7687:7687 \
    -v cmm-neo4j-data:/data \
    -e NEO4J_AUTH=${NEO4J_USER:-neo4j}/${NEO4J_PASSWORD:-neo4j} \
    -e NEO4J_PLUGINS='["apoc"]' \
    neo4j:5
  echo "✓ Neo4j starting at http://localhost:7474"
  echo "  Credentials from .env (NEO4J_USER/NEO4J_PASSWORD)"
  echo "  Wait ~30s for startup, then run: just neo4j-upload"

# Stop Neo4j container (preserves data)
neo4j-stop:
  docker stop cmm-neo4j || true
  docker rm cmm-neo4j || true
  @echo "✓ Neo4j stopped (data preserved in volume)"

# Remove Neo4j data volume (full reset)
neo4j-clean: neo4j-stop
  docker volume rm cmm-neo4j-data || true
  @echo "✓ Neo4j data volume removed"

# Upload KGX files to local Neo4j
# REQUIRES: Neo4j running (just neo4j-start), KGX files exist
neo4j-upload:
  #!/usr/bin/env bash
  set -a; source .env; set +a
  echo "Uploading KGX data to Neo4j..."
  uv run kgx neo4j-upload \
    -i tsv \
    -l ${NEO4J_URI:-bolt://localhost:7687} \
    -u ${NEO4J_USER:-neo4j} \
    -p ${NEO4J_PASSWORD:-neo4j} \
    output/kgx/strains_nodes.tsv output/kgx/strains_edges.tsv \
    output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv \
    output/kgx/media_ingredients_nodes.tsv output/kgx/media_ingredients_edges.tsv
  echo "✓ Upload complete - browse at http://localhost:7474"

# Check Neo4j status
neo4j-status:
  @docker ps --filter name=cmm-neo4j || echo "Neo4j not running"

# Generate graph summary statistics (via kgx library)
# NOTE: Output is degraded until METPO/CMM prefixes are registered with Biolink.
#       Categories and predicates using METPO terms will show as "unknown".
#       See GitHub issues: biolink/biolink-model#1666, biopragmatics/bioregistry#1794, #1795
# REQUIRES: KGX files exist, WRITES: output/kgx/summary.yaml, output/kgx/meta-kg.json
kgx-graph-summary:
  @echo "Generating graph summary (degraded output until METPO/CMM prefixes registered)..."
  uv run kgx graph-summary \
    -i tsv \
    -o output/kgx/summary.yaml \
    output/kgx/strains_nodes.tsv output/kgx/strains_edges.tsv \
    output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv
  uv run kgx graph-summary \
    -i tsv \
    -o output/kgx/meta-kg.json \
    --report-type meta-knowledge-graph \
    output/kgx/strains_nodes.tsv output/kgx/strains_edges.tsv \
    output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv
  @echo "✓ Graph summary complete - see output/kgx/summary.yaml and meta-kg.json"
