# Delaney Media KGX Schema Specification

## Overview

This document specifies the standardized KGX/Biolink schema for Delaney media data files, ensuring full compliance with KGX format while preserving complete scientific provenance without reification.

## Design Principles

1. **Standards Compliance**: Use standard Biolink Model properties wherever possible
2. **Provenance Preservation**: Maintain full audit trail to source publications via PROV-O aligned columns
3. **Flat Structure**: Avoid reification - use direct columns for quantitative measurements
4. **Semantic Precision**: Use Units Ontology (UO) CURIEs for all units
5. **Traceability**: Enable deterministic, unambiguous mapping back to source data

## Node Schema

### Required Columns

| Column | Description | Example | Standard |
|--------|-------------|---------|----------|
| `id` | CURIE identifier | `CHEBI:114249`, `doi:10.1371/journal.pone.0062957.s005` | KGX required |
| `name` | Human-readable name | `sodium dihydrogenphosphate monohydrate` | Biolink standard |
| `category` | Biolink Model category | `biolink:ChemicalEntity` | KGX required |

Nodes are kept minimal with only the three required KGX columns. Chemical properties and cross-references are stored on edges to preserve provenance context.

### Category Definitions

- **`biolink:ChemicalEntity`**: Individual chemical compounds (CHEBI, PubChem identifiers)
- **`biolink:ChemicalMixture`**: Stock solutions and defined mixtures (UUID or DOI identifiers)
- **`biolink:ComplexMolecularMixture`**: Complete culture media (DOI identifiers preferred)

### Example Node

```tsv
id	name	category
CHEBI:31440	copper(II) sulfate pentahydrate	biolink:ChemicalEntity
```

## Edge Schema

### Core KGX Columns (Required)

| Column | Description | Example | Standard |
|--------|-------------|---------|----------|
| `subject` | Source node CURIE | `doi:10.1371/journal.pone.0062957.s005` | KGX required |
| `predicate` | Biolink relationship | `biolink:has_part` | KGX required |
| `object` | Target node CURIE | `CHEBI:114249` | KGX required |
| `knowledge_level` | Type of assertion | `knowledge_assertion` | Biolink required |
| `agent_type` | Source of assertion | `manual_agent` | Biolink required |

### Provenance Columns (Required)

| Column | Description | Example | Alignment |
|--------|-------------|---------|-----------|
| `primary_knowledge_source` | Original data source | `infores:cmm` | Biolink standard |
| `publications` | Supporting publication | `PMID:23646164` | Biolink standard |
| `source_specification` | Verbatim source text | `NaH2PO4·H2O` | PROV-O `prov:value` |

### Source-Specified Columns (What PDF/Source Said)

| Column | Description | Example | Unit Column | UO Term |
|--------|-------------|---------|-------------|---------|
| `source_specification` | Verbatim text from source | `NaH2PO4·H2O` | N/A | N/A |
| `source_name` | Alternative name if given | `PIPES` | N/A | N/A |
| `source_concentration_value` | Concentration from source | `1.88` | `source_concentration_unit` | UO:0000063 (mM) |
| `source_role` | Role from source | `Buffer/Nutrient` | N/A | N/A |

**Critical Distinction**: These preserve what the PDF/paper actually specified. Never computed or normalized.

### Amount/Volume Columns (When Mass Was Given)

| Column | Description | Example | Unit Column | UO Term |
|--------|-------------|---------|-------------|---------|
| `amount` | Mass or quantity | `25.9` | `amount_unit` | UO:0000021 (gram) |
| `solution_volume_prepared` | Batch volume | `1` | `solution_volume_unit` | UO:0000099 (liter) |

**When to use**: Source gave mass/volume instead of concentration. Amount + volume allows calculating concentration.

### Calculated Columns (Computed from Mass/Volume)

| Column | Description | Example | Unit Column | UO Term |
|--------|-------------|---------|-------------|---------|
| `calculated_concentration` | Molar concentration | `0.1876934003` | `calculated_concentration_unit` | UO:0000062 (molar) |

**When present**: Only when concentration was calculated from `amount` and `solution_volume_prepared`. Empty when source specified concentration directly.

### Chemical Property Columns (Provenance-Critical)

