## Add your own just recipes here. This is imported by the main justfile.

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
