# Tariff_consumption_link
Linking HS10 to UCC codes

## Overview
This repository contains a concordance mapping between US HS10 tariff codes and Consumer Expenditure Survey (CES) UCC codes.

## Files

### Input Data
- `hs10_desc.xlsx` - US Harmonized Tariff Schedule 10-digit codes (23,472 codes)
- `ucc_codes_2017_2019_merged.csv` - UCC codes from Diary survey 2017-2019 (681 codes)

### Output Files
1. **hs10_to_ucc_concordance.csv** - Main concordance mapping (25,060 matches)
   - Includes demographic splits for apparel/footwear (12,380 matches with 0.25 weight)
   - Confidence scores: HIGH/MEDIUM-HIGH/MEDIUM/LOW

2. **unmatched_hs10_codes.csv** - HS10 codes with no UCC match (2,311 codes)

3. **unmatched_ucc_codes.csv** - UCC codes with no HS10 match (400 codes)
   - Categorized by: SERVICE/HOUSING/FINANCIAL/PREPARED_FOOD/OTHER

4. **concordance_summary.txt** - Statistics and coverage metrics

5. **concordance_methodology.md** - Complete documentation of matching algorithm

### Script
- **create_concordance.py** - Replication script to regenerate concordance

## Usage

To regenerate the concordance:
```bash
python3 create_concordance.py
```

## Results Summary
- **HS10 Coverage**: 90.2% matched (21,161 of 23,472 codes)
- **UCC Coverage**: 41.3% matched (281 of 681 codes)
- **Demographic Splits**: 12,380 apparel/footwear matches with 0.25 weights
- **Match Quality**: 83.3% MEDIUM-HIGH confidence

## Methodology
The concordance uses advanced semantic matching with:
- Tokenization and similarity scoring
- Category-level matching (e.g., "beef" → "meat")
- Demographic splits for apparel/footwear (men's, women's, boys', girls')
- Service filtering (UCCs for services excluded from matching)

See `concordance_methodology.md` for complete details.
