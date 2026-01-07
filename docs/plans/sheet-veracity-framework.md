# Plan: Sheet Data Veracity Framework

## Overview

Create a **general validation framework** that verifies data integrity across all sheets by cross-checking field values against authoritative sources (NCBI, BacDive, culture collections, etc.).

## Problem Statement

Current pipeline **trusts input data** and enriches missing fields, but doesn't **verify** existing values. This allows errors like:
- Bogus taxon IDs (e.g., 408004 = Streptomyces instead of Methylorubrum)
- Missing strain-level taxon IDs (e.g., 272630 for AM1 strain)
- Name-ID mismatches that go undetected
- Invalid genome accessions, culture collection IDs, etc.

## Architecture

```
src/cmm_ai_automation/
├── validation/                    # NEW: General validation framework
│   ├── __init__.py
│   ├── base.py                    # FieldValidator base class, Issue/Report
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── ncbi_taxon.py          # NCBITaxon ID validation
│   │   ├── culture_collection.py  # DSM, ATCC, JCM format validation
│   │   ├── genome_accession.py    # GCA/GCF validation
│   │   └── scientific_name.py     # Name↔taxon cross-validation
│   ├── schemas.py                 # Sheet column → validator mappings
│   └── engine.py                  # Validation orchestration
```

## Data Structures

```python
# validation/base.py

@dataclass
class ValidationIssue:
    sheet: str               # "strains.tsv", "growth_preferences.tsv", etc.
    row: int                 # Row number in sheet
    field: str               # Column name
    issue_type: str          # "invalid_id", "name_mismatch", "missing_value", etc.
    severity: str            # "error", "warning", "info"
    value: str | None        # The problematic value
    expected: str | None     # What we expected (if applicable)
    actual: str | None       # What we found from authoritative source
    message: str             # Human-readable description
    suggestion: str | None   # Suggested fix

@dataclass
class ValidationReport:
    sheets_checked: list[str]
    rows_checked: int
    issues: list[ValidationIssue]
    stats: dict[str, int]    # Counts by issue_type

# Base class for validators
class FieldValidator(ABC):
    """Base class for field validators."""

    @abstractmethod
    def validate(self, value: str, context: dict[str, Any]) -> list[ValidationIssue]:
        """Validate a single field value. Context contains other row values."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Validator name for reporting."""
        pass
```

## Validators

| Validator | Checks | Used By |
|-----------|--------|---------|
| `NCBITaxonValidator` | ID exists, name matches, hierarchy valid | strains, taxa_and_genomes |
| `NCBITaxonListValidator` | Validate semicolon-separated taxon IDs | strains (kg_microbe_nodes) |
| `CultureCollectionValidator` | Format valid (DSM:1234), optionally verify exists | strains |
| `GenomeAccessionValidator` | GCA/GCF format, optionally verify in NCBI | taxa_and_genomes |
| `ScientificNameValidator` | Cross-check against taxon_id in same row | all |
| `GrowthMediumValidator` | Validate against MediaDive vocabulary | growth_preferences |

## Sheet Schemas

```python
# validation/schemas.py

SHEET_SCHEMAS = {
    "strains.tsv": {
        "species_taxon_id": ("ncbi_taxon", {"check_rank": "species"}),
        "kg_microbe_nodes": ("ncbi_taxon_list", {"cross_check_name": "scientific_name"}),
        "culture_collection_ids": ("culture_collection_list", {}),
        "scientific_name": ("scientific_name", {"taxon_field": "species_taxon_id"}),
        "strain_id": ("culture_collection", {}),
    },
    "taxa_and_genomes.tsv": {
        "NCBITaxon id": ("ncbi_taxon", {}),
        "Genome identifier (GenBank, IMG etc)": ("genome_accession", {}),
        "Strain name": ("scientific_name", {"taxon_field": "NCBITaxon id"}),
    },
    "growth_preferences.tsv": {
        "strain id": ("culture_collection", {"allow_designation": True}),
        "Growth Media": ("growth_medium", {}),
    },
}
```

## Core Functions

### validation/engine.py

```python
def validate_sheet(
    sheet_path: Path,
    schema: dict[str, tuple[str, dict]] | None = None
) -> ValidationReport:
    """Validate a single sheet against its schema."""

def validate_all_sheets(
    sheets_dir: Path,
    schemas: dict[str, dict] = SHEET_SCHEMAS
) -> ValidationReport:
    """Validate all sheets in directory."""

def print_validation_report(report: ValidationReport) -> None:
    """Print human-readable report."""

def export_validation_report(report: ValidationReport, path: Path) -> None:
    """Export report as JSON or TSV for further processing."""
```

### validation/validators/ncbi_taxon.py

```python
def search_ncbi_taxonomy(query: str, retmax: int = 10) -> list[str]:
    """Search NCBI Taxonomy by name. Port from enrich_strains.py."""

class NCBITaxonValidator(FieldValidator):
    """Validate NCBI Taxon IDs."""

    def validate(self, value: str, context: dict) -> list[ValidationIssue]:
        # 1. Check ID exists
        # 2. Check name matches (if scientific_name in context)
        # 3. Check rank (if check_rank option set)
        # 4. Suggest strain-level taxon if missing

class NCBITaxonListValidator(FieldValidator):
    """Validate semicolon-separated NCBITaxon IDs (e.g., kg_microbe_nodes)."""
```

## PydanticAI Integration (Optional)

