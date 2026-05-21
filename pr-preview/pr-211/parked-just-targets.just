# Parked just targets -- not yet restored to project.justfile
# See https://github.com/turbomam/cmm-ai-automation/issues/166
#
# Duplicates already removed:
#   - mediadive-kgx-export (already in project.justfile)
#   - kgx-merge (superseded by kgx-merge-all in project.justfile)
#
# Classification key:
#   INPUT:    where data comes from
#   OUTPUT:   what gets written
#   PLATFORM: external services or infrastructure required
#   PRIORITY: high / medium / low (for restoring to project.justfile)

# =============================================================================
# ENRICHMENT -- DuckDB pipeline (PubChem, ChEBI, CAS, Node Normalization)
# =============================================================================
# These use the EnrichmentStore (DuckDB) to cache multi-source chemical lookups.
# The enrich-to-store CLI entrypoint is registered in pyproject.toml.

# INPUT: TSV (ingredients list), OUTPUT: DuckDB
# PLATFORM: PubChem + ChEBI + CAS (optional) + Node Norm APIs
# PRIORITY: medium
enrich-to-store:
  uv run enrich-to-store --input data/private/normalized/ingredients.tsv

# INPUT: TSV, OUTPUT: DuckDB + KGX TSV
# PLATFORM: same as enrich-to-store
# PRIORITY: medium
enrich-and-export-kgx:
  uv run enrich-to-store --input data/private/normalized/ingredients.tsv --export-kgx --output output/kgx/ingredients

# INPUT: TSV (first N rows), OUTPUT: DuckDB
# PLATFORM: same as enrich-to-store
# PRIORITY: medium
enrich-to-store-test n='5':
  uv run enrich-to-store --input data/private/normalized/ingredients.tsv --limit {{n}} --verbose

# INPUT: DuckDB (existing), OUTPUT: KGX TSV (no API calls)
# PLATFORM: local only
# PRIORITY: medium
export-kgx:
  uv run python -c "from cmm_ai_automation.store.enrichment_store import EnrichmentStore; from pathlib import Path; store = EnrichmentStore(); store.export_to_kgx(Path('output/kgx/ingredients')); print('✓ KGX export complete')"

# INPUT: TSV, OUTPUT: enriched TSV
# PLATFORM: PubChem API (+ optional CAS)
# PRIORITY: low -- bodies are identical, likely superseded by enrich-to-store
enrich-ingredients input output:
  uv run enrich-ingredients --input {{input}} --output {{output}}

# PRIORITY: low -- identical body to enrich-ingredients
enrich-ingredients-with-cas input output:
  uv run enrich-ingredients --input {{input}} --output {{output}}

# =============================================================================
# KGX EXPORT -- Google Sheets curation data to KGX TSV
# =============================================================================
# These export from experimentalist source/sink sheet downloads (local TSVs)
# to KGX node/edge files. No external API calls.

# INPUT: experimentalist sheets (local TSV), OUTPUT: KGX TSV
# PLATFORM: local only
# PRIORITY: high
kgx-export-growth:
  @mkdir -p output/kgx
  uv run python -m cmm_ai_automation.scripts.export_growth_kgx
  @echo "✓ Growth export complete"

# INPUT: experimentalist sheets (local TSV), OUTPUT: KGX TSV
# PLATFORM: local only
# PRIORITY: high
kgx-export-media-ingredients:
  @mkdir -p output/kgx
  uv run python -m cmm_ai_automation.scripts.export_media_ingredients_kgx
  @echo "✓ Media ingredients export complete"

# Orchestrates kgx-export-growth + kgx-export-media-ingredients
# PRIORITY: high
kgx-export-all: kgx-export-growth kgx-export-media-ingredients
  @echo "✓ KGX exports complete (growth, media-ingredients)"
  @ls -la output/kgx/

# =============================================================================
# KGX EXPORT -- end-to-end pipeline (Google Sheets -> enrich -> KGX)
# =============================================================================

# INPUT: Google Sheets (download) + PubChem/ChEBI/CAS/NodeNorm APIs
# OUTPUT: KGX TSV + DuckDB
# PLATFORM: Google Sheets API, PubChem, ChEBI, CAS, Node Norm
# PRIORITY: high
ingredients-to-kgx:
  @echo "Step 1: Downloading sheets from Google..."
  uv run download-sheets --spreadsheet "{{experimentalist_source_sink_sheet_id}}" --output-dir {{experimentalist_source_sink_dir}}
  @echo "Step 2: Extracting unique ingredients..."
  @mkdir -p output
  cut -f2 {{experimentalist_source_sink_dir}}/media_ingredients.tsv | tail -n +2 | sort -u | awk 'BEGIN{print "ingredient_name"}{print}' > output/ingredients_unique.tsv
  @echo "  Found $(wc -l < output/ingredients_unique.tsv | tr -d ' ') unique ingredients"
  @echo "Step 3: Enriching with iterative spidering and exporting KGX..."
  uv run enrich-to-store --input output/ingredients_unique.tsv --export-kgx --output output/kgx/ingredients --verbose
  @echo "✓ Pipeline complete: output/kgx/ingredients_nodes.tsv"

