# Tariff_consumption_link
Linking HS10 tariff codes to UCC consumer expenditure codes using a GPT-assisted pipeline

## Overview
This repository contains a high-precision concordance mapping between US Harmonized Tariff
Schedule 10-digit codes (HS10) and Consumer Expenditure Survey Universal Classification Codes
(UCC). The pipeline uses a hybrid approach: fast Python candidate generation followed by GPT
semantic judging (with a strict deterministic fallback when no API key is available).

## Files

### Input Data
- `hs10_desc.xlsx` — US 10-digit HTS codes with descriptions (23,472 codes)
- `ucc_codes_2017_2019_merged.csv` — UCC codes from the 2017–2019 Diary survey (681 codes)

### Output Files
1. **`hs10_to_ucc_concordance.csv`** — Main concordance (9,830 HS10–UCC pairs, HIGH precision)
2. **`unmatched_hs10_codes.csv`** — 18,153 HS10 codes without a consumer-goods UCC match
3. **`unmatched_ucc_codes.csv`** — 390 UCC codes without HS10 matches (categorised by reason)
4. **`concordance_summary.txt`** — Summary statistics (internally consistent with above files)
5. **`suspicious_matches.csv`** — Flagged pairs for manual QA review (9 pairs)
6. **`match_decisions.jsonl`** — Full audit trail with per-HS10 decision records
7. **`concordance_methodology.md`** — Complete methodology documentation
8. **`generate_concordance.py`** — Pipeline script (replaces `create_concordance.py`)

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
  --output-dir   DIR     Directory for outputs (default: current directory)
  --min-score    FLOAT   Minimum deterministic score (default: 0.40)
  --max-candidates INT   Candidate UCC codes per HS10 for GPT stage (default: 10)
  --no-gpt               Skip GPT judging even if OPENAI_API_KEY is set
```

## Pipeline Architecture

```
hs10_desc.xlsx ──┐
                 ├──► Stage A: Candidate generation  ──► Stage B: GPT judging (optional)
ucc_codes.csv  ──┘    (token/synonym/chapter filter)       (structured JSON output)
                                    │                                │
                                    └───────────────┬───────────────┘
                                                    ▼
                                        Stage C: Hard post-validation rules
                                        (veto generic-only matches, chapter
                                         incompatibility hard reject, etc.)
                                                    │
                                                    ▼
                                    hs10_to_ucc_concordance.csv
                                    unmatched_hs10_codes.csv
                                    unmatched_ucc_codes.csv
                                    concordance_summary.txt
                                    suspicious_matches.csv
                                    match_decisions.jsonl
```

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

### Hard guardrails
1. **Whole-word tokenisation only** — substring matches rejected at token level
2. **Anchor noun requirement** — at least one non-generic noun must overlap
3. **Generic-token exclusion** — `FRESH`, `FROZEN`, `WATER`, `PROCESSED`, `SPECIFIED`
   and ~60 other administrative/adjective tokens cannot alone drive a match
4. **Chapter compatibility hard reject** — HS chapter ↔ UCC prefix domain check;
   incompatible pairs receive score = 0 regardless of token overlap
5. **Goods-only UCC pool** — financial/rental/service/utility/restaurant UCC codes
   excluded before candidate generation
6. **Suspicious-match audit** — flagged pairs written to `suspicious_matches.csv`

### Confidence levels
| Level | Score | Interpretation |
|---|---|---|
| HIGH | ≥ 0.70 | Strong semantic overlap; recommend direct use |
| MEDIUM-HIGH | ≥ 0.55 | Good overlap; use with awareness |
| MEDIUM | ≥ 0.40 | Partial overlap; review before relying on these |
| LOW | < 0.40 | Rejected (not written to concordance) |

## Current Results (deterministic fallback)
- **Total pairs**: 9,830
- **HS10 matched**: 5,319 / 23,472 (22%) — most unmatched are industrial / non-consumer
- **UCC matched**: 291 / 681 (42%)
- **HIGH confidence**: 2,925 pairs
- **Suspicious flags**: 9 (all media-player electronics; legitimate matches)

> **Note**: Running with `OPENAI_API_KEY` set activates GPT judging over the top-10
> candidates per HS10, which can improve recall for borderline consumer goods while
> maintaining precision through strict structured output (JSON schema with accept/reject,
> confidence, and rationale fields).

## Known Limitations
- **Negation context**: Phrases like `NOT FOR CIVIL AIRCRAFT` still carry `AIRCRAFT`
  as a token; GPT mode handles this correctly, deterministic mode may not.
- **Ingredient ambiguity**: `CHEESE CONTAINING COW'S MILK` may match the `MILK` UCC
  category; semantic judgment in GPT mode corrects this.
- **Part-vs-whole**: HS10 "parts for X" codes may match X consumer category because
  they share product nouns. Acceptable for trade-linkage purposes.
- **Industrial inputs**: ~77% of HS10 codes have no consumer-goods UCC equivalent
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

