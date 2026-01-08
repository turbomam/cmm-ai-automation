# Strains Data - Private/Curated

This directory contains enriched strain data that includes private/unpublished information from the research team.

## Files

### `strains_enriched.tsv`
**Source:** Enriched strain data with columns from multiple sources, indicated by suffixes:
- `_sub_or_mpj` - original values from Google Sheets "strains" tab
- `_mam` - values from BacDive enrichment
- `_fresh_lookup` - re-queried values from NCBI/BacDive
- Agreement columns comparing values across sources

**Provenance:** ⚠️ **UNCLEAR** - The exact process that created this file is not fully documented. The original `strains.tsv` and intermediate `strains_merged.tsv` files have been removed.

**Note:** The existing `scripts/enrich_strains.py` does **NOT** produce this file format - it outputs different columns. A proper regeneration pipeline needs to be built (see GitHub issues #125, #126).

## Column Suffix Convention

| Suffix | Meaning |
|--------|---------|
| `_sub_or_mpj` | Original value from strains.tsv / Google Sheets |
| `_mam` | Value from BacDive enrichment |
| `_fresh_lookup` | Re-queried value (preferred when available) |

Priority for lookups: `_fresh_lookup` > `_sub_or_mpj` > `_mam`

## Privacy & Access

All files in `data/private/strains/` are **ignored by git** and remain private.

**Planned:** One of these files (likely `strains.tsv` or a derivative) will eventually be added to the team's Google Sheets workbook for broader access.

**Current access:** Until then, contact Mark (repository owner) for access to these files.

## Regeneration

⚠️ **Current state:** No script regenerates `strains_enriched.tsv` in its current format.

**To download fresh strains data from Google Sheets:**
```bash
uv run python -m cmm_ai_automation.scripts.download_sheets
```

**TODO:** Build proper pipeline to recreate enriched file from Google Sheets data - see issues #125, #126.

## See Also

- `data/private/` - Other downloaded Google Sheets tabs (may be publishable)
- `src/cmm_ai_automation/strains/` - Strain processing modules
- `src/cmm_ai_automation/transform/kgx.py` - Uses column suffixes in `transform_strain_row()`
- `docs/best_practices_strain_data_curation.md` - Data curation guidelines
