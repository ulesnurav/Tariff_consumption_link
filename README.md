# Tariff_consumption_link
Linking HS10 to UCC codes using semantic matching

## Overview
This repository contains a comprehensive concordance mapping between US Harmonized Tariff Schedule 10-digit codes (HS10) and Consumer Expenditure Survey Universal Classification Codes (UCC).

## Files

### Input Data
- `hs10_desc.xlsx` - US 10-digit HTS codes with descriptions (23,472 codes)
- `ucc_codes_2017_2019_merged.csv` - UCC codes from 2017-2019 Diary survey (681 codes)

### Output Files
1. **`hs10_to_ucc_concordance.csv`** - Main concordance with 70,497 HS10-UCC pairs
2. **`unmatched_hs10_codes.csv`** - 5,860 HS10 codes without matches
3. **`unmatched_ucc_codes.csv`** - 251 UCC codes without matches (categorized by reason)
4. **`concordance_summary.txt`** - Summary statistics
5. **`concordance_methodology.md`** - Complete methodology documentation
6. **`create_concordance.py`** - Python script to generate the concordance

## Usage

To regenerate the concordance mapping:

```bash
pip install pandas openpyxl
python create_concordance.py
```

## Results Summary

- **HS10 Coverage**: 75% (17,612 of 23,472 codes matched)
- **UCC Coverage**: 63% (430 of 681 codes matched)
- **Total Pairs**: 70,497 HS10-UCC pairs
- **Confidence Levels**: 
  - HIGH: 11,696 pairs
  - MEDIUM-HIGH: 28,694 pairs
  - MEDIUM: 18,295 pairs
  - LOW: 11,812 pairs

## Methodology

The concordance uses advanced semantic matching with:
- Direct token matching with stopword filtering
- Semantic synonym mappings (e.g., "bovine" → "beef")
- Word boundary detection to prevent false matches
- Confidence level assignment based on match quality
- Demographic splits for generic apparel/footwear (25% each)

See `concordance_methodology.md` for complete details.
