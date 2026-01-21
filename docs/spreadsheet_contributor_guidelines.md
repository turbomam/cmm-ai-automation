# Spreadsheet Contributor Guidelines

**Date:** 2026-01-21
**Applies to:**
- [BER CMM Data for AI](https://docs.google.com/spreadsheets/d/1h-kOdyvVb1EJPqgTiklTN9Z8br_8bP8KGmxA19clo7Q)
- [Media Components](https://docs.google.com/spreadsheets/d/1wzVvifG0a5MhcAynjSUAtaxIOWG4hmvyUy7NAbI4Ohc)

These guidelines help keep our data normalized, machine-readable, and ready for knowledge graph construction.

---

## Quick Checklist

Before submitting changes, verify:

- [ ] Every column has a non-empty, unique header name
- [ ] No trailing empty columns or rows
- [ ] Chemical names are spelled correctly (check PubChem/ChEBI)
- [ ] IDs use standard prefixes (CHEBI:, PUBCHEM.COMPOUND:, bacdive:, etc.)
- [ ] Units are consistent within each column
- [ ] No merged cells
- [ ] Provenance/source links are included for new data

---

## Column Headers

### Do

```
id | name | concentration_mM | source_url
```

- Use lowercase with underscores (`snake_case`)
- Be specific: `concentration_mM` not just `concentration`
- Include units in header if all values share the same unit
- Every column MUST have a unique, non-empty header

### Don't

```
  | Name | Concentration | link |   |   |
```

- Empty column headers (causes parsing errors)
- Trailing empty columns (causes duplicate header errors)
- Spaces in header names (use underscores)
- Duplicate header names (data will be lost)

---

## Identifiers and CURIEs

### Preferred ID Formats

| Entity Type | Prefix | Example | Where to Find |
|-------------|--------|---------|---------------|
| Chemicals | `CHEBI:` | `CHEBI:17790` | [ChEBI](https://www.ebi.ac.uk/chebi/) |
| Chemicals (no ChEBI) | `PUBCHEM.COMPOUND:` | `PUBCHEM.COMPOUND:887` | [PubChem](https://pubchem.ncbi.nlm.nih.gov/) |
| Taxa | `NCBITaxon:` | `NCBITaxon:408` | [NCBI Taxonomy](https://www.ncbi.nlm.nih.gov/taxonomy) |
| Strains | `bacdive:` | `bacdive:12896` | [BacDive](https://bacdive.dsmz.de/) |
| Publications | `PMID:` or `doi:` | `PMID:23646164` | [PubMed](https://pubmed.ncbi.nlm.nih.gov/) |
| Media | `mediadive.medium:` | `mediadive.medium:104c` | [MediaDive](https://mediadive.dsmz.de/) |

### Do

```
CHEBI:17790
PUBCHEM.COMPOUND:887
NCBITaxon:408
bacdive:12896
doi:10.1371/journal.pone.0062957
```

### Don't

```
17790                    (missing prefix)
ChEBI:17790              (wrong case - use CHEBI)
https://www.ebi.ac.uk/chebi/searchId.do?chebiId=17790  (full URL instead of CURIE)
methanol                 (name instead of ID)
```

---

## Chemical Names and Formulas

### Spelling Matters

Chemical names must be spelled correctly for automated lookups to work.

| Wrong | Correct |
|-------|---------|
| Prosydium chloride | Praseodymium chloride |
| Calcium Chloride | calcium chloride (or CaCl₂) |
| MgSO4.7H2O | MgSO₄·7H₂O (use proper subscripts and middle dot) |

### Finding Correct Names

1. Search [PubChem](https://pubchem.ncbi.nlm.nih.gov/) for the chemical
2. Use the "IUPAC Name" or "Depositor-Supplied Synonyms"
3. Copy the ChEBI or PubChem ID for the `id` column

### Hydration States

Be specific about hydration:
- `calcium chloride` (anhydrous)
- `calcium chloride dihydrate` (CaCl₂·2H₂O)
- `calcium chloride hexahydrate` (CaCl₂·6H₂O)

These are different compounds with different molecular weights!

---

## Units and Concentrations

### Consistency Within Columns

All values in a column should use the same unit:

| concentration_mM |
|------------------|
| 30 |
| 1.45 |
| 0.5 |

NOT:

| concentration |
|---------------|
| 30 mM |
| 1.45 mM |
| 500 µM |  ← different unit! |

### Standard Unit Abbreviations

| Unit | Abbreviation |
|------|--------------|
| millimolar | mM |
| micromolar | µM (or uM) |
| nanomolar | nM |
| grams per liter | g/L |
| milligrams per liter | mg/L |
| percent weight/volume | % w/v |

### Put Units in Column Headers

If all values share a unit, put it in the header:

```
concentration_mM | lower_bound_mM | upper_bound_mM
```

---

## Empty Cells and Missing Data

### Conventions

| Meaning | Use |
|---------|-----|
| Data not yet entered | Leave cell empty |
| Value is known to be zero | `0` |
| Value is not applicable | `N/A` |
| Value is unknown | `unknown` or leave empty |

### Don't Use

- `?` (ambiguous)
- `-` (could be confused with negative number)
- `TBD` (use empty instead)
- Notes in data cells like "Amino acids?"

---

## Provenance and Sources

### Always Include Source

Every new data point should have a source. Add columns like:

| Column | Purpose | Example |
|--------|---------|---------|
| `source_url` | Link to original source | `https://pmc.ncbi.nlm.nih.gov/articles/PMC3639900/` |
| `source_pmid` | PubMed ID | `PMID:23646164` |
| `source_doi` | DOI | `doi:10.1371/journal.pone.0062957` |
| `source_notes` | How value was obtained | `Extracted from Table 2` |

### Source Column Examples

```
# Good
source_url: https://pmc.ncbi.nlm.nih.gov/articles/PMC3639900/
source_pmid: PMID:23646164

# Acceptable for internal data
source_notes: Lab measurement by [Name], 2026-01-15

# Not useful
source_url: (empty)
source_notes: found online
```

---

## Tab/Sheet Organization

### Naming Conventions

- Use descriptive names: `medium_kgx_nodes` not `Sheet3`
- Indicate relationship: `MP_media` and `MP_media_extended`
- Use underscores, not spaces: `growth_preferences` not `Growth Preferences`

### Avoid Duplication

If two tabs have overlapping data (e.g., `MP_media` and `MP_media_extended`):
- Keep ONE authoritative tab
- Archive or delete the incomplete version
- Or clearly document the relationship in a `_notes` tab

### KGX Tabs Pattern

For knowledge graph export, use paired tabs:
- `{domain}_kgx_nodes` - Node definitions (id, category, name, ...)
- `{domain}_kgx_edges` - Relationships (subject, predicate, object, ...)

---

## Data Types

### Numbers

- Store numbers as numbers, not text
- Don't include units in numeric cells (put units in header)
- Use period for decimal: `1.45` not `1,45`

### Text

- Avoid leading/trailing spaces
- Be consistent with capitalization

### Booleans

Use consistent values:
- `TRUE` / `FALSE` (preferred)
- `1` / `0`
- `yes` / `no`

NOT: `Yes`, `Y`, `true`, `True` (inconsistent)

---

## Common Mistakes to Avoid

### 1. Merged Cells
Never merge cells. They break CSV/TSV export and parsing.

### 2. Notes in Data Cells
```
# Wrong
Component: "Amino acids? limit 5-10 components"

# Right
Component: "Amino acids"
notes: "limit 5-10 components"
```

### 3. Formulas in Export Columns
If a column will be exported, use values not formulas.

### 4. Hidden Rows/Columns
Hidden data will still be exported and may cause confusion.

### 5. Inconsistent Row Ordering
If tabs relate to each other, keep rows in the same order or use explicit IDs to link them.

---

## Validation Tools

### Before Submitting

1. **Download as TSV** and open in a text editor to check for issues
2. **Check for trailing columns**: In Google Sheets, click the last column header and verify there's no data to the right
3. **Search for empty headers**: Ctrl+F for tab characters in the header row

### Automated Validation

Our `download-sheets` tool will report:
- Duplicate column headers
- Empty column headers (in non-trailing positions)
- Tabs that fail to parse

---

## Getting Help

- **Chemical ID lookup**: [UniChem](https://www.ebi.ac.uk/unichem/) maps between ChEBI, PubChem, and other databases
- **Strain ID lookup**: [BacDive](https://bacdive.dsmz.de/) is authoritative for bacterial strains
- **Ontology terms**: [OLS](https://www.ebi.ac.uk/ols/) searches across ontologies

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-21 | Initial version |
