# Hypho + MP grounding status and next steps (since last download)

_Date generated: 2026-01-07_
_Updated: 2026-01-08 (added etymology 2a, MediaDive 162 comparison 2a-ii, 11+ Hypho variants 2a-iii, verified clustering 2a-iv, local PDF table 2b; corrected EDTA/methanol statements - EDTA reduces consistency, not blocks growth)_

This note captures what we’ve most recently established about **grounding “Hypho” and “MP” media** (± methanol) from your sheet-derived ingredient lists, plus a few related cleanups (MPYG, DSMZ:88), and concrete next steps for automation.

---

## 1) High-confidence grounding for MP (“Methylobacterium PIPES medium”)

### Canonical reference
The cleanest anchor for **MP medium** is:

- Delaney NF et al. (2013) *PLoS ONE*: **“Development of an optimized medium…”**  
  - PubMed: https://pubmed.ncbi.nlm.nih.gov/23646164/  
  - PMC full text: https://pmc.ncbi.nlm.nih.gov/articles/PMC3639900/  
  - Paper DOI: https://doi.org/10.1371/journal.pone.0062957

This paper explicitly defines **“MP (Methylobacterium PIPES) medium”** and contrasts it with older EDTA-chelated media.

### The recipe you should ground to
The practical “recipe object” you can treat as the canonical MP recipe is in the supplement:

- **Table S1** (MP medium + trace metals mix): https://doi.org/10.1371/journal.pone.0062957.s005

### Match to your sheet ingredient list
Your MP ingredient set matches the MP formulation extremely well:

- Buffer + phosphate system: **PIPES**, **K2HPO4·3H2O**, **NaH2PO4·H2O**
- Basal salts: **MgCl2·6H2O**, **(NH4)2SO4**, **CaCl2·2H2O**
- Chelator / metals: **sodium citrate** + the “C7” metal set including **tungstate** (this is a strong discriminator for MP vs Hypho)

**One modeling fix:** your “MP” list includes **disodium succinate hexahydrate**. In this literature lineage, **succinate and/or methanol are best modeled as carbon-source supplements**, not as part of the MP base definition. Create:
- `MP_base` (grounded to Table S1)
- `MP + succinate` (derived from MP_base; has_supplement succinate)
- `MP + methanol` (derived from MP_base; has_supplement methanol)
- optionally `MP + succinate + methanol` (common in practice)

---

## 2) Best current grounding for Hypho (“variant Hypho” lineage)

### Canonical reference
The same Delaney 2013 work provides a canonical “old media” / Hypho lineage and a recipe supplement:

- **Text S1** (variant-Hypho recipe): https://doi.org/10.1371/journal.pone.0062957.s006

### Match to your sheet ingredient list
Your Hypho ingredient set is dominated by an **EDTA-based trace metal mix** with:
- Disodium EDTA
- ZnSO4·7H2O, MnCl2·4H2O, FeSO4·7H2O, (NH4)6Mo7O24·4H2O, CuSO4, CoCl2·6H2O (and associated salts)

That “EDTA + Vishniac-like metals” pattern is consistent with the older Hypho lineage described in Delaney 2013 and its discussion of EDTA-chelated media.

### Hypho + methanol
Treat **methanol** as a *supplement / carbon source addition*:
- `Hypho_base` (grounded to Text S1)
- `Hypho + methanol` (derived from Hypho_base; has_supplement methanol)

---

## 2a) Etymology of "Hypho" - tracing to *Hyphomicrobium*

### Origin of the name

The name **"Hypho"** is short for ***Hyphomicrobium*** - a genus of methylotrophic bacteria that was studied alongside *Pseudomonas* AM1 (later reclassified as *Methylobacterium extorquens* AM1) in the foundational C1 metabolism research of the 1960s.

### Primary source (1961)

The earliest reference in the Delaney 2013 lineage is:

> Large PJ, Peel D, Quayle JR (1961) Microbial growth on C1 compounds. II. Synthesis of cell constituents by methanol- and format-grown *Pseudomonas* AM 1, and methanol-grown *Hyphomicrobium vulgare*. Biochemical Journal 81(3): 470-480.

