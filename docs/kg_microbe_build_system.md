# kg-microbe Build System Reference

**Date:** 2026-01-08
**Based on:** kg-microbe commit `cddcd79`
**Purpose:** Document build commands, available transforms, and architecture for CMM team use

---

## Quick Reference

```bash
cd ~/gitrepos/kg-microbe

# Full pipeline
poetry run kg download -y download.yaml -o data/raw
poetry run kg transform
poetry run kg merge

# Selective transform (recommended for CMM work)
poetry run kg transform -s bacdive -s bactotraits -s madin_etal -s mediadive

# Selective merge
poetry run kg merge -y merge.cmm.yaml  # (create custom config first)
```

---

## CLI Commands

### Download

```bash
poetry run kg download [OPTIONS]

Options:
  -y PATH    YAML config file (required, e.g., download.yaml)
  -o TEXT    Output directory (required, e.g., data/raw)
  -x         Download only first 5 kB (for testing)
  -i         Ignore cache, force re-download
```

**Re-running is safe:** Existing files are cached. Only use `-i` if you need fresh copies.

### Transform

```bash
poetry run kg transform [OPTIONS]

Options:
  -i PATH    Input directory (default: data/raw)
  -o TEXT    Output directory (default: data/transformed)
  -s SOURCE  Specific source(s) to transform (repeatable)
  --show-status / --no-show-status
```

**Available sources:**
```
-s [ontologies|bacdive|bakta|cog|kegg|mediadive|madin_etal|rhea_mappings|bactotraits]
```

### Merge

```bash
poetry run kg merge [OPTIONS]

Options:
  -y PATH      YAML merge config (default: merge.yaml)
  -p INTEGER   Number of processes
```

---

## Available Transforms

| Transform | Description | Input Data | Notes |
|-----------|-------------|------------|-------|
| `bacdive` | Microbial strain traits | `bacdive_strains.json` (Google Drive) | Core CMM source |
| `bactotraits` | Microbial traits database | `BactoTraits_databaseV2_Jun2022.csv` | Core CMM source |
| `madin_etal` | Condensed traits (bacteria-archaea-traits) | `madin_etal.csv` (GitHub) | Core CMM source |
| `mediadive` | Growth media, solutions, ingredients | MediaDive API + cached JSON | **New from Marcin** |
| `ontologies` | NCBITaxon, ChEBI, ENVO, GO, EC, METPO, UPA | OBO PURLs | Expensive (large ontologies) |
| `bakta` | Gene annotations | CMM-specific Bakta files | New in 2026-01 |
| `cog` | Clusters of Orthologous Groups | NCBI FTP (`cog-24.def.tab`) | New in 2026-01 |
| `kegg` | KEGG orthologs | KEGG REST API | New in 2026-01 |
| `rhea_mappings` | Rhea reaction → GO/EC mappings | Expasy FTP | Supporting data |

### CMM-Relevant Subset

For CMM work, you likely only need:
```bash
poetry run kg transform -s bacdive -s bactotraits -s madin_etal -s mediadive
```

The ontology transforms are expensive (especially NCBITaxon) and only needed if you're rebuilding from scratch or need updated ontology versions.

---

## Merge Configurations

Three merge configs exist:

| File | Contents | Use Case |
|------|----------|----------|
| `merge.yaml` | Full KG (all active sources) | Production releases |
| `merge.minimal.yaml` | bacdive + madin_etal only | Quick testing |
| `merge.current.yaml` | bacdive + madin_etal + bactotraits | Development |

### Creating a CMM-Specific Merge Config

```bash
cp merge.current.yaml merge.cmm.yaml
# Edit to add mediadive source, then:
poetry run kg merge -y merge.cmm.yaml
```

Example addition for `merge.cmm.yaml`:
```yaml
    mediadive:
      name: "mediadive"
      input:
        format: tsv
        filename:
          - data/transformed/mediadive/nodes.tsv
          - data/transformed/mediadive/edges.tsv
```

---

## Directory Structure

