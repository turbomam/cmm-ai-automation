# Hypho + MP grounding status and next steps (since last download)

_Date generated: 2026-01-07_

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