| Column | Description | Example | Rationale |
|--------|-------------|---------|-----------|
| `molecular_mass` | Molecular mass in Daltons | `249.68` | On edges to show what MW was used to ground this assertion |
| `xref` | Cross-reference identifiers | `WIKIDATA:Q27114864` | On edges to show how this chemical was identified in context |

**Provenance Rationale**: Molecular mass and xrefs are stored on edges, not nodes, because they document the evidence used to ground each specific assertion. If there's an error or discrepancy in one source (e.g., wrong molecular mass), having these properties on the edge shows exactly what information was available when that grounding decision was made. This enables auditing which facts clarified the identification.

### Metadata Columns (Optional)

| Column | Description | Example | Standard |
|--------|-------------|---------|----------|
| `description` | Contextual notes | `Wikidata Q27288149 has no ChEBI; grounded to PUBCHEM` | Biolink standard |

### Example Edges

**Example 1: Source-specified concentration** (PDF said "1.88 mM"):
```tsv
subject	predicate	object	knowledge_level	agent_type	primary_knowledge_source	publications	source_specification	source_name	source_concentration_value	source_concentration_unit	source_role	amount	amount_unit	solution_volume_prepared	solution_volume_unit	calculated_concentration	calculated_concentration_unit	molecular_mass	xref	description
doi:10.1371/journal.pone.0062957.s005	biolink:has_part	CHEBI:114249	knowledge_assertion	manual_agent	infores:cmm	PMID:23646164	NaH2PO4·H2O		1.88	UO:0000063				UO:0000099			137.99
```
**Key**: `source_concentration_value` = 1.88, `source_concentration_unit` = UO:0000063 (mM). No calculated concentration - source specified it directly.

**Example 2: Mass-based with calculated concentration** (PDF gave mass, concentration computed):
```tsv
subject	predicate	object	knowledge_level	agent_type	primary_knowledge_source	publications	source_specification	source_name	source_concentration_value	source_concentration_unit	source_role	amount	amount_unit	solution_volume_prepared	solution_volume_unit	calculated_concentration	calculated_concentration_unit	molecular_mass	xref	description
uuid:a8a5a509-ba8c-4ae6-a6d3-98583066c984	biolink:has_part	CHEBI:114249	knowledge_assertion	manual_agent	infores:cmm	PMID:23646164	NaH2PO4 22.5 g (or 25.9 g NaH2PO4·H2O)					25.9	UO:0000021	1	UO:0000099	0.1876934003	UO:0000062	137.99		10X P solution stock
```
**Key**: `amount` = 25.9 g, `solution_volume_prepared` = 1 L → `calculated_concentration` = 0.1877 M. Source gave mass, not concentration.

## Unit Standardization

All measurement units must use Units Ontology (UO) CURIEs:

### Concentration Units

| Unit | Description | UO CURIE |
|------|-------------|----------|
| M | Molar | `UO:0000062` |
| mM | Millimolar | `UO:0000063` |
| μM | Micromolar | `UO:0000064` |

### Mass Units

| Unit | Description | UO CURIE |
|------|-------------|----------|
| g | Gram | `UO:0000021` |
| mg | Milligram | `UO:0000022` |
| μg | Microgram | `UO:0000023` |

### Volume Units

| Unit | Description | UO CURIE |
|------|-------------|----------|
| L | Liter | `UO:0000099` |
| mL | Milliliter | `UO:0000098` |
| μL | Microliter | `UO:0000101` |

## Provenance Strategy

### Scientific Integrity Requirements

The schema addresses specific concerns about data quality:

1. **Experimentalist Claims**: "Taxon T grows in medium M" requires traceable source
2. **LLM-Generated Data**: Noisy inputs must preserve original specification
3. **Manual Curation**: Human assertions tagged with `agent_type: manual_agent`

### Provenance Fields

- **`primary_knowledge_source`**: Links to institutional source (`infores:cmm`)
- **`publications`**: Links to peer-reviewed publication (PMID, DOI)
- **`source_specification`**: Preserves verbatim text from source (e.g., `NaH2PO4·H2O`)
- **`agent_type`**: Tracks who/what made the assertion:
  - `manual_agent`: Human curator
  - `text_mining_agent`: LLM extraction
  - `manual_validation_of_automated_agent`: Human-verified LLM output

### Audit Trail Example

