# AGENTS.md for cmm-ai-automation

AI-assisted automation for Critical Mineral Metabolism (CMM) data curation. Builds a knowledge graph of microbial growth media, strains, and chemical ingredients by integrating Google Sheets, BacDive, MediaDive, NCBI, ChEBI, PubChem, and other biological databases.

**CLAUDE.md is a symlink to this file.** Both Claude Code and Codex read the same instructions.

## Repo management

- `uv` for dependency management (never `pip`)
- `just` for build recipes — run `just --list` to see all targets
- `mkdocs` for documentation
- `uv run` to run commands in the project environment

## Project structure

```
src/cmm_ai_automation/
├── schema/           # LinkML schema (edit this)
├── datamodel/        # Generated Python datamodel (do not edit)
├── clients/          # API clients: CAS, ChEBI, OLS, PubChem, MediaDive, NCBI node_normalization
├── scripts/          # CLI scripts for the data pipeline (primarily Click, some argparse)
├── store/            # Enrichment store (MongoDB-backed)
├── strains/          # Strain data: BacDive, culture collections, NCBI, consolidation, inference
├── transform/        # KGX transforms: growth media, growth preferences, BacDive source
├── reconcile/        # Reconciliation agent and KGX bridge
├── validation/       # Custom validation engine and schema validators
├── gsheets.py        # Google Sheets download and sync
└── _version.py       # Dynamic versioning from git tags
```

Other top-level directories:
- `project/` — Generated project files (do not edit)
- `tests/` — pytest tests
- `docs/` — mkdocs documentation
- `data/private/` — Downloaded sheets and intermediate data (gitignored)
- `output/kgx/` — Generated KGX node/edge TSVs

## Data infrastructure

- **MongoDB** — BacDive and MediaDive collections (local or remote, configured via `.env`)
- **ChromaDB** — NCBITaxon embeddings for semantic strain search
- **DuckDB** — Analytical queries over KGX exports
- **Neo4j** — Graph visualization and querying (Docker-based)
- **Google Sheets** — Source data from experimentalists; downloaded as TSV via gspread

## CLI entry points (pyproject.toml `[project.scripts]`)

- `download-sheets` — Download Google Sheets tabs as TSV
- `enrich-ingredients` — Enrich chemical ingredients via CAS/ChEBI/PubChem
- `enrich-to-store` — Enrich and persist to MongoDB enrichment store

Most pipeline work uses `just` targets rather than bare CLI commands.

## Key just targets

```bash
# Data acquisition
just download-normalized-kgx-sheets    # Google Sheets → TSV
just download-source-sink-sheets       # Experimentalist source/sink data
just load-bacdive                      # BacDive → MongoDB
just load-mediadive                    # MediaDive bulk → MongoDB (~10s)
just load-mediadive-details            # MediaDive details → MongoDB (3-4+ hours)

# KGX exports
just mediadive-kgx-export              # MongoDB → KGX nodes/edges TSVs
just kgx-export-bacdive                # BacDive MongoDB → KGX
just chemicals-kgx-from-curies         # ChEBI/PubChem → chemical KGX
just strains-kgx-from-curies           # NCBI/BacDive → strain KGX
just kgx-merge-all                     # Merge all KGX into single graph

# Neo4j
just neo4j-start                      # Start Neo4j Docker container
just neo4j-stop                       # Stop Neo4j Docker container
just neo4j-upload-merged               # Load merged KGX into Neo4j

# Quality
just qa                                # Full QA: lint, tests, schema, docs, smoke tests
just test                              # pytest
just lint-fast                         # ruff only
just gen-project                       # Regenerate Python datamodel from schema
```

## Testing

```bash
just test          # or: uv run pytest
just test-verbose  # with coverage
just qa            # full QA suite
```

- `@pytest.mark.integration` for tests requiring external APIs, MongoDB, etc.
- See [SKILL.md](SKILL.md) for complete bbop-skills testing guidelines (doctests, no mocks, parametrize, etc.)

## Related repositories

- [CultureBotAI/CMM-AI](https://github.com/CultureBotAI/CMM-AI) — Collaborating project (Marcin Joachimiak)
- [Knowledge-Graph-Hub/kg-microbe](https://github.com/Knowledge-Graph-Hub/kg-microbe) — Upstream microbial KG
- [berkeleybop/metpo](https://github.com/berkeleybop/metpo) — Microbial Phenotype Ontology

## Engineering standards

This repo follows [berkeleybop/bbop-skills](https://github.com/berkeleybop/bbop-skills). See [SKILL.md](SKILL.md) for the full guidelines on testing, CLI conventions, code style, and documentation.
