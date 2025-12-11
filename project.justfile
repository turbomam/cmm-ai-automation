## Add your own just recipes here. This is imported by the main justfile.

# =============================================================================
# QA TARGETS
# =============================================================================

# Run comprehensive QA: all tests, pre-commit hooks, coverage report, smoke tests
qa: test-all lint-all smoke-test-all

# Run all tests including integration tests with coverage
test-all:
  uv run pytest --cov --cov-report=term-missing --cov-report=html -v

# Run all linting and QA checks
lint-all:
  uv run pre-commit run --all-files
  uv run mypy src/cmm_ai_automation/
  uv run linkml-lint --config .linkml-lint.yaml src/cmm_ai_automation/schema/

# =============================================================================
# FUNCTIONAL TARGETS - Data Pipeline Operations
# =============================================================================

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
# SMOKE TESTS - Verify CLI scripts can be imported and show help
# =============================================================================

# Run all smoke tests (safe, fast, no network/API calls)
smoke-test-all: smoke-test-download-sheets smoke-test-enrich-ingredients smoke-test-enrich-to-store smoke-test-enrich-strains smoke-test-codify-strains smoke-test-build-ncbitaxon smoke-test-load-bacdive smoke-test-load-mediadive-details

smoke-test-download-sheets:
  @uv run download-sheets --help > /dev/null

smoke-test-enrich-ingredients:
  @uv run enrich-ingredients --help > /dev/null

smoke-test-enrich-to-store:
  @uv run enrich-to-store --help > /dev/null

smoke-test-enrich-strains:
  @uv run python -m cmm_ai_automation.scripts.enrich_strains --help > /dev/null

smoke-test-codify-strains:
  @uv run python -m cmm_ai_automation.scripts.codify_strains --help > /dev/null

smoke-test-build-ncbitaxon:
  @uv run python -m cmm_ai_automation.scripts.build_ncbitaxon_chromadb --help > /dev/null

smoke-test-load-bacdive:
  @uv run python -m cmm_ai_automation.scripts.load_bacdive_mongodb --help > /dev/null

smoke-test-load-mediadive-details:
  @uv run python -m cmm_ai_automation.scripts.load_mediadive_details --help > /dev/null
