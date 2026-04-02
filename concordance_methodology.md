
# HS10-to-UCC Concordance Mapping Methodology

## Overview

This document describes the methodology used by `generate_concordance.py` to create a
high-precision concordance between US Harmonized Tariff Schedule 10-digit codes (HS10)
and Consumer Expenditure Survey Universal Classification Codes (UCC).

The pipeline uses a **hybrid approach**:
1. **Stage A — Candidate generation** (Python): fast lexical/synonym retrieval to shortlist
   plausible UCC candidates per HS10 code
2. **Stage B — GPT semantic judging** (optional): GPT reranks shortlisted candidates with
   strict structured output (JSON schema) when `OPENAI_API_KEY` is set
3. **Stage C — Hard post-validation** (Python): deterministic rules veto GPT approvals
   for known error patterns and domain incompatibilities

## Data Sources

1. **HS10 Codes**: `hs10_desc.xlsx` — 23,472 US 10-digit HTS codes with descriptions
2. **UCC Codes**: `ucc_codes_2017_2019_merged.csv` — 681 UCC codes from the 2017–2019
   Diary survey

Both datasets load codes as strings to preserve leading zeros.

---

## Stage A: Candidate Generation

### 1. Text normalisation and tokenisation

Descriptions are normalised to uppercase, then tokenised on whitespace and punctuation.
Tokens shorter than 3 characters are discarded.

### 2. Generic-token exclusion (`GENERIC_TOKENS`)

~70 high-frequency generic adjectives and administrative words are excluded from the anchor
set and from candidate lookup. These cannot alone drive a match. Examples:

```
FRESH, FROZEN, PROCESSED, LIVE, DRIED, SMOKED, SALTED, CANNED, WHOLE, GROUND,
OTHER, SPECIFIED, UNSPECIFIED, MISC, NESOI, NEC, MISCELLANEOUS, GENERAL, VARIOUS,
WEIGHING, CONTAINING, PRODUCTS, ITEMS, ARTICLES, PARTS, MATERIALS, FOOD,
AND, OR, WITH, FOR, FROM, BY, OF, THE, NOT, WATER, ...
```

**Rationale**: Previous matches like `COLD-WATER SHRIMPS` → `BOTTLED WATER`, or
`AS SPECIFIED` → `UNSPECIFIED` were caused by these generic tokens.

### 3. Anchor noun extraction

Tokens not in `GENERIC_TOKENS` become "anchor nouns". A match requires at least one
anchor noun to overlap (directly or via synonym). No match is accepted on generic tokens
alone.

### 4. Semantic synonym expansion (`HS_TO_UCC_SYNONYMS`)

~200 domain-specific synonyms (bidirectional) expand anchor tokens before candidate
retrieval. Examples:

| HS10 term | → UCC equivalent |
|---|---|
| `BOVINE` / `CATTLE` | `BEEF` |
| `SWINE` | `PORK` |
| `POULTRY` / `BROILER` / `FOWL` | `CHICKEN` |
| `TROUSERS` / `SLACKS` | `PANTS` |
| `SETTEE` / `DIVAN` | `SOFA` |
| `MEDICAMENT` | `MEDICINE` |
| `PERIODICAL` | `MAGAZINES` |

Generic or ambiguous terms (e.g., `PLANT`, `STOCK`) are intentionally **excluded** from
synonym maps to prevent cross-category false positives.

### 5. Whole-word-only matching

Tokenisation splits on word boundaries. Matching compares token sets (not substrings).
This eliminates classic substring traps:

| Bad pair | Root cause | Now |
|---|---|---|
| `HORSES AND ASSES` → `TOLL PASSES` | `ASSES` ⊂ `PASSES` | ✅ Rejected |
| `IMMEDIATE SLAUGHTER` → `DIGITAL MEDIA PLAYERS` | `IMMEDIATE` ⊃ `MEDIA` | ✅ Rejected |
| `LAYER-TYPE` hens → `AUDIO PLAYERS` | `LAYER` ⊂ `PLAYERS` | ✅ Rejected |
| `AS SPECIFIED` → `UNSPECIFIED` | `SPECIFIED` ⊂ `UNSPECIFIED` | ✅ Rejected |

### 6. Candidate retrieval

