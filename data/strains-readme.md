# Strains Data - Private/Curated

This directory contains manually curated and computationally enriched strain data that includes private/unpublished information from the research team.

## Files

### `strains.tsv`
**Source:** Manually derived from the team's Google Sheets workbook "strains" tab
**Provenance:** Human-curated data combining:
- Culture collection IDs
- Species taxonomic IDs  
- Growth characteristics
- Lab-specific annotations

**Do NOT commit to public repository** - contains unpublished research data

### `strains_merged.tsv` (if present)
**Source:** Manually merged in spreadsheet software (LibreOffice Calc) combining:
- Columns from `strains.tsv` (with suffix `_sub_or_mpj`)
- Columns from BacDive enrichment (with suffix `_mam`)
- Deduplication and conflict resolution

**Process:** **NOT programmatically generated** - this was a manual curation step
**Status:** Intermediate working file from prior analysis

### `strains_enriched.tsv` (if present)
**Source:** Computationally enriched from `strains_merged.tsv` or `strains.tsv`
**Process:** Enrichment via `scripts/enrich_strains.py` using:
- NCBI Taxonomy API
- BacDive API/MongoDB
- Culture collection web scraping
- Semantic search via ChromaDB

**Status:** Final enriched dataset for analysis

## Privacy & Access

All files in `data/private/strains/` are **ignored by git** and remain private.

**Planned:** One of these files (likely `strains.tsv` or a derivative) will eventually be added to the team's Google Sheets workbook for broader access.

**Current access:** Until then, contact Mark (repository owner) for access to these files.

## Regeneration

To regenerate enriched data:

```bash
# Enrich strains (requires API credentials)
uv run python -m cmm_ai_automation.scripts.enrich_strains \
  --input data/private/strains/strains.tsv \
  --output data/private/strains/strains_enriched.tsv
```

## See Also

- `data/private/` - Other downloaded Google Sheets tabs (may be publishable)
- `src/cmm_ai_automation/strains/` - Strain processing modules
- `src/cmm_ai_automation/scripts/enrich_strains.py` - Main enrichment script