```
kg-microbe/
├── data/
│   ├── raw/              # Downloaded source files (cached)
│   │   ├── bacdive_strains.json
│   │   ├── mediadive.json
│   │   ├── mediadive/    # Cached MediaDive API responses
│   │   └── ...
│   ├── transformed/      # Transform outputs (nodes.tsv, edges.tsv per source)
│   │   ├── bacdive/
│   │   ├── bactotraits/
│   │   ├── mediadive/
│   │   ├── ontologies/
│   │   └── ...
│   └── merged/           # Final merged KG
│       └── merged-kg/
├── download.yaml         # Download configuration
├── merge.yaml            # Full merge configuration
├── merge.minimal.yaml    # Minimal merge configuration
├── merge.current.yaml    # Development merge configuration
└── kg_microbe/
    ├── transform.py      # Transform dispatcher
    └── transform_utils/  # Per-source transform code
        ├── bacdive/
        ├── mediadive/
        └── ...
```

---

## Architecture: Standard Tools vs Custom Code

| Component | Standard BBOP/KGX Tool | Custom kg-microbe Code |
|-----------|------------------------|------------------------|
| **Download** | `kghub-downloader` | Config only (`download.yaml`) |
| **Merge** | KGX merge library | Config only (`merge.yaml`) |
| **Transform** | **None** | Custom Python per source |
| **Node/Edge schema** | **None** | Hardcoded in `Transform` base class |

### The Transform Framework

kg-microbe uses a custom `Transform` base class (`kg_microbe/transform_utils/transform.py`) rather than KGX instantiators:

```python
# From transform_utils/transform.py lines 53-75
self.node_header = [
    ID_COLUMN,
    CATEGORY_COLUMN,
    NAME_COLUMN,
    DESCRIPTION_COLUMN,
    XREF_COLUMN,
    PROVIDED_BY_COLUMN,
    SYNONYM_COLUMN,
    IRI_COLUMN,
    OBJECT_COLUMN,      # ← Edge column in node header
    PREDICATE_COLUMN,   # ← Edge column in node header
    RELATION_COLUMN,    # ← Edge column in node header (deprecated in Biolink 3.x)
    SAME_AS_COLUMN,
    SUBJECT_COLUMN,     # ← Edge column in node header
    SUBSETS_COLUMN,
]
self.edge_header = [
    SUBJECT_COLUMN,
    PREDICATE_COLUMN,
    OBJECT_COLUMN,
    RELATION_COLUMN,
    PRIMARY_KNOWLEDGE_SOURCE_COLUMN,
]
```

**This explains why:**
- Node files have edge-specific columns (`subject`, `predicate`, `object`, `relation`) - baked into base class
- Edge files have only 5 columns (missing Biolink 3.x `knowledge_level`, `agent_type`)
- The `relation` column persists despite being deprecated

Each source has its own transform class that inherits from this base:
- `kg_microbe/transform_utils/bacdive/bacdive.py` → `BacDiveTransform`
- `kg_microbe/transform_utils/mediadive/mediadive.py` → `MediaDiveTransform`
- etc.

---

## Cleaning and Rebuilding

### Backup Current Outputs

```bash
cd ~/gitrepos/kg-microbe

# Backup transformed data
tar -czvf backup_transformed_$(date +%Y%m%d).tar.gz data/transformed/

# Backup merged data
tar -czvf backup_merged_$(date +%Y%m%d).tar.gz data/merged/
```

### Clean Intermediate Files

```bash
# Clean transformed data (cheap to regenerate)
rm -rf data/transformed/*

# Clean merged data (cheap to regenerate)
rm -rf data/merged/*

# Keep data/raw/ - expensive to re-download, and download is cached anyway
```

### Rebuild

```bash
# If you kept data/raw/:
poetry run kg transform -s bacdive -s bactotraits -s madin_etal -s mediadive
poetry run kg merge -y merge.cmm.yaml

# Full rebuild from scratch:
poetry run kg download -y download.yaml -o data/raw
poetry run kg transform
poetry run kg merge
```