Each HS10 code looks up its anchor tokens (including synonyms) in an inverted index over
UCC anchor tokens. The top-`K` UCC codes by initial token overlap are taken as candidates
(default `K=10`).

---

## Stage A/C: Scoring and Hard Filters

### 7. Coverage-based scoring

Each candidate pair receives a score in [0, 1]:

```
score = 0.65 × UCC_coverage + 0.35 × HS10_coverage + bigram_bonus
```

Where:
- `UCC_coverage = |ucc_anchors ∩ hs10_expanded| / |ucc_anchors|`
  (fraction of UCC anchor nouns explained by the HS10 product)
- `HS10_coverage = |hs10_anchors ∩ ucc_expanded| / |hs10_anchors|`
  (fraction of HS10 anchor nouns corroborated by the UCC description)
- `bigram_bonus` = +0.10 per matching non-generic consecutive bigram (max 1.0 total)

UCC coverage is weighted higher because the UCC description is the narrower, more
specific label — if the UCC says "GROUND BEEF" every anchor noun must be satisfied.

### 8. HS Chapter × UCC prefix compatibility (HARD REJECT)

Each HS10 code belongs to one of 97 HS chapters (first 2 digits). Each UCC code has a
2-digit prefix. The mapping `HS_CHAPTER_UCC_ALLOWED` defines which UCC prefixes are
compatible with each HS chapter. If the chapter has a non-empty allowed set **and** the
UCC prefix is not in it, the pair receives score = 0.0 (hard reject).

Examples:
| HS chapter | Product domain | Allowed UCC prefixes |
|---|---|---|
| 02 | Meat cuts | 03–07 (beef, pork, proc. meats, poultry, seafood) |
| 50–67 | Textiles / apparel / footwear | 36–44 (apparel + footwear + accessories) |
| 84–85 | Machinery / electronics | 30–31 (appliances, electronics) + vehicles + toys |
| 87 | Motor vehicles | 45–49 (cars, trucks, fuel, tires, auto services) |
| 86 | Railway equipment | NONE (not a consumer good) |

This eliminates cross-domain false positives like:
- Leather (ch.41) → `BEEF` UCC codes (prefix 03)
- Machinery (ch.84) → `SUGAR` UCC code (prefix 15)
- Railway cars (ch.86) → `NEW CARS` / `NEW TRUCKS` UCC codes

### 9. Goods-only UCC filter

Before candidate generation, UCC codes are classified using `classify_ucc()`. Codes
matching any of ~50 exclusion phrases are removed from the candidate pool entirely:

```
INSURANCE, MORTGAGE, RENT, REPAIR SERVICE, HOSPITAL, PHYSICIAN,
AT RESTAURANTS, AT FAST FOOD, CATERED AFFAIR, ELECTRICITY,
INTERNET SERVICE, CABLE TV, LEGAL FEE, AT EMPLOYER, ...
```

This ensures financial, housing, utility, repair-service, and restaurant categories
cannot appear in the concordance.

### 10. Acceptance threshold

Only pairs with `score ≥ 0.40` (default) are written to the concordance.

---

## Stage B: GPT Semantic Judging (Optional)

When `OPENAI_API_KEY` is set, the top-K candidates per HS10 code (from Stage A) are
submitted to GPT for semantic judgment using a strict prompt:

**System prompt excerpt**:
> You are an expert in US trade classification (HTS) and consumer expenditure surveys
> (CEX). Judge whether an HS10 product description corresponds to a specific UCC consumer
> expenditure category. Rules: UCC categories must represent physical consumer goods (not
> services, financial products, utilities, or restaurant meals). The match must be based on
> SPECIFIC product type, not generic modifiers. Reject if HS10 product is an industrial
> input, raw material, or non-consumer good.

**Required JSON output schema per candidate**:
```json
{
  "ucc_code": "string",
  "accept": true/false,
  "confidence": "high|medium|low",
  "reason": "string (one sentence explaining accept/reject)"
}
```

GPT results override the deterministic score. Deterministic hard-reject rules (Stage C)
still apply after GPT — GPT cannot approve a chapter-incompatible pair.

---

## Confidence Calibration