Leverage existing `reconcile/agent.py` for ambiguous cases:

```python
# validation/resolvers.py

class PydanticAIResolver:
    """Use LLM to resolve ambiguous validation issues."""

    def __init__(self, model: str = "openai:gpt-4o-mini"):
        self.reconciler = StrainReconciler(model)

    async def resolve_multiple_taxon_matches(
        self,
        query_name: str,
        candidate_taxon_ids: list[str]
    ) -> tuple[str | None, str]:
        """When NCBI search returns multiple hits, use LLM to pick best."""
        # Convert taxon IDs to StrainCandidates
        # Use reconciler.find_best_match()
        # Return (best_taxon_id, reasoning)

    async def resolve_name_taxon_conflict(
        self,
        expected_name: str,
        taxon_id: str,
        ncbi_name: str
    ) -> tuple[bool, str]:
        """Determine if name mismatch is due to synonymy or error."""
        # Ask LLM if names are synonyms/variants
        # Return (is_acceptable, reasoning)
```

**Use cases:**
1. NCBI search for "Methylorubrum extorquens AM1" returns multiple IDs → LLM picks 272630
2. Name "Sinorhizobium meliloti" doesn't exactly match NCBITaxon:382 "Ensifer meliloti" → LLM recognizes synonymy
3. Multiple culture collection IDs found → LLM determines if they refer to same strain

## Implementation Steps

### Phase 1: Core Framework
1. **Create `validation/base.py`**
   - `ValidationIssue` and `ValidationReport` dataclasses
   - `FieldValidator` abstract base class

2. **Create `validation/validators/ncbi_taxon.py`**
   - Port `search_ncbi_taxonomy()` from `enrich_strains.py`
   - `NCBITaxonValidator` class
   - `NCBITaxonListValidator` for semicolon-separated fields

3. **Create `validation/schemas.py`**
   - `SHEET_SCHEMAS` mapping columns to validators

4. **Create `validation/engine.py`**
   - `validate_sheet()` and `validate_all_sheets()`
   - Report printing and export

### Phase 2: Additional Validators
5. **Create `validation/validators/culture_collection.py`**
6. **Create `validation/validators/genome_accession.py`**
7. **Create `validation/validators/scientific_name.py`**

### Phase 3: CLI & Integration
8. **Create `scripts/validate_sheets.py`**
   - Options: `--sheet`, `--all`, `--json`, `--use-pydanticai`

9. **Create `validation/resolvers.py`** (optional)
   - PydanticAI integration for ambiguous cases

### Phase 4: Testing
10. **Create `tests/validation/` test suite**
    - Mock NCBI responses
    - Test each validator and issue type

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/cmm_ai_automation/validation/__init__.py` | CREATE |
| `src/cmm_ai_automation/validation/base.py` | CREATE |
| `src/cmm_ai_automation/validation/engine.py` | CREATE |
| `src/cmm_ai_automation/validation/schemas.py` | CREATE |
| `src/cmm_ai_automation/validation/validators/__init__.py` | CREATE |
| `src/cmm_ai_automation/validation/validators/ncbi_taxon.py` | CREATE |
| `src/cmm_ai_automation/validation/validators/culture_collection.py` | CREATE |
| `src/cmm_ai_automation/validation/validators/scientific_name.py` | CREATE |
| `src/cmm_ai_automation/validation/resolvers.py` | CREATE (optional) |
| `src/cmm_ai_automation/scripts/validate_sheets.py` | CREATE |
| `tests/validation/test_ncbi_taxon.py` | CREATE |
| `tests/validation/test_engine.py` | CREATE |

## Example CLI Output

```
$ uv run python -m cmm_ai_automation.scripts.validate_sheets --all

Validating sheets in data/private/...

strains.tsv (27 rows)
  ✓ strain_id: 27/27 valid
  ✗ species_taxon_id: 25/27 valid, 2 issues
  ✗ kg_microbe_nodes: 22/27 valid, 5 issues
  ✓ culture_collection_ids: 27/27 valid

taxa_and_genomes.tsv (215 rows)
  ✓ NCBITaxon id: 215/215 valid
  ...

VALIDATION REPORT
=================
Sheets checked: 3
Rows checked: 266
Issues found: 12

ERRORS (5):
  strains.tsv:3 [bogus_xref_taxon] kg_microbe_nodes contains NCBITaxon:408004
    → Actual: "Streptomyces sp. 13-32" (unrelated to Methylorubrum)
  ...

WARNINGS (7):
  strains.tsv:3 [missing_strain_taxon] Strain "AM-1" has no strain-level taxon ID
    → Suggestion: Use NCBITaxon:272630 "Methylorubrum extorquens AM1"
  ...

Summary by type:
  bogus_xref_taxon:     3
  missing_strain_taxon: 5
  invalid_taxon_id:     2
  name_mismatch:        2
```

## Success Criteria

- [ ] General framework works for any sheet/field type
- [ ] Detects bogus taxon IDs like 408004 in kg_microbe_nodes
- [ ] Discovers missing strain-level taxon IDs (e.g., 272630 for AM1)
- [ ] Validates name↔ID consistency against NCBI
- [ ] Schema-driven: add new sheets by adding to SHEET_SCHEMAS
- [ ] Optional PydanticAI for ambiguous resolution
- [ ] Rate-limits API calls appropriately
- [ ] Generates actionable report with suggestions
- [ ] All tests pass, `just lint-all` passes