```tsv
source_specification	primary_knowledge_source	publications	agent_type
NaH2PO4·H2O	infores:cmm	PMID:23646164	manual_agent
```

This enables:
- Tracing back to exact source text
- Verifying against original publication
- Identifying who/what made the claim
- Auditing LLM vs human contributions

## Validation

### Validation Script

```bash
just validate-kgx-custom
```

This runs the custom KGX validator that:
1. Monkey-patches `PrefixManager.is_curie` to allow slashes in DOIs
2. Adds custom prefixes (doi, uuid) from `config/kgx_validation_config.yaml`
3. Validates against KGX and Biolink Model requirements

### Validation Requirements

**Nodes must have:**
- Valid CURIE in `id` column
- Biolink category in `category` column
- Human-readable `name`

**Edges must have:**
- Valid subject/object CURIEs matching existing nodes
- Biolink predicate (e.g., `biolink:has_part`)
- `knowledge_level` and `agent_type` values
- At least one provenance field (publications or primary_knowledge_source)

**All edges pass if:**
```
SUCCESS: No validation errors found!
```

## Migration from Legacy Schema

### Deprecated Columns → New Standard

| Old Column | New Column | Notes |
|------------|------------|-------|
| `raw_specification` | `source_specification` | PROV-O aligned |
| `raw_name` | (removed) | Redundant with node `name` |
| `raw_molar_mass` | `molecular_mass` | Kept on edges for provenance |
| `raw_conc` + `raw_conc_units` | `concentration` + `concentration_unit` | UO CURIEs |
| `raw_role` | `description` | Biolink standard |
| `comments` | `description` | Biolink standard |
| `amount` + `units` | `amount` + `amount_unit` | Split and standardized |
| `liters_made` | `solution_volume_prepared` + `solution_volume_unit` | Split and standardized |
| `concentration_moles_per_liter` | `concentration` | With `concentration_unit: UO:0000062` |
| (new) | `xref` | Added to edges for cross-reference provenance |

### Breaking Changes

1. **No reification**: Quantities stored as flat columns, not QuantityValue objects
2. **UO CURIEs required**: All units must use Units Ontology identifiers
3. **Properties on edges**: molecular_mass and xref stay on edges to preserve provenance context
4. **Standard Biolink properties**: primary_knowledge_source, publications, description

## Best Practices

### When Adding New Data

1. **Identify entities properly**:
   - Prefer CHEBI IDs for chemicals
   - Use DOIs for published media
   - Generate UUIDs only when necessary

2. **Preserve source information**:
   - Copy exact specification text to `source_specification`
   - Link to publication via PMID or DOI
   - Tag with correct `agent_type`
   - Include molecular_mass if available (shows what MW was used for grounding)
   - Include xref if available (shows how the chemical was verified)
   - Document in `description` how xref relates to identifier choice

3. **Standardize measurements**:
   - Convert all concentrations to molar units when possible
   - Use UO CURIEs for all units
   - Store masses in grams or milligrams

4. **Document discrepancies**:
   - Use `description` field for notes about conflicts
   - Reference source documentation (see `docs/hypho_mp_grounding_and_next_steps.md`)

### Quality Checks

Before committing data changes:

```bash
# Validate KGX compliance
just validate-kgx-custom

# Run integration tests
uv run pytest tests/test_delaney_kgx_validation.py -v

# Check for common issues
grep -E "^[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*$" data/private/static/delaney-media-edges.tsv
```

## Resources

- [KGX Specification](https://github.com/biolink/kgx)
- [Biolink Model](https://biolink.github.io/biolink-model/)
- [Units Ontology](https://www.ebi.ac.uk/ols/ontologies/uo)
- [PROV-O](https://www.w3.org/TR/prov-o/)
- Project documentation: `docs/hypho_mp_grounding_and_next_steps.md`

## Related Files

- **Data**: `data/private/static/delaney-media-{nodes,edges}.tsv` (gitignored)
- **Config**: `config/kgx_validation_config.yaml`
- **Validation**: `src/cmm_ai_automation/scripts/validate_kgx_custom.py`
- **Build**: `project.justfile` (line 193-199: `validate-kgx-custom` target)
- **Source PDFs**: `papers/pone.0062957.s00{5,6}.pdf`
