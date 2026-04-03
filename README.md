# Tariff_consumption_link
Linking HS10 tariff codes to UCC consumer expenditure codes using a GPT-assisted pipeline

## Overview
This repository contains a high-precision concordance mapping between US Harmonized Tariff
Schedule 10-digit codes (HS10) and Consumer Expenditure Survey Universal Classification Codes
(UCC). The pipeline uses a hybrid approach: fast Python candidate generation followed by GPT
semantic judging (with a strict deterministic fallback when no API key is available).

The concordance supports **many-to-many** HS6↔UCC mappings with a `map_weight` field for each
link, enabling weighted aggregation in downstream Stata workflows.

## Files

### Input Data
- `hs10_desc.xlsx` — US 10-digit HTS codes with descriptions (23,472 codes)
- `ucc_codes_2017_2019_merged.csv` — UCC codes from the 2017–2019 Diary survey (681 codes)
- `hs6_2017.csv` — HS 6-digit reference codes (5,388 basic-level codes)

### Output Files
1. **`hs10_to_ucc_concordance.csv`** — Main concordance with `map_weight` (26,776 HS10–UCC pairs)
2. **`hs6_to_ucc_concordance.csv`** — HS6-level concordance for Stata `1:m` merge with `map_weight`
3. **`unmatched_hs10_codes.csv`** — HS10 codes without a consumer-goods UCC match
4. **`unmatched_ucc_codes.csv`** — UCC codes without HS10 matches (categorised by reason)
5. **`concordance_summary.txt`** — Summary statistics including HS6 coverage
6. **`suspicious_matches.csv`** — Flagged pairs for manual QA review (anti-trap patterns only)
7. **`match_decisions.jsonl`** — Full audit trail with per-HS10 decision records
8. **`concordance_methodology.md`** — Complete methodology documentation
9. **`generate_concordance.py`** — Pipeline script (replaces `create_concordance.py`)

### Legacy Files
- `create_concordance.py` — Old naive lexical matcher (superseded; kept for reference only)

## Quick Start

### Requirements
```bash
pip install pandas openpyxl
# Optional (enables GPT judging):
pip install openai
```

### Run (deterministic fallback — no API key needed)
```bash
python generate_concordance.py
```

### Run (with GPT semantic judging)
```bash
export OPENAI_API_KEY=sk-...
python generate_concordance.py
```

### CLI options
```
python generate_concordance.py [options]

Options:
  --input-hs10   PATH    HS10 Excel file (default: hs10_desc.xlsx)
  --input-ucc    PATH    UCC CSV file  (default: ucc_codes_2017_2019_merged.csv)
  --input-hs6    PATH    HS6 reference CSV for coverage stats (default: hs6_2017.csv)
  --min-score    FLOAT   Minimum deterministic score (default: 0.35)
  --max-candidates INT   Candidate UCC codes per HS10 for scoring (default: 20)
```

## Pipeline Architecture

```
hs10_desc.xlsx ──┐
                 ├──► Stage A: Candidate generation  ──► Stage B: GPT judging (optional)
ucc_codes.csv  ──┘    (token/synonym/anchor-noun)         (structured JSON output)
                                    │                                │
                                    └───────────────┬───────────────┘
                                                    ▼
                                        Stage C: Hard post-validation rules
                                        (anti-trap substring filters,
                                         chapter soft-penalty scoring, etc.)
                                                    │
                                                    ▼
                                    hs10_to_ucc_concordance.csv   (HS10-level, with map_weight)
                                    hs6_to_ucc_concordance.csv    (HS6-level, with map_weight)
                                    unmatched_hs10_codes.csv
                                    unmatched_ucc_codes.csv
                                    concordance_summary.txt
                                    suspicious_matches.csv
                                    match_decisions.jsonl
```

## `map_weight` Field

Each HS6↔UCC link carries a `map_weight` (0–1) representing the relative mapping confidence:

- At the **HS10 level**, `map_weight` is computed by normalising `match_score` values within
  each HS10 code so they sum to 1.0 across all accepted UCCs for that HS10.
- At the **HS6 level**, `map_weight` is the mean of HS10-level weights across all HS10 codes
  belonging to the HS6, then re-normalised to sum to 1.0 per HS6 code.

### Using `map_weight` in the Stata pipeline

```stata
* Merge concordance 1:m on hs6_code
merge 1:m hs6_code using "Data/Temp/hs6_to_ucc_concordance.dta"
keep if _merge == 3
drop _merge

* Compute mapping-weighted import share
bysort ucc_code date: egen total_imports = total(m_q1)
gen import_weight = m_q1 / total_imports if !mi(total_imports) & total_imports > 0
replace import_weight = 0 if mi(import_weight)

* Combined weight = import share × mapping confidence
gen combined_weight = import_weight * map_weight
* Re-normalise within ucc_code×date
bysort ucc_code date: egen total_comb = total(combined_weight)
replace combined_weight = combined_weight / total_comb if total_comb > 0

* Weighted tariff
gen tariff_weighted_new = tariff_weighted * combined_weight
replace tariff_weighted_new = 0 if mi(tariff_weighted_new)
collapse (sum) tariff_weighted_new, by(ucc_code ucc_description date)
```

If you prefer to ignore mapping weights for now, simply set `map_weight = 1` for all rows —
the many-to-many structure is preserved and the downstream code works unchanged.

## Matching Quality

### What improved over the old matcher
The previous `create_concordance.py` used naive substring/fuzzy matching that produced
70,497 pairs — many obviously wrong:

