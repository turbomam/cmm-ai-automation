# CMM-AI vs kg-microbe: Methods and Outcomes

**Purpose:** Document key differences in approach and resulting data quality between this repository and kg-microbe.

**Date:** 2026-01-07  
**Related Issue:** #123

---

## Executive Summary

While both projects create knowledge graphs for microbial data, cmm-ai-automation prioritizes strict KGX/Biolink compliance, explicit provenance tracking, and schema-driven validation. This leads to higher data quality but requires more upfront modeling work.

---

## 1. Prefix Strategy and CURIE Validity

### kg-microbe Approach

- Uses **generic prefixes** with source embedded in local ID:
  - `strain:bacdive_161512`
  - `medium:104c` (ambiguous - MediaDive? TogoMedium?)
  - `assay:API_zym_Cystine arylamidase` ⚠️ **spaces in CURIE**

**Issues** (see kg-microbe#430):
- 100 invalid CURIEs (0.05% of nodes) with spaces or extra colons
- Examples: `assay:API_zym_Acid phosphatase`, `strain:NRRL-:-NRS-341`
- Breaks RDF export and CURIE expansion

### CMM Approach

- Uses **scoped bioregistry-style prefixes**:
  - `bacdive.strain:161512`
  - `mediadive.medium:104c`
  - `NCBITaxon:408`

**Advantages:**
- Unambiguous source attribution
- Valid CURIE format (no spaces or invalid chars)
- URL-expandable via bioregistry

**Documentation:** See [best-practices.md](best-practices.md) and [#53](https://github.com/turbomam/cmm-ai-automation/issues/53)

---

## 2. Schema-Driven vs Ad-hoc Generation

### kg-microbe Approach

- TSV generation via custom Transform classes
- No formal schema validation before export
- Flexibility for rapid iteration

### CMM Approach

- **LinkML schema first**: `src/cmm_ai_automation/schema/cmm_ai_automation.yaml`
- Classes explicitly map to Biolink categories
- Enums with `meaning:` slots for ontology grounding
- Generated Python dataclasses via `gen-pydantic`

**Advantages:**
- Type safety and validation
- Self-documenting data structures
- Easier to detect incompatibilities early

**Documentation:** See [architecture.md](architecture.md)

---

## 3. Biolink Model Compliance

### kg-microbe Issues

From kg-microbe#438:
- **186,197 edges** use `biolink:capable_of` with wrong object type
- Objects categorized as `biolink:PhenotypicQuality` (EC enzyme codes)
- Biolink Model requires `Occurrent` (processes/activities) as range

From kg-microbe#436:
- Empty or inconsistent `relation` values in edges
- Non-CURIE `primary_knowledge_source` values
- Subject/object with spaces (see #430)

### CMM Approach

- Explicit Biolink category mappings in schema:
  ```yaml
  classes:
    Strain:
      class_uri: biolink:OrganismalEntity
    Taxon:
      class_uri: biolink:OrganismTaxon
    GrowthMedium:
      # Evaluating: ChemicalMixture vs custom METPO class
  ```
- Edge predicates validated against Biolink Model or METPO
- `kgx validate` target (currently non-blocking during METPO registration - see #91)

**Documentation:** See [#59](https://github.com/turbomam/cmm-ai-automation/issues/59) for alignment strategy

---

## 4. Entity Resolution and Provenance

### kg-microbe Approach

- Generates nodes/edges per source
- Post-merge deduplication via koza
- Limited provenance metadata

### CMM Approach

- **SourceRecord** class tracks which API provided which fields:
  ```yaml
  SourceRecord:
    slots:
      - source_name      # "pubchem", "chebi", "node_normalizer"
      - source_query     # Original query used
      - source_timestamp # When fetched
  ```

- **DataConflict** class records disagreements:
  ```yaml
  DataConflict:
    slots:
      - field_name
      - primary_source
      - primary_value
      - conflicting_source
      - conflicting_value
      - resolution  # enum: KEPT_PRIMARY, USED_CONFLICTING, MANUAL
  ```

**Advantages:**
- Transparent data lineage
- Reproducible enrichment
- Explicit conflict resolution

**Documentation:** See `src/cmm_ai_automation/store/enrichment_store.py`

---

## 5. Media Grounding Quality

### kg-microbe / CMM-AI Approach (from related project)

Analysis of mappings from CultureBotAI/CMM-AI project (which uses kg-microbe as target):

- **Method:** SQL `LIKE '%keyword%'` matching on media names
- **Quality:** 25% of mappings are WRONG due to substring matches
  - "MP" → "LAMPROBACTER" (contains "MP")
  - "MP" → "AMPHIBACILLUS" (contains "MP")

**Documentation:** See [kg_microbe_nodes_analysis.md](kg_microbe_nodes_analysis.md)

### CMM Approach (Planned)

- Structured mapping table with quality metadata:
  ```yaml
  MediaMapping:
    slots:
      - sheet_media_id
      - target_id
      - match_type  # enum: EXACT, VARIANT, CLOSE, WRONG
      - confidence  # 0.0-1.0
      - method      # "manual", "semantic_search", "sql_like"
      - curator     # Who validated it
  ```

- No semicolon-delimited multi-value fields (see #85)
- Explicit tracking of alignment quality (see #84)

---

## 6. Testing and Validation

### kg-microbe

- Has test suite (tox.ini)
- Does NOT run `kgx validate` in CI (see #81)
- Manual validation findings documented in issues

### CMM

- Pytest suite: 426 tests passing
- Pre-commit hooks: mypy, ruff, bandit, linkml-lint, pip-audit
- `kgx validate` target (non-blocking until METPO prefix registered)
- Integration tests marked separately

**Documentation:** See `pyproject.toml` and `.pre-commit-config.yaml`

---

## 7. KGX Field Usage and Provenance

### kg-microbe Field Issues

From kg-microbe#436 (BacDive edges.tsv violations):
- **Empty or inconsistent `relation` values** - unclear when to populate
- **Non-CURIE `primary_knowledge_source`** - violates infores: requirement
- **Missing required provenance** - knowledge_level, agent_type often absent

### CMM Approach: Strict KGX Compliance

**Edge Model** (`src/cmm_ai_automation/transform/kgx.py`):
```python
class KGXEdge(BaseModel):
    # Required fields
    subject: str                              # CURIE
    predicate: str                            # CURIE (biolink: or RO:)
    object: str                               # CURIE
    knowledge_level: Literal[                 # Biolink enum
        "knowledge_assertion",
        "logical_entailment",
        "prediction",
        "statistical_association"
    ]
    agent_type: Literal[                      # Biolink enum
        "manual_agent",
        "automated_agent",
        "computational_model",
        "not_provided"
    ]

    # Provenance (recommended)
    primary_knowledge_source: list[str] | None  # infores: CURIEs
    aggregator_knowledge_source: list[str] | None

    # Optional but useful
    id: str | None                            # Deterministic SHA256 hash
    publications: list[str] | None            # PMID: CURIEs
```

#### CMM Rules

**1. Predicate Selection**

- Use **Biolink predicates** when available:
  - `biolink:in_taxon` for taxonomy relationships
  - `biolink:capable_of` for enzyme/process assertions
  - `biolink:has_part` for composition

- Use **RO predicates** for fine-grained semantics:
  - `RO:0002162` (in taxon) - more specific than biolink
  - `RO:0001019` (contains) for ingredient relationships

- **Never use custom predicates** without Biolink/OBO registration

**2. Relation vs Predicate**

- `predicate` field: REQUIRED, always a CURIE
- `relation` field: DEPRECATED in Biolink 3.0+, do not use
- kg-microbe mixes these inconsistently

**3. Provenance Requirements**

All edges MUST have:
- `knowledge_level`: How was this asserted?
  - `"knowledge_assertion"` - direct database claim
  - `"prediction"` - ML/AI inferred
  - `"statistical_association"` - correlation-based

- `agent_type`: Who/what asserted it?
  - `"manual_agent"` - human curator
  - `"automated_agent"` - script/pipeline

- `primary_knowledge_source`: Where did it originate?
  - MUST use `infores:` prefix
  - Example: `["infores:bacdive"]`, `["infores:mediadive"]`
  - Register at https://github.com/biolink/information-resource-registry

**4. infores: Usage**

The `infores:` namespace identifies **information resources** (databases, APIs):

✅ **CORRECT:**
- `infores:bacdive` - BacDive database
- `infores:ncbi-taxonomy` - NCBI Taxonomy
- `infores:pubchem` - PubChem
- `infores:chebi` - ChEBI

❌ **WRONG:**
- `"BacDive"` - not a CURIE
- `bacdive:7142` - this is a strain ID, not a knowledge source
- `http://bacdive.dsmz.de` - not registered

**Before using a new infores:**, check:
1. Is it registered in the [Biolink information resource registry](https://github.com/biolink/information-resource-registry)?
2. If not, submit a registration PR

**5. Node Provenance**

Nodes use `provided_by` field (not `primary_knowledge_source`):
```python
KGXNode(
    id="NCBITaxon:408",
    category=["biolink:OrganismTaxon"],
    name="Methylorubrum extorquens",
    provided_by=["infores:ncbi-taxonomy"]
)
```

**Deduplication**: When same node from multiple sources, merge `provided_by`:
```python
# Before merge:
Node A: provided_by=["infores:ncbi"]
Node B: provided_by=["infores:bacdive"]

# After merge:
Node: provided_by=["infores:bacdive", "infores:ncbi"]  # sorted
```

**Documentation:**
- [bacdive_kgx_pipeline.md](bacdive_kgx_pipeline.md) - Provenance patterns
- [best_practices_strain_data_curation.md](best_practices_strain_data_curation.md) - CURIE requirements

---

## 8. Custom vs Standard KGX Fields

### kg-microbe Custom Fields

kg-microbe nodes/edges often include non-standard fields without documentation:
- Mixed use of Biolink standard vs custom properties
- Unclear which fields are queryable/meaningful
- No schema definition for validation

### CMM Approach: Lenient But Documented

**Node/Edge models use Pydantic with `extra="allow"`:**
```python
class KGXNode(BaseModel):
    # Required Biolink fields
    id: str
    category: list[str]

    # Optional Biolink fields  
    name: str | None = None
    description: str | None = None
    provided_by: list[str] | None = None
    xref: list[str] | None = None
    synonym: list[str] | None = None
    in_taxon: list[str] | None = None

    model_config = {"extra": "allow"}  # Permits custom fields
```

**Custom fields we add:**
- `type_strain: bool` - Type strain status (microbiology-specific)
- `biosafety_level: int` - Risk group (microbiology-specific)
- `strain_designation: str` - Lab designation (domain-specific)
- `has_genome: list[str]` - Genome assembly CURIEs

**Key difference**: Custom fields are:
1. **Documented** in LinkML schema with descriptions
2. **Typed** with explicit Python type hints
3. **Justified** as domain-specific extensions
4. **Proposed** to Biolink Model when broadly applicable

**Example from schema:**
```yaml
slots:
  type_strain:
    description: "Whether this strain is the nomenclatural type for the species"
    range: boolean
    comments:
      - "Per ICNP (International Code of Nomenclature of Prokaryotes)"
      - "Specific to microbiology, not general Biolink"
```

---

## 9. Documented Gray Zones / Incompatibilities

### Known kg-microbe Issues Referenced in CMM Docs

1. **Invalid CURIEs** (kg-microbe#430)
   - 100 nodes with spaces or extra colons
   - Documented in [best-practices.md](best-practices.md)

2. **Biolink Model violations** (kg-microbe#438)
   - Wrong object types for `capable_of` predicate
   - 186K+ edges affected

3. **Prefix ambiguity**
   - `medium:` could be MediaDive, TogoMedium, or local
   - CMM uses scoped prefixes: `mediadive.medium:`, `togomedium:M443`

4. **Media grounding quality**
   - Substring matching produces false positives
   - CMM plans explicit quality tracking (#84)

### CMM Intentional Divergences

| Design Choice | CMM | kg-microbe | Rationale |
|---|---|---|---|
| Prefix style | `bacdive.strain:12345` | `strain:bacdive_12345` | URL-expandable, unambiguous source |
| Schema | LinkML with Biolink mappings | Ad-hoc Python classes | Type safety, validation, documentation |
| Provenance | `SourceRecord` and `DataConflict` classes | Implicit in file structure | Transparent lineage, conflict resolution |
| Validation | CI + kgx validate | Manual + tox | Catch issues early |
| Entity IDs | Canonical namespace policy (#98) | Post-merge dedup | One ID per entity, explicit policy |

---

## 10. Areas of Potential Coordination

Despite differences, there are collaboration opportunities:

1. **MediaDive transform** (#114)
   - Both projects transform MediaDive
   - CMM documents composition model gaps (#111)
   - Could share findings on solution nesting

2. **BacDive data quality**
   - CMM has detailed BacDive JSON schema analysis
   - Could contribute irregular path handling patterns (#69)

3. **METPO term proposals** (#9, #106)
   - Both need cultivation-specific predicates
   - Could jointly propose terms to berkeleybop/metpo

4. **TogoMedium integration** (#75)
   - Neither project fully integrates TogoMedium yet
   - Could share SPARQL patterns

5. **MicroMediaParam mappings** (#19, #22)
   - kg-microbe references MicroMediaParam compound mappings
   - CMM ingredient enrichment (#23) could leverage same data

---

## 11. When to Use Each Approach

### Use kg-microbe When

- Need comprehensive microbial KG quickly
- Willing to accept some data quality issues
- Post-processing pipeline can handle invalid CURIEs
- Flexibility more important than strict validation

### Use CMM When

- Strict KGX/Biolink compliance required
- Need explicit provenance tracking
- Want schema-driven type safety
- Working on CMM-specific (lanthanide/rare earth) research
- Contributing data to Biolink ecosystem

---

## 12. References

### CMM Documentation

- [Architecture](architecture.md)
- [Best Practices](best-practices.md)
- [kg-microbe Nodes Analysis](kg_microbe_nodes_analysis.md)
- [Session Notes 2025-12-16](session-notes-2025-12-16.md)

### CMM Issues

- #53 - Standardize CURIE prefixes
- #58 - Document modeling differences from kg-microbe
- #59 - Align LinkML schema with kg-microbe patterns
- #67 - Adopt kg-microbe CLI pattern (download/transform/merge)
- #81 - Add KGX validate to CI
- #84 - Track alignment quality
- #85 - Avoid semicolon-delimited multi-value fields
- #91 - METPO prefix registration
- #98 - Canonical namespace policy
- #114 - Coordinate with kg-microbe MediaDive transform

### kg-microbe Issues

- kg-microbe#430 - Invalid CURIEs (spaces, colons)
- kg-microbe#436 - KGX format violations
- kg-microbe#438 - Biolink Model predicate range violations

### External Resources

- [Biolink Model](https://biolink.github.io/biolink-model/)
- [Bioregistry](https://bioregistry.io/)
- [METPO Ontology](https://github.com/berkeleybop/metpo)
- [KGX Documentation](https://github.com/biolink/kgx)

---

**Last Updated:** 2026-01-07  
**Maintainer:** @turbomam
