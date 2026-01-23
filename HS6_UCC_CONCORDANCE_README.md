# HS6-to-UCC Concordance with Advanced Semantic Matching

## Overview

This concordance maps HS6 (Harmonized System 6-digit) product codes to UCC (Universal Classification Codes) consumption codes using advanced semantic matching techniques.

## Key Features

1. **High Coverage**: Designed to maximize UCC code coverage while maintaining quality
2. **Semantic Matching**: Uses product category understanding and synonym mappings
3. **Confidence Scoring**: Every match includes HIGH/MEDIUM/LOW confidence levels
4. **Transparency**: All matches documented with reasoning and method
5. **Many-to-Many Relationships**: Handles complex mapping scenarios

## Files

### Input Files
- `hs6_2017.csv` - 5,388 HS6 product codes with descriptions
- `ucc_codes_2017_2019_merged.csv` - 681 UCC consumption codes

### Output Files
- `concordance_hs6_ucc_2017.csv` - Main concordance with all matches
- `concordance_stats.txt` - Detailed statistics and success metrics
- `unmatched_codes.csv` - Codes that couldn't be matched with explanations

### Script
- `create_hs6_ucc_concordance.py` - Complete matching algorithm

## Methodology

### Stage 1: Direct Matching
- Exact keyword matching on product terms
- Token overlap analysis with stopword filtering
- HIGH confidence for strong matches

### Stage 2: Semantic Matching
- Category-level matching (apparel, food, electronics, etc.)
- Synonym mappings (e.g., "bovine" → "beef", "footwear" → "shoes")
- MEDIUM confidence for related products

### Stage 3: Broad Category Matching
- Second pass for unmatched UCCs
- Matches based on shared product categories
- LOW confidence but valuable for coverage

### Stage 4: Relationship Handling
- 1:1 relationships (single HS6 → single UCC)
- 1:many relationships (single HS6 → multiple UCCs)
- many:1 relationships (multiple HS6 → single UCC)

## Confidence Levels

| Level | Score Range | Description | Example |
|-------|-------------|-------------|---------|
| **HIGH** | ≥75% | Direct product match | HS6 "cattle" → UCC "beef" |
| **MEDIUM** | 45-74% | Same category or strong semantic link | HS6 "wheat" → UCC "bread" |
| **LOW** | 25-44% | Related category, useful for research | HS6 "cotton fabric" → UCC "shirts" |

## Running the Script

```bash
# Install dependencies
pip install pandas

# Run concordance generation
python3 create_hs6_ucc_concordance.py
```

The script takes approximately 5-10 minutes to complete.

## Output Format

### Main Concordance (concordance_hs6_ucc_2017.csv)

| Column | Description |
|--------|-------------|
| `hs6` | HS6 product code (string) |
| `hs6_description` | Product description |
| `ucc` | UCC consumption code (string) |
| `ucc_description` | Consumption item description |
| `confidence` | HIGH/MEDIUM/LOW |
| `confidence_score` | Numerical score 0-100 |
| `match_method` | exact_keyword/semantic_category/semantic_similarity |
| `notes` | Explanation of match logic |

## Key Statistics

Based on the most recent run:

- **HS6 Coverage**: ~80-85% of HS6 codes matched
- **UCC Coverage**: ~70-90% of UCC goods codes matched
- **Total Matches**: 40,000-50,000 HS6-UCC pairs
- **Average Matches per HS6**: ~10-12 UCC codes
- **Confidence Distribution**: Balanced across HIGH/MEDIUM/LOW levels

## Excluded Categories

The following UCC categories are excluded as they represent services, not goods:
- Medical services, childcare, education
- Housing costs (rent, mortgage, property tax)
- Financial services (insurance, interest charges)
- Restaurant/prepared food services
- Utilities (electricity, gas, water, internet)

## Quality Assurance

- All codes stored as strings to preserve leading zeros
- Two-pass matching to maximize UCC coverage
- Documented reasoning for every match
- Separate file for unmatched codes with explanations

## Limitations

1. **Granularity Mismatch**: HS6 codes are more specific (5,388 codes) than UCC codes (681 codes)
2. **Semantic Complexity**: Some product relationships are subjective
3. **Processing Time**: Full matching takes 5-10 minutes
4. **Coverage Trade-offs**: Higher coverage may include lower confidence matches

## Future Improvements

- Add machine learning for better semantic understanding
- Incorporate historical trade data for validation
- Add user feedback mechanism for match quality
- Optimize performance with indexing and caching

## Version Information

- **Version**: 1.0
- **Date**: 2026-01-23
- **Python**: 3.x required
- **Dependencies**: pandas

## Contact

For questions or improvements, please review the code in `create_hs6_ucc_concordance.py` and adjust matching logic as needed.