---

## Anti-patterns and Reproducibility Concerns

### Pre-processed Files from Google Drive

**Problem:** Some "raw" downloads are actually pre-processed files hosted on Google Drive rather than fetched directly from authoritative sources.

From `download.yaml`:
```yaml
# BacDive - pre-processed JSON from Google Drive, not BacDive API
-
  url: gdrive:1b_UWdIvsIM81V5WdFedNoxN3R4UUf4F2
  local_name: bacdive_strains.json

# UniProt - pre-processed tarballs from Google Drive
-
  url: https://drive.google.com/file/d/1-aFVHE54t8HvcV4Z32hyTkmlXci07Y9g/view?usp=drive_link
  local_name: uniprot_proteomes.tar.gz
-
  url: https://drive.google.com/file/d/1PkqAp5v0IKs9qwu9mbK7gVeNaO-p3HsI/view?usp=drive_link
  local_name: uniprot_human.tar.gz
```

**Why this is problematic:**

| Issue | Impact |
|-------|--------|
| **Broken provenance chain** | Cannot trace data back to authoritative source |
| **Unknown processing** | What transformations were applied before upload? |
| **Version ambiguity** | Which version of the source data was used? |
| **Not reproducible** | Cannot regenerate from scratch without the Google Drive files |
| **Single point of failure** | If Google Drive link breaks, pipeline fails |
| **No update path** | How do you get fresh data from the actual source? |

**Best practice:** Download raw data directly from authoritative APIs/endpoints, then apply all transformations in documented, versioned code.

**Contrast with good examples in the same file:**
```yaml
# Good: Direct from authoritative source
-
  url: http://purl.obolibrary.org/obo/chebi.owl.gz
  local_name: chebi.owl.gz

# Good: Direct from source API
-
  url: https://mediadive.dsmz.de/rest/media
  local_name: mediadive.json

# Good: Direct from source repository
-
  url: https://github.com/bacteria-archaea-traits/bacteria-archaea-traits/blob/master/output/condensed_traits_NCBI.csv?raw=true
  local_name: madin_etal.csv
```

**Recommendation:** For any source using `gdrive:` or Google Drive URLs, document:
1. What the original authoritative source is
2. What processing was applied before upload
3. When the file was created and from what version of source data
4. How to regenerate the file from scratch

---

## Resource Requirements

From the README:

> The KG construction process, particularly the transform step involving trimming of NCBI Taxonomy for any KG and the steps involving the microbial UniProt dataset for KG-Microbe-Function and KG-Microbe-Biomedical-Function, is computationally intensive. Successful execution on a local machine may require significant memory resources (e.g., >500 GB of RAM).

**For CMM work:** The bacdive, bactotraits, madin_etal, and mediadive transforms are reasonable on a standard machine. Avoid `ontologies` transform unless necessary (NCBITaxon is huge).

---

## Documentation Status

| Aspect | Documented? | Location |
|--------|-------------|----------|
| Basic usage | ✅ Brief | README.md |
| CLI options | ✅ Via `--help` | CLI |
| Transform sources | ❌ Not listed | (this document) |
| Merge configs | ❌ Not explained | (this document) |
| Architecture | ❌ Not documented | (this document) |
| Custom schema issues | ❌ Not documented | See `kg_microbe_verification_2026-01-08.md` |

---

## Related Documentation

- [kg_microbe_verification_2026-01-08.md](kg_microbe_verification_2026-01-08.md) - Data quality verification
- [kg_microbe_risks.md](kg_microbe_risks.md) - Risk assessment for CMM
- [cmm_vs_kg_microbe.md](cmm_vs_kg_microbe.md) - Comparison of approaches
- [curie_prefix_strategy.md](curie_prefix_strategy.md) - CURIE/prefix planning

---

## See Also

- [KGX documentation](https://github.com/biolink/kgx)
- [kghub-downloader](https://github.com/monarch-initiative/kghub-downloader)
- [kg-microbe repository](https://github.com/Knowledge-Graph-Hub/kg-microbe)
