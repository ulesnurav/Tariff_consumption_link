
# HS10-to-UCC Concordance Mapping Methodology

## Overview

This document describes the methodology used to create a comprehensive concordance between US Harmonized Tariff Schedule 10-digit codes (HS10) and Consumer Expenditure Survey Universal Classification Codes (UCC).

## Data Sources

1. **HS10 Codes**: `hs10_desc.xlsx` - Contains 23,472 US 10-digit HTS codes with descriptions
2. **UCC Codes**: `ucc_codes_2017_2019_merged.csv` - Contains 681 UCC codes from the 2017-2019 Diary survey

**Important**: Both datasets preserve codes in string format to prevent loss of leading zeros.

## Matching Methodology

### 1. Semantic Text Matching

The concordance uses advanced semantic matching rather than simple keyword searches:

- **Tokenization**: Descriptions are tokenized into meaningful words
- **Direct Matching**: Exact word matches between HS10 and UCC descriptions
- **Semantic Synonyms**: Product relationships are understood (e.g., "bovine" → "beef")
- **Partial Matching**: Substring matches for compound terms

### 2. Confidence Level Assignment

Each match is assigned a confidence level based on similarity scores:

- **HIGH** (≥0.8): Clear semantic match with strong token overlap
- **MEDIUM-HIGH** (≥0.6): Strong match with moderate similarity
- **MEDIUM** (≥0.4): Reasonable match with some uncertainty
- **LOW** (<0.4): Possible match but significant uncertainty

### 3. UCC Code Filtering

UCC codes are filtered to include only goods (exclude services):

**Excluded Categories**:
- **SERVICE**: Repair services, medical care, childcare, education, etc.
- **HOUSING**: Rent, mortgage interest, property taxes
- **FINANCIAL**: Insurance premiums, finance charges, interest, bank fees
- **PREPARED_FOOD**: Restaurant meals, catered food (not raw ingredients)
- **UTILITY**: Electricity, gas, water, phone, internet services

### 4. Apparel & Footwear Demographic Splits

Generic apparel/footwear items are matched to demographic-specific UCC codes:

- Generic "FOOTWEAR" → MEN'S FOOTWEAR (25%) + WOMEN'S FOOTWEAR (25%) + BOYS' FOOTWEAR (25%) + GIRLS' FOOTWEAR (25%)
- The `demographic_split` column indicates the proportion (0.25 for splits, 1.0 otherwise)

**Rationale**: Consumer expenditure data is collected by demographic categories, so generic imports should be distributed across all demographics.

### 5. Multiple Matches

One HS10 code can match multiple UCC codes when:
- The HS10 product spans multiple consumer categories
- Demographic splits are applied
- Multiple confidence levels are warranted

## Output Files

### 1. Main Concordance (`hs10_to_ucc_concordance.csv`)
Contains all HS10-UCC matches with confidence levels and reasoning.

### 2. Unmatched HS10 Codes (`unmatched_hs10_codes.csv`)
HS10 codes that could not be matched to any UCC code, with explanations.

### 3. Unmatched UCC Codes (`unmatched_ucc_codes.csv`)
UCC codes without HS10 matches, categorized by reason (SERVICE, HOUSING, FINANCIAL, etc.).

### 4. Summary Statistics (`concordance_summary.txt`)
Aggregate statistics on matching results and distributions.

### 5. This Document (`concordance_methodology.md`)
Detailed methodology and replication instructions.

### 6. Python Script (`create_concordance.py`)
Fully executable script to replicate the concordance.

## Limitations and Assumptions

### Limitations
1. **Semantic matching is heuristic**: Not perfect, some matches may be incorrect
2. **Confidence levels are subjective**: Based on similarity thresholds
3. **Coverage gaps**: Some HS10 products have no consumer expenditure equivalent
4. **Granularity mismatch**: HS10 is very detailed (23K+ codes) while UCC is broader (681 codes)

### Assumptions
1. **Demographic splits**: 25% equal distribution across demographics is assumed for generic apparel/footwear
2. **Service exclusion**: All UCC service categories are excluded from matching
3. **String format**: Codes are preserved as strings to maintain leading zeros
4. **Minimum threshold**: Matches below 0.3 similarity score are excluded

## Quality Assurance

The following quality checks are performed:
- No duplicate HS10-UCC pairs (unless different confidence levels)
- Demographic split values are validated
- All codes remain in string format
- Unmatched codes have explanations
- Sample matches reviewed for semantic accuracy

## Replication Instructions

To replicate this concordance:

1. **Install dependencies**:
   ```bash
   pip install pandas openpyxl
   ```

2. **Ensure input files are present**:
   - `hs10_desc.xlsx`
   - `ucc_codes_2017_2019_merged.csv`

3. **Run the script**:
   ```bash
   python create_concordance.py
   ```

4. **Verify outputs**:
   - Check that all 6 output files are created
   - Review sample matches in the concordance file
   - Examine summary statistics

## Version Information

- **Script Version**: 1.0
- **Generated**: 2026-01-10
- **Python Version**: 3.x required
- **Dependencies**: pandas, openpyxl

## Contact and Feedback

This concordance is generated automatically. For questions or improvements, please review the code in `create_concordance.py` and adjust matching logic as needed.
