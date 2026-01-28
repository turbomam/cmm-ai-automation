# Spreadsheet Contributor Guidelines

**Date:** 2026-01-21
**Applies to:**
- [BER CMM Data for AI](https://docs.google.com/spreadsheets/d/1h-kOdyvVb1EJPqgTiklTN9Z8br_8bP8KGmxA19clo7Q)
- [Media Components](https://docs.google.com/spreadsheets/d/1wzVvifG0a5MhcAynjSUAtaxIOWG4hmvyUy7NAbI4Ohc)

These guidelines help keep our data normalized, machine-readable, and ready for knowledge graph construction.

---

## Critical Rule: No Semantic Formatting

**NEVER use colors, fonts, bold, italic, or any visual formatting to convey meaning.**

| Don't | Why It's Wrong | Do Instead |
|-------|----------------|------------|
| Red text = "needs review" | Lost on export to TSV/CSV | Add `status` column with value `needs_review` |
| Yellow highlight = "uncertain" | Not machine-readable | Add `confidence` column: `high`, `medium`, `low` |
| Bold = "important" | Invisible to code | Add `priority` column or `is_primary` boolean |
| Strikethrough = "deprecated" | Lost on export | Add `deprecated` column: `TRUE`/`FALSE` |
| Green background = "validated" | Can't be queried | Add `validation_status` column |

**Why this matters:**
- TSV/CSV exports strip all formatting
- Automated pipelines can't see colors
- Different people interpret colors differently
- Colorblind users can't distinguish red/green

**Allowed uses of formatting:**
- Header row styling (for human readability only)
- Conditional formatting that DUPLICATES a column value (not replaces it)
- Frozen rows/columns for navigation

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

---

## Data Dictionary

Legend for "Source" column:
- **H** = Human-populated (manual entry)
- **S** = Software-populated (automated enrichment)
- **H→S** = Human enters initial value, software may validate/enrich
- **S→H** = Software generates, human reviews/corrects

---

### BER CMM Data for AI Sheets

#### `medium_kgx_nodes` - Media definitions for KGX export

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | CURIE | H→S | Identifier (CHEBI:, uuid:, doi:, PUBCHEM.COMPOUND:) |
| `name` | text | H | Human-readable name |
| `category` | CURIE | H | Biolink category (biolink:ChemicalEntity, biolink:ChemicalMixture, etc.) |
| `pH` | number | H | pH value if applicable |
| `medium_prep_notes` | text | H | Preparation instructions |

#### `medium_kgx_edges` - Media composition relationships

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `subject` | CURIE | H | Medium ID (from medium_kgx_nodes) |
| `predicate` | CURIE | H | Relationship type (biolink:has_part) |
| `object` | CURIE | H→S | Ingredient ID (CHEBI:, PUBCHEM.COMPOUND:) |
| `knowledge_level` | enum | H | knowledge_assertion, not_provided |
| `agent_type` | enum | H | manual_agent, manual_validation_of_automated_agent |
| `primary_knowledge_source` | CURIE | H | infores: identifier |
| `publications` | CURIE | H | PMID: reference |
| `source_asserted_*` | various | H | Original values from source document |
| `calculated_*` | various | S | Computed from source values |
| `object_molecular_mass` | number | S | Looked up from ChEBI/PubChem |

#### `growth_kgx_nodes` - Growth-related entities

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | CURIE | H→S | Entity identifier |
| `category` | CURIE | H | Biolink category |
| `name` | text | H | Human-readable name |
| `strain_notes` | text | H | Notes about strain |
| `synonym` | text | H | Alternative names |

#### `growth_kgx_edges` - Growth relationships

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `subject` | CURIE | H | Strain ID (bacdive:) |
| `predicate` | CURIE | H | METPO:2000517 (grows_in) |
| `object` | CURIE | H | Medium ID |
| `knowledge_level` | enum | H | knowledge_assertion |
| `agent_type` | enum | H | manual_agent |
| `primary_knowledge_source` | CURIE | H | infores: identifier |

#### `strains` - Strain submission data

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `strain_id_submitted` | text | H | User-submitted strain identifier |
| `bacdive_id` | integer | S | BacDive database ID |
| `bacdive_url` | URL | S | Link to BacDive entry |
| `ncbi_url` | URL | S | Link to NCBI Taxonomy |
| `ncbi_taxon_strain` | integer | S | NCBI taxon ID for strain |
| `species_taxon_id_submitted` | integer | H | User-submitted species taxon |
| `ncbi_taxon_species_from_bacdive` | integer | S | Species taxon from BacDive lookup |
| `scientific_name_submitted` | text | H | User-submitted scientific name |
| `bacdive_name` | text | S | Name from BacDive |
| `name_agreement` | boolean | S | Whether names match |
| `strain_designation_submitted` | text | H | User strain designation |
| `strain_confirmed` | text | H | Curator confirmation |
| `type_strain_submitted` | boolean | H | Is this a type strain? |
| `bacdive_type_strain` | boolean | S | Type strain status from BacDive |
| `XoxF/ExaF/GDH` | boolean | H | Has XoxF gene? |
| `LutH/MluA` | boolean | H | Has LutH gene? |
| `lanM`, `lanP` | boolean | H | Lanthanide-related genes |
| `culture_collection_ids` | text | H→S | Collection IDs (DSM:, ATCC:, etc.) |
| `procurement_urls` | URL | H | Where to obtain strain |
| `biosafety_level` | integer | H→S | BSL-1, BSL-2, etc. |
| `kg_microbe_nodes` | CURIE | S | Matching kg-microbe node IDs |

#### `strains_assessed` - Strain validation results

All columns from `strains` plus comparison columns:
- `*_fresh_lookup` = S (new API lookup)
- `*_agreement` = S (computed comparison)
- `*_sub_only` / `*_lookup_only` = S (set differences)

#### `media_ingredients` - Ingredient library

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `ingredient_id` | text | H | Local identifier |
| `ingredient_name` | text | H | Human-readable name |
| `media_id` | text | H | Which medium uses this |
| `media_name` | text | H | Medium name |
| `ontology_id` | CURIE | H→S | CHEBI: or PUBCHEM.COMPOUND: ID |
| `ontology_label` | text | S | Name from ontology |
| `chemical_formula` | text | H→S | Chemical formula |
| `concentration` | number | H | Amount |
| `unit` | text | H | Unit of concentration |
| `role` | text | H | Function (buffer, mineral, carbon source) |
| `kg_microbe_nodes` | CURIE | S | Matching kg-microbe IDs |
| `notes` | text | H | Additional notes |
| `source` | text | H | Data provenance |

#### `growth_media` - Media catalog

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `placeholder URI` | URI | S | Temporary identifier (to be replaced) |
| `media_id` | text | H | Short identifier |
| `media_name` | text | H | Full name |
| `media_type` | enum | H | minimal, complex, defined |
| `alternative_names` | text | H | Synonyms |
| `description` | text | H | Purpose/description |
| `target_organisms` | text | H | What grows on this |
| `ph` | number | H | Target pH |
| `sterilization_method` | text | H | Autoclave, filter, etc. |
| `references` | text | H | Literature citations |
| `kg_microbe_nodes` | CURIE | S | Matching kg-microbe IDs |
| `source` | enum | H | extend, curate, etc. |

#### `genes_and_proteins` - Gene/protein catalog

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `gene or protein id` | text | H→S | UniProt or gene ID |
| `organism` | text | H | Source organism |
| `alternative name` | text | H | Synonyms |
| `annotation` | text | H→S | Functional annotation |
| `EC` | CURIE | S | EC number |
| `GO` | CURIE | S | GO terms |
| `CHEBI` | CURIE | S | Associated chemicals |
| `Source` | text | H | Data source |
| `Download URL` | URL | H | Data download link |

---

### Media Components Sheets

#### `MP_media` / `MP_media_extended` - MP medium formulation

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `Component` | text | H | Chemical name (use standard spelling!) |
| `Concentration` | text | H | Amount with unit (e.g., "30 mM") |
| `Solubility` | text | H→S | Solubility limit |
| `Lower bound` | text | H | Minimum effective concentration |
| `Upper bound` | text | H | Maximum safe concentration |
| `Limit of toxicity` | text | H | Toxicity threshold |
| `Bacteria` | text | H | Test organism |
| `link` | URL | H | Source reference |

**Note:** `MP_media_extended` has the same structure but with enriched data from literature.

#### `design1` / `design2` - Experimental design parameters

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `Component` | text | H | Chemical/parameter name |
| `Lower Bound` / `Min` | number | H | Minimum value to test |
| `Upper Bound` / `Max` | number | H | Maximum value to test |
| `Solubility` | text | H | Physical limit |
| `Limit of Toxicity` | text | H | Biological limit |
| `Physiological Concentration` | text | H | Typical in vivo level |
| `Bacteria/Organism` | text | H | Target organism |
| `Notes` | text | H | Additional context |
| `Source Link` | URL | H | Reference |

#### `Sheet3_IUPAC_NAMES_TO_SMILES_AND_MORFEUS_` - Chemical descriptors

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `compound` | text | H | IUPAC name (input) |
| `activity` | number | H | Biological activity |
| `SMILES` | text | S | SMILES string (from OPSIN) |
| `source` | text | S | Conversion source |
| `error` | text | S | Conversion errors |
| `mass` | number | S | Molecular mass |
| `radius` | number | S | Molecular radius |
| `charge` | number | S | Formal charge |
| `ip`, `ea` | number | S | Ionization potential, electron affinity |
| `homo`, `lumo` | number | S | Frontier orbital energies |
| `electrophilicity`, `nucleophilicity` | number | S | Morfeus descriptors |
| `sasa_*` | number | S | Solvent-accessible surface area |
| `disp_*` | number | S | Dispersion descriptors |
| `status` | enum | S | Conversion status (ok, error) |
| `pubchem_cid` | integer | S | PubChem compound ID |
| `inchi`, `inchikey` | text | S | InChI identifiers |
| `molecular_formula` | text | S | Chemical formula |

---

## Column Ownership Summary

### Human-Owned Columns (do not overwrite)
- Names, descriptions, notes
- Experimental parameters (concentrations, bounds)
- Curator assessments and confirmations
- Source/provenance information

### Software-Owned Columns (do not manually edit)
- `*_fresh_lookup` - API lookup results
- `*_agreement` - Computed comparisons
- `kg_microbe_nodes` - Cross-reference matches
- Morfeus descriptors, SMILES conversions
- `calculated_*` columns

### Shared Columns (human enters, software validates)
- `ontology_id` - Human enters CHEBI:, software may suggest corrections
- `culture_collection_ids` - Human enters, software validates format
- `ncbi_taxon_*` - Human may enter, software looks up authoritative value

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-21 | Initial version |
| 2026-01-21 | Added semantic formatting rule, data dictionary |