- **DOI:** [10.1042/bj0810470](https://doi.org/10.1042/bj0810470)
- **PMID:** [14462405](https://pubmed.ncbi.nlm.nih.gov/14462405/)
- **PMC:** [PMC1243367](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1243367/) (free full text)

This paper studied both organisms growing on C1 compounds (methanol, format), and the cultivation medium used for *Hyphomicrobium* became the basis for what is now called "Hypho medium."

### The Vishniac trace elements connection

The Hypho medium recipe (Text S1 in Delaney 2013) includes a "Vishniac Trace Elements" solution, citing:

> Vishniac W & Santer M (1957) The Thiobacilli. Bacteriological Reviews 21:195.

The trace metal formula in Text S1 is a modified version (50-fold lower concentrations, pH 5.0 instead of 6.0) of the original Vishniac formula.

### Why the name persists

The "Hypho" name stuck in the *Methylobacterium* research community even though the medium is now primarily used for *M. extorquens* rather than *Hyphomicrobium* species. The Delaney 2013 paper refers to it as "variant-Hypho" to acknowledge both its heritage and the modifications made over decades of use.

### Key distinguishing feature from MP

The critical difference between Hypho and MP media is the **metal chelator**:
- **Hypho**: EDTA-chelated metals (Vishniac-style)
- **MP**: Citrate-chelated metals (C7 solution)

**Why MP was developed:** Delaney et al. 2013 found that EDTA-based Hypho medium produced **slower and inconsistent** growth on methanol - freshly prepared medium sometimes required days of "aging" before supporting growth, and results varied between batches and between plastic vs glass vessels. EDTA sequesters metals (especially calcium needed for PQQ-dependent methanol dehydrogenase), but growth *can* still occur under the right conditions. MP medium with citrate chelation provides **faster and more reproducible** growth, not because EDTA completely blocks methanol metabolism, but because citrate allows more consistent metal bioavailability.

**Important:** Methylotrophs *can* grow on EDTA-Hypho + methanol (as demonstrated in BER-CMM lab data). The issue is reproducibility and growth rate, not impossibility.

---

## 2a-ii) MediaDive 162 vs Delaney Hypho: same name, different media

**Critical finding:** The name "Hypho" or "Hyphomicrobium medium" refers to **multiple distinct formulations** that should not be treated as interchangeable.

### Side-by-side comparison

| Feature | MediaDive 162 | Delaney 2013 Hypho (Text S1) |
|---------|---------------|------------------------------|
| **Full name** | HYPHOMICROBIUM MEDIUM | variant-Hypho |
| **URL/DOI** | https://mediadive.dsmz.de/medium/162 | doi:10.1371/journal.pone.0062957.s006 |
| **Buffer type** | Phosphate | Phosphate |
| **Buffer conc.** | ~25 mM (Na₂HPO₄ + KH₂PO₄) | ~33 mM (K₂HPO₄ + NaH₂PO₄) |
| **(NH₄)₂SO₄** | 3.8 mM ✓ | 3.8 mM ✓ |
| **MgSO₄** | 0.8 mM ✓ | 0.8 mM ✓ |
| **pH** | 7.2–7.4 | ~6.75 |
| **EDTA** | **NO** | **YES** |
| **Chelator** | None (unchelated metals) | EDTA (Vishniac trace elements) |
| **Trace metals** | Fe, Mo, Mn, Ca only | Zn, Ca, Mn, Fe, Mo, Cu, Co |
| **Yeast extract** | 0.1 g/L | None |
| **Carbon source** | Methylamine 50 mM (included) | Treated as supplement |

### Implications

1. **Methanol compatibility**: Both can support methanol growth, but with different characteristics. MediaDive 162 (no EDTA) may provide more consistent growth. Delaney Hypho (EDTA) can support methanol growth but may show more batch-to-batch variability.

2. **Trace metal availability**: MediaDive 162 has fewer metals and no chelator. Delaney Hypho has a richer metal set but EDTA affects their bioavailability.

3. **Defined vs semi-defined**: MediaDive 162 includes yeast extract (semi-defined). Delaney Hypho is fully defined.

4. **pH difference**: Nearly 0.5 pH units apart - significant for some organisms.

### Recommendation

Do **not** treat "Hypho" as a single grounded concept. Instead:

- `mediadive:162` → "HYPHOMICROBIUM MEDIUM (DSMZ 162)" - no EDTA, semi-defined
- `doi:10.1371/journal.pone.0062957.s006` → "variant-Hypho (Delaney 2013)" - EDTA-chelated, defined

These share ancestry but are functionally different media with different expected growth outcomes on C1 substrates.

---

## 2a-iii) The "Hypho" explosion: 11+ variants in MediaDive alone

A search for "hypho" on MediaDive returns **at least 11 distinct media**:

https://mediadive.dsmz.de/media?search=hypho

| ID | Source | Name | Type | pH |
|----|--------|------|------|-----|
| 162 | DSMZ | HYPHOMICROBIUM MEDIUM | complex | 7.2 |
| 166 | DSMZ | HYPHOMICROBIUM STRAIN X MEDIUM | defined | 7.2 |
| 281 | DSMZ | HYPHOMONAS MEDIUM | complex | 7.5 |
| 619 | DSMZ | HYPHOMICROBIUM METHYLOVORUM MEDIUM | defined | — |
| 939 | DSMZ | METHYLOTROPHIC ARTHROBACTER AND HYPHOMICROBIUM MEDIUM | defined | 7.2–7.5 |
| 1355 | DSMZ | HYPHOMICROBIUM MEDIUM | defined | 6.0 |
| 1386 | DSMZ | HYPHOMICROBIUM MEDIUM SAF | defined | 6.0–6.5 |
| 1419 | DSMZ | HYPHOMICROBIUM MEDIUM | complex | 7.5 |
| 1420 | DSMZ | HALF STRENGHS HYPHOMICROBIUM MEDIUM | complex | 7.5 |
| J884 | JCM | HYPHOMICROBIUM MEDIUM | defined | — |
| J1088 | JCM | 0.3 x HYPHOMICROBIUM MEDIUM | — | — |

### Key observations

1. **pH range spans 1.5 units**: from 6.0 (DSMZ 1355, 1386) to 7.5 (DSMZ 281, 1419, 1420)

2. **Complex vs defined**: roughly half each - they are not interchangeable

3. **Multiple sources**: DSMZ and JCM have independent "Hyphomicrobium medium" definitions

4. **Different genera**: DSMZ 281 is for *Hyphomonas*, not *Hyphomicrobium*

5. **Dilution variants**: J1088 is "0.3x" strength; 1420 is "half strength"

6. **Strain-specific**: 166 is specifically for "strain X"

### Conclusion

**"Hypho" is not a medium. It is a naming convention for a family of 10+ distinct formulations.**

Any data pipeline that treats "Hypho" as a single grounded entity will produce incorrect mappings. Each variant must be resolved to its specific MediaDive ID or DOI.

---

## 2a-iv) MediaDive "Related media" clusters by NAME, not chemistry

MediaDive's "Related media" feature groups these three as related:

```
Related media for HYPHOMICROBIUM MEDIUM
162    HYPHOMICROBIUM MEDIUM
1355   HYPHOMICROBIUM MEDIUM
1419   HYPHOMICROBIUM MEDIUM
```

**But they are chemically distinct:**

| ID | Chelator | pH | Type | Methanol growth? |
|----|----------|-----|------|------------------|
| 162 | **None** | 7.2 | complex | Yes (consistent) |
| 1355 | **EDTA** (Vishniac) | 6.0 | defined | Yes (but may vary batch-to-batch) |
| 1419 | **NTA** (Hutner's) | 7.5 | complex | Unknown |

### Verified trace element lineages

**Vishniac EDTA family** (origin: Medium 69 - STARKEYA NOVELLA MEDIUM)
- 166, 1355, J884, J1088 all reference "Vishniac & Santer, 1957"
- Contains Na₂-EDTA (50g/L), ZnSO₄, CaCl₂, MnCl₂, FeSO₄, (NH₄)₆Mo₇O₂₄, CuSO₄, CoCl₂
- 939 uses EDTA but at extremely high concentration (50 g/L in trace solution)

**Hutner's NTA family** (origin: Medium 1419)
- 1419 defines trace element solution S2896
- 1420 explicitly derived from 1419 ("half strength")
- Uses nitrilotriacetic acid (NTA), not EDTA

**No chelator family**
- 162, 619, 1386
- 1386 is notable: uses **HEPES buffer** (closest to MP philosophy)

### Warning

**MediaDive "Related media" is a name-match grouping, not a chemistry match.**

Do not assume related media are interchangeable. A strain optimized for 162 (no EDTA, pH 7.2) may show different growth kinetics on 1355 (EDTA, pH 6.0) due to chelator and pH differences.

---

## 2b) Local copies of Delaney 2013 PDFs

The following PDF files are stored in `papers/` for offline reference:

| Filename | Content | Supplement ID |
|----------|---------|---------------|
| `pone.0062957.pdf` | Main paper: "Development of an Optimized Medium, Strain and High-Throughput Culturing Methods for *Methylobacterium extorquens*" | - |
| `pone.0062957.s005.pdf` | **Table S1: MP Medium recipe** (PIPES buffer, citrate-chelated C7 metals) | S1 Table |
| `pone.0062957.s006.pdf` | **Text S1: variant-Hypho medium recipe** (phosphate buffer, EDTA-chelated Vishniac metals) | S1 Text |

These supplements contain the authoritative recipes for both media formulations.

---

## 3) MPYG: the acronym collision to stop repeating

Your earlier sheet label expanded **MPYG** as “Methanol–Peptone–Yeast extract–Glucose”.

However, in external sources (ATCC), **MPYG** commonly means:

- **“Modified peptone-yeast extract glucose (MPYG)”** (ATCC Medium 1237)

ATCC pages for multiple strains explicitly list:
- “**ATCC Medium 1237: Modified peptone-yeast extract glucose (MPYG)**”
Example pages (showing the medium name):  
- https://www.atcc.org/products/33324  
- https://www.atcc.org/products/27208

**Recommendation:** treat your “MPYG = Methanol–…” as either:
- a misexpansion, or
- a project-specific medium that should be renamed to avoid collision with ATCC MPYG.

---

## 4) Green & Bousfield (1983): what it is (and isn’t)

You flagged “Green and Bousfield (1983)” as a citation associated with MPYG in your sheets.

We identified the precise reference as a taxonomy/nomenclature paper:

- DOI: https://doi.org/10.1099/00207713-33-4-875

This is not a “medium recipe definition” paper. It should not be used as a primary recipe citation for MPYG/Hypho/MP. If it’s attached to a medium in a sheet, treat that as a provenance/association error (likely: it was meant as strain/taxonomy support, not medium formulation support).

---

## 5) DSMZ:88 mismatch (strong evidence of sheet corruption)

DSMZ Medium **88** is **Sulfolobus medium**, not a Paracoccus “SM medium”:

- MediaDive/Bacmedia canonical page: https://bacmedia.dsmz.de/medium/88  
- DSMZ PDF: https://www.dsmz.de/microorganisms/medium/pdf/DSMZ_Medium88.pdf

So your sheet row:
- “DSMZ:88 (SM medium for Paracoccus)”
is almost certainly an ID/name mismatch (or column-sort drift). Mark it untrusted until re-grounded.

---

## 6) “Web-resolvable candidate” media that could be confused with Hypho

Because “Hypho” can be mentally conflated with “Hyphomicrobium”-named media, it’s useful to keep a couple of MediaDive anchors around as candidates when ingredient overlap suggests that confusion:

- MediaDive **Medium 619**: “Hyphomicrobium methylovorum medium”  
  https://mediadive.dsmz.de/medium/619

These are not automatically your Hypho, but they are strong candidate nodes for automated disambiguation when names drift.

---

## 7) A minimal deterministic classifier you can apply to sheet-derived ingredient sets

### MP-lineage signature (high precision)
If a recipe includes:
- **PIPES** + **citrate** + **tungstate**
→ classify as **MP-lineage** and ground to Table S1:  
https://doi.org/10.1371/journal.pone.0062957.s005

### Hypho-lineage signature (high precision)
If a recipe includes:
- **EDTA** plus the Vishniac-style metals set (Zn/Mn/Fe/Mo/Cu/Co…)
→ classify as **Hypho-lineage** and ground to Text S1:  
https://doi.org/10.1371/journal.pone.0062957.s006

### Carbon source handling (important for KG sanity)
If **methanol** or **succinate** appears:
- attach them as **supplements / carbon sources** to a base recipe, rather than redefining the base medium.

---

## 8) Next automation steps (short, practical)

1. **Mint canonical “recipe nodes”**:
   - `doi:10.1371/journal.pone.0062957.s005` as MP_base_recipe
   - `doi:10.1371/journal.pone.0062957.s006` as Hypho_base_recipe

2. **Normalize sheet ingredients** into a canonical ingredient vocabulary (even if it’s just your internal IDs initially), then auto-classify each medium by the signature rules above.

3. **Generate SSSOM mapping rows** for:
   - `project:MP` → `doi:...s005` (exactMatch)
   - `project:Hypho` → `doi:...s006` (exactMatch)
   - `project:MP+MeOH` → derived-from MP_base + has_supplement methanol (not a direct exactMatch to a different public record)

4. **Quarantine suspect rows**:
   - Any record where an external ID implies a different concept (e.g., DSMZ:88).
   - Any record where the citation is clearly non-recipe (e.g., Green & Bousfield 1983).

---

## 9) Quick “grounding anchors” we also touched recently (useful, stable nodes)

- MediaDive **J443**: LB (Luria-Bertani) agar  
  https://mediadive.dsmz.de/medium/J443

- MediaDive **R2A** family (modifications listing for medium 830)  
  https://mediadive.dsmz.de/modifications/830

---

_End._
