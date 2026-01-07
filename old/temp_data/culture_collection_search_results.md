# Culture Collection Search Results

Search performed on: 2026-01-05
BacDive MongoDB: localhost:27017/bacdive/strains

## Summary

- **Total IDs searched**: 23 unique culture collection IDs
- **Found via aggregation**: 22
- **Not found**: 1 (NCIMB:13946)

## Critical Issue: DSM:1337 Found Wrong Strain!

**Input**: DSM:1337
**Expected**: Methylorubrum extorquens AM1 (BacDive ID: 7142)
**Actually found**: Heliomicrobium undosum BG29 (BacDive ID: 6124, DSM:13378)

**Root cause**: Regex match without word boundaries - "DSM 1337" matches "DSM **1337**8" as substring

## Search Results by ID

| Input ID | Found? | BacDive ID | DSM Number | Species | Designation | Notes |
|----------|--------|------------|------------|---------|-------------|-------|
| ATCC:4358 | ✓ | 33 | 5432 | Acidomonas methanolica | MB 58 | Different DSM # |
| ATCC:43883 | ✓ | 7170 | 5688 | Methylorubrum zatmanii | 135 | ✓ Correct |
| ATCC:47054 | ✓ | 12896 | 6125 | Pseudomonas putida | mt-2 KT2440 | ✓ Correct |
| CIP:101128 | ✓ | 7152 | 1819 | Methylobacterium radiotolerans | 0-1 | ✓ Correct |
| CIP:111632 | ✓ | 166193 | N/A | Paracoccus nototheniae | I-41R45 | ✓ Correct |
| DSM:11574 | ✓ | 167724 | 11574 | Paracoccus marcusii | MH1 | ✓ Correct |
| DSM:1337 | ✓ | 6124 | **13378** | Heliomicrobium undosum | BG29 | ⚠️ WRONG MATCH |
| DSM:14457 | ✓ | 7169 | 14457 | Methylorubrum rhodesianum | RXM | ✓ Correct |
| DSM:15083 | ✓ | 7174 | 15083 | Methylorubrum podarium | FM4 | ✓ Correct |
| DSM:16371 | ✓ | 7176 | 16371 | Methylobacterium aquaticum | GR16 | ✓ Correct |
| DSM:17706 | ✓ | 7225 | 17706 | Methylosinus sporium | 5 | ✓ Correct |
| DSM:17862 | ✓ | 13722 | 17862 | Paracoccus homiensis | DD-R11 | ✓ Correct |
| DSM:19779 | ✓ | 7192 | 19779 | Methylobacterium phyllosphaerae | CBMB27 | ✓ Correct |
| DSM:25844 | ✓ | 24173 | 25844 | Methylobacterium tarhaniae | N4211 | ✓ Correct |
| DSM:413 | ✓ | 3814 | **4133** | Crocinitomix catalasitica | H13 | ⚠️ Different DSM # |
| JCM:10893 | ✓ | 7172 | 11490 | Methylorubrum thiocyanatum | ALL/SCN-P | ✓ Correct |
| LMG:24788 | ✓ | 7195 | 21893 | Methylobacterium bullatum | F3.2 | ✓ Correct |
| NBRC:15843 | ✓ | 7166 | 5686 | Methylobacterium fujisawaense | O-31 | ✓ Correct |
| NBRC:16711 | ✓ | 13713 | 8537 | Paracoccus aminovorans | DM-82 | ✓ Correct |
| NCIMB:11131 | ✓ | 168221 | N/A | Methylosinus trichosporium | OB3b | ✓ Correct |
| NCIMB:13343 | ✓ | 7171 | 8832 | Methylorubrum aminovorans | TH-15 | ✓ Correct |
| NCIMB:13778 | ✓ | 7173 | 14458 | Methylorubrum suomiense | F20 | ✓ Correct |
| NCIMB:13946 | ✗ | - | - | - | - | NOT FOUND |

## DSM:1337 Reconciliation

The correct strain for DSM:1337 should be:

**Via `General.DSM-Number: 1337`**:
- BacDive ID: 7142
- Species: Methylorubrum extorquens
- Designation: 0355, AM-1, AM1
- Culture Collections: DSM 1337, ATCC 43645, NCIMB 9399, IAM 12631, JCM 2802, ...

**What was actually found via aggregation** (substring match):
- BacDive ID: 6124
- DSM Number: 13378 (contains "1337" as substring)
- Species: Heliomicrobium undosum
- Designation: BG29

## Recommended Fix

Use word-boundary regex pattern in aggregation:

```javascript
{
  $match: {
    $expr: {
      $regexMatch: {
        input: "$cc_field",
        regex: "(^|,\\s*)DSM 1337(\\s*,|$)"
      }
    }
  }
}
```

Or better: **Always use `General.DSM-Number` integer field for DSM IDs**:

```python
# For DSM IDs, use integer field (fast, exact)
if prefix == "DSM":
    doc = collection.find_one({"General.DSM-Number": int(number)})

# For other collections, use aggregation
else:
    doc = search_via_aggregation(collection, f"{prefix} {number}")
```

## NCIMB:13946 Investigation

Need to check:
1. Does this strain exist in BacDive at all?
2. Is it stored under a different ID format?
3. Is the culture collection string formatted differently?

Search commands to investigate:
```javascript
// Check if it exists in any form
db.strains.find({"External links": {$regex: /13946/}})
db.strains.find({"External links": {$regex: /NCIMB/}})
```

## Next Steps for Reconciliation Tool

1. **Fix regex**: Add word boundaries to prevent substring matches
2. **Prefer integer fields**: Use `General.DSM-Number` for DSM IDs
3. **Validate results**: Cross-check species/designation to detect wrong matches
4. **Handle missing**: Gracefully handle IDs not found in BacDive
5. **Multi-source reconciliation**: Cross-reference with NCBI, web scraping, etc.