| Bad match (old) | Root cause | Status |
|---|---|---|
| `HORSES AND ASSES` → `TOLL PASSES` | `ASSES` ⊂ `PASSES` | ✅ Eliminated |
| `...IMMEDIATE SLAUGHTER` → `DIGITAL MEDIA PLAYERS` | `IMMEDIATE` ⊃ `MEDIA` | ✅ Eliminated |
| `LAYER-TYPE` hens → `AUDIO PLAYERS` | `LAYER` ⊂ `PLAYERS` | ✅ Eliminated |
| `AS SPECIFIED` → `UNSPECIFIED` | `SPECIFIED` ⊂ `UNSPECIFIED` | ✅ Eliminated |
| `COLD-WATER SHRIMPS` → `BOTTLED WATER` | generic `WATER` token | ✅ Eliminated |
| Leather goods → `BEEF` UCC codes | BOVINE synonym + no chapter check | ✅ Eliminated |
| Machinery → `SUGAR` UCC codes | no chapter check | ✅ Eliminated |
| `HAND-KNOTTED CARPET` → `HAND TOOLS` | generic `HAND` token | ✅ Eliminated |
| `WOMEN'S TROUSERS` → `WOMEN'S ACCESSORIES` | generic demographic token | ✅ Eliminated |

### Hard guardrails retained
1. **Whole-word tokenisation only** — substring matches rejected at token level
2. **Anchor noun requirement** — at least one non-generic noun must overlap
3. **Generic-token exclusion** — `FRESH`, `FROZEN`, `WATER`, `HAND`, `MEN`, `WOMEN`,
   `CARCASS` and ~80 other administrative/adjective/demographic tokens cannot alone drive a match
4. **Chapter compatibility soft penalty** — cross-domain HS chapter ↔ UCC prefix pairs
   receive a 55% score reduction (not a hard reject); very strong semantic matches can still pass
5. **Goods-only UCC pool** — financial/rental/service/utility/restaurant UCC codes
   excluded before candidate generation
6. **Anti-trap audit** — known false-positive patterns written to `suspicious_matches.csv`

### New features
- **Anchor-noun synonym matching** — SHEEP→LAMB, BOVINES→BEEF, SWINE→PORK, OVINES→LAMB/MUTTON,
  and ~40 other species/product synonyms for high-recall coverage
- **Synonym-match bonus** — +0.15 score when an HS10 anchor directly maps to a UCC anchor
  via the synonym lexicon (e.g., SHEEP→LAMB where LAMB is a UCC anchor)
- **MEAT/MEATS normalisation** — singular/plural forms treated as equivalent anchors
- **Many-to-many output** — all accepted HS10↔UCC pairs retained; no forced top-1
- **`map_weight`** — normalised confidence weight per link for Stata integration

### Confidence levels
| Level | Score | Interpretation |
|---|---|---|
| HIGH | ≥ 0.70 | Strong semantic overlap; recommend direct use |
| MEDIUM-HIGH | ≥ 0.55 | Good overlap; use with awareness |
| MEDIUM | ≥ 0.40 | Solid partial coverage |
| MEDIUM-LOW | ≥ 0.35 | Borderline acceptable; use with caution |
| LOW | < 0.35 | Rejected (not written to concordance) |

## Current Results (deterministic fallback)
- **Total pairs**: 26,776 HS10-UCC
- **HS10 matched**: 9,350 / 23,472 (39%)
- **HS6 matched**: 2,258 / 5,388 (41%) — **above 40% target**
- **UCC matched**: 317 / 534 consumer-goods UCCs (59%)
- **Confidence distribution**: HIGH 6,595 | MEDIUM-HIGH 4,673 | MEDIUM 6,393 | MEDIUM-LOW 9,115
- **Suspicious flags**: 0 (all known false-positive patterns eliminated)

> **Note**: Running with `OPENAI_API_KEY` set activates GPT judging over the top-20
> candidates per HS10, which can further improve recall for borderline consumer goods while
> maintaining precision through strict structured output.

## Downstream Stata Compatibility

The `hs6_to_ucc_concordance.csv` file is designed for `merge 1:m hs6_code` in Stata.
Required variables: `hs6_code`, `ucc_code`, `ucc_description`, `map_weight`, `confidence_level`.

The `map_weight` sums to exactly 1.0 per `hs6_code`, enabling direct use as a mixing weight
in weighted-average tariff calculations.

## Known Limitations
- **Negation context**: Phrases like `NOT FOR CIVIL AIRCRAFT` still carry `AIRCRAFT`
  as a token; GPT mode handles this correctly, deterministic mode may not.
- **Ingredient ambiguity**: `CHEESE CONTAINING COW'S MILK` may match the `MILK` UCC
  category; semantic judgment in GPT mode corrects this.
- **Part-vs-whole**: HS10 "parts for X" codes may match X consumer category because
  they share product nouns. Acceptable for trade-linkage purposes.
- **Industrial inputs**: ~59% of HS10 codes have no consumer-goods UCC equivalent
  (chemicals, metals, machinery, raw materials); this is expected and correct.

## Reproducibility
All outputs are deterministic given the same input files and Python environment.
The `match_decisions.jsonl` file records every HS10 code's candidate set, scores,
accept/reject decision, and reason — enabling full audit of any match or non-match.

## Dependencies
| Package | Purpose |
|---|---|
| `pandas` | Data loading and CSV output |
| `openpyxl` | Reading `.xlsx` input |
| `openai` (optional) | GPT semantic judging |

Tested with Python 3.10+.