| Level | Score range | Meaning |
|---|---|---|
| HIGH | ≥ 0.70 | UCC and HS10 strongly mutually covered; ready to use |
| MEDIUM-HIGH | ≥ 0.55 | Good coverage; minor semantic ambiguity |
| MEDIUM | ≥ 0.40 | Partial coverage; review before relying on in research |
| LOW | < 0.40 | Rejected; not written to concordance |

---

## QA Checks and Audit Trail

### Suspicious-match detection

`flag_suspicious()` scans every accepted pair for known error patterns using regex:

| Pattern | Label |
|---|---|
| `ASSES` ↔ `PASS` | substring trap: ASSES≈PASSES |
| `IMMEDIATE` ↔ `MEDIA` | substring trap: IMMEDIATE≈MEDIA |
| `LAYER` (standalone) ↔ `PLAYER` | substring trap: LAYER≈PLAYERS |
| `SPECIFIED` ↔ `UNSPECIFIED` | substring trap: SPECIFIED≈UNSPECIFIED |
| `BREAD` ↔ `SWEAT` | false match: SWEETBREADS vs BREAD |

Flagged pairs are written to `suspicious_matches.csv` for manual review.

### match_decisions.jsonl

Every HS10 code produces a JSONL record with:
- Input tokens and anchor nouns
- Candidate UCC codes considered (with scores and reasons)
- Final accept/reject decision
- Whether GPT was used

This enables full audit of any match or non-match decision.

---

## Output Files

| File | Description |
|---|---|
| `hs10_to_ucc_concordance.csv` | Accepted HS10–UCC pairs with score, confidence, reason |
| `unmatched_hs10_codes.csv` | HS10 codes with no accepted UCC match |
| `unmatched_ucc_codes.csv` | UCC codes not matched to any HS10 (with category reason) |
| `concordance_summary.txt` | Summary statistics (counts consistent with above files) |
| `suspicious_matches.csv` | Flagged pairs for manual QA |
| `match_decisions.jsonl` | Full per-HS10 audit trail |

---

## Reproducibility Notes

- All outputs are **deterministic** given the same input files and Python environment
  when GPT is disabled.
- GPT mode introduces model non-determinism; set `temperature=0` in API calls for
  maximum reproducibility (default in `generate_concordance.py`).
- Re-running `generate_concordance.py` with the same inputs will produce identical
  output files in deterministic mode.
- The `match_decisions.jsonl` file captures every decision rationale.

---

## Known Limitations

1. **Negation context**: Phrases like `NOT FOR CIVIL AIRCRAFT` carry `AIRCRAFT` as a
   token. GPT mode handles this; deterministic mode may link such HS10 codes to aircraft
   UCC categories.
2. **Ingredient ambiguity**: `CHEESE CONTAINING COW'S MILK` may match the `MILK` UCC
   category in deterministic mode because `MILK` is a shared token.
3. **Part-vs-whole**: HS10 "PARTS FOR X" codes may match the X consumer category.
   Acceptable for trade-linkage analysis but note the semantic imprecision.
4. **Industrial inputs**: ~77% of HS10 codes are industrial/non-consumer (chemicals,
   metals, machinery, raw materials). These correctly appear in `unmatched_hs10_codes.csv`.
5. **Precision over recall**: The 0.40 threshold prioritises avoiding false positives.
   Lowering `--min-score` increases recall but may introduce cross-category matches.

---

## Tuning Knobs

| Parameter | Default | Effect |
|---|---|---|
| `--min-score` | 0.40 | Lower → more matches, less precision |
| `--max-candidates` | 10 | Higher → more GPT calls, better recall |
| `GENERIC_TOKENS` set | ~70 items | Add tokens to block spurious matches |
| `HS_CHAPTER_UCC_ALLOWED` | per chapter | Widen sets to allow cross-domain matches |
| `UCC_NONGOOD_PHRASES` | ~50 phrases | Add phrases to exclude more UCC service codes |

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `pandas` | ≥ 1.3 | Data loading and CSV output |
| `openpyxl` | ≥ 3.0 | Reading `.xlsx` input |
| `openai` (optional) | ≥ 1.0 | GPT semantic judging |

Python 3.10+ required.

---

## Version Information

- **Pipeline version**: 2.0 (GPT-assisted, strict guardrails)
- **Previous version**: 1.0 (`create_concordance.py`, naive substring matching)
- **Python**: 3.10+
- **Dependencies**: pandas, openpyxl; openai (optional)