# =============================================================================
# KGX EXPORT -- sampling variants (for testing)
# =============================================================================

# INPUT: TSV with CURIEs + BacDive MongoDB + NCBI API, OUTPUT: KGX TSV
# PLATFORM: MongoDB, NCBI API
# PRIORITY: low -- chemicals-kgx-sample already in project.justfile covers the pattern
strains-kgx-sample input id_field n:
  uv run python -m cmm_ai_automation.scripts.strains_kgx_from_curies \
    --input {{input}} \
    --id-field {{id_field}} \
    --sample-n {{n}} \
    --output-dir output/kgx/strains_sample

# =============================================================================
# KGX VALIDATION -- Biolink Model conformance
# =============================================================================

# INPUT: KGX TSV, OUTPUT: validation JSON
# PLATFORM: kgx tool (local)
# PRIORITY: high
kgx-validate:
  @echo "Validating KGX files (expected errors for unregistered METPO/CMM prefixes)..."
  uv run kgx validate -i tsv output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv \
    -o output/kgx/validation_report.json || true
  @echo "✓ Validation complete - see output/kgx/validation_report.json"

# INPUT: KGX TSV (multiple), OUTPUT: validation JSON
# PLATFORM: kgx tool (local)
# PRIORITY: high
kgx-validate-all:
  @echo "Validating all KGX files..."
  uv run kgx validate -i tsv \
    output/kgx/strains_nodes.tsv output/kgx/strains_edges.tsv \
    output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv \
    -o output/kgx/validation_report.json || true
  @echo "✓ Validation complete - see output/kgx/validation_report.json"

# INPUT: KGX TSV + custom config, OUTPUT: validation JSON
# PLATFORM: local (custom script + config/kgx_validation_config.yaml)
# PRIORITY: medium
validate-kgx-custom nodes='data/private/static/delaney-media-nodes.tsv' edges='data/private/static/delaney-media-edges.tsv':
  @if [ ! -f "{{nodes}}" ]; then echo "ERROR: Nodes file does not exist: {{nodes}}"; echo "Usage: just validate-kgx-custom <nodes.tsv> <edges.tsv>"; exit 1; fi
  @if [ ! -f "{{edges}}" ]; then echo "ERROR: Edges file does not exist: {{edges}}"; echo "Usage: just validate-kgx-custom <nodes.tsv> <edges.tsv>"; exit 1; fi
  @echo "Validating KGX files with custom context (DOIs and UUIDs allowed)..."
  uv run python src/cmm_ai_automation/scripts/validate_kgx_custom.py \
    --nodes {{nodes}} \
    --edges {{edges}} \
    --config config/kgx_validation_config.yaml \
    --output output/kgx/validation_report.json

# =============================================================================
# KGX TRANSFORM -- format conversion (TSV to other formats)
# =============================================================================

# INPUT: KGX TSV, OUTPUT: RDF N-Triples
# PLATFORM: kgx tool (local)
# PRIORITY: low -- unclear if RDF is consumed downstream
kgx-to-rdf:
  uv run kgx transform \
    -i tsv \
    -o output/kgx/cmm_graph \
    -f nt \
    output/kgx/strains_nodes.tsv output/kgx/strains_edges.tsv \
    output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv
  @echo "✓ RDF export complete: output/kgx/cmm_graph.nt"

# INPUT: KGX TSV, OUTPUT: JSONL
# PLATFORM: kgx tool (local)
# PRIORITY: low -- unclear if JSONL is consumed downstream
kgx-to-jsonl:
  uv run kgx transform \
    -i tsv \
    -o output/kgx/cmm_graph \
    -f jsonl \
    output/kgx/strains_nodes.tsv output/kgx/strains_edges.tsv \
    output/kgx/growth_nodes.tsv output/kgx/growth_edges.tsv
  @echo "✓ JSONL export complete: output/kgx/cmm_graph_nodes.jsonl, cmm_graph_edges.jsonl"

# =============================================================================
# KGX ANALYSIS -- graph introspection
# =============================================================================

# INPUT: KGX TSV directory, OUTPUT: edge pattern TSV
# PLATFORM: local (custom script)
# PRIORITY: medium
kgx-edge-patterns-merged:
  uv run python -m cmm_ai_automation.scripts.edge_patterns_merged output/kgx/ > output/kgx/edge_patterns.tsv
  @echo "✓ Analysis complete - see output/kgx/edge_patterns.tsv"

# INPUT: KGX TSV, OUTPUT: YAML summary + meta-KG JSON
# PLATFORM: kgx tool (local, degraded until prefix registration)
# PRIORITY: medium
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

# =============================================================================
# CHROMADB -- embedding/semantic search
# =============================================================================

# INPUT: TSV + ChromaDB, OUTPUT: coded TSV
# PLATFORM: ChromaDB, OpenAI API
# PRIORITY: low -- unclear if still in active use
codify-strains input output chroma_path:
  uv run python -m cmm_ai_automation.scripts.codify_strains --input {{input}} --output {{output}} --chroma-path {{chroma_path}}
