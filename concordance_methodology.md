# HS10 to UCC Concordance Methodology

## Overview
This document describes the methodology used to create a concordance mapping between US HS10 tariff codes and Consumer Expenditure Survey (CES) UCC codes.

## Data Sources

### HS10 Data (hs10_desc.xlsx)
- **Source**: US Harmonized Tariff Schedule
- **Records**: 23,472 10-digit product codes
- **Coverage**: Tradeable goods that can be imported
- **Format**: String codes (10 digits with leading zeros preserved)

### UCC Data (ucc_codes_2017_2019_merged.csv)
- **Source**: Consumer Expenditure Survey Diary (2017-2019)
- **Records**: 681 Universal Classification Codes
- **Coverage**: Consumer expenditures (goods AND services)
- **Format**: String codes (6 digits with leading zeros preserved)

## Matching Algorithm

### 1. Semantic Matching Approach
The algorithm uses advanced semantic matching rather than simple keyword matching:

- **Tokenization**: Descriptions are tokenized and normalized (lowercase, special characters removed)
- **Token Similarity**: Jaccard similarity calculated between token sets
- **Category-Level Matching**: Related terms matched at category level (e.g., "beef" matches "meat")
- **Material/Product Matching**: Key material and product type terms given higher weight

### 2. Confidence Scoring
Each match is assigned a confidence level based on semantic similarity score:

- **HIGH** (score ≥ 0.6): Direct match, clear product alignment
- **MEDIUM-HIGH** (score ≥ 0.4): Strong match with minor differences
- **MEDIUM** (score ≥ 0.25): Plausible match with some uncertainty
- **LOW** (score < 0.25): Weak match, best available option

### 3. Special Handling: Apparel/Footwear Demographic Splits
For HS10 codes in apparel and footwear categories:

- Algorithm identifies apparel/footwear products using keyword matching
- Searches for demographic-specific UCC codes (men's, women's, boys', girls')
- If all 4 demographics have matching UCCs, creates 4 matches with 0.25 weight each
- This reflects the reality that imported apparel can serve multiple demographics

**Example**: Men's cotton trousers (HS10) → 4 UCC matches:
- 25% Men's pants
- 25% Women's pants  
- 25% Boys' pants
- 25% Girls' pants

### 4. Service Filtering
UCC codes representing services are identified and excluded from matching:
- Healthcare services
- Repairs and maintenance
- Housing expenses (rent, mortgage)
- Financial services (interest, fees)
- Prepared food services (restaurants)

## Unmatched UCC Analysis

### Categories
Unmatched UCC codes are categorized by reason:

1. **SERVICE**: Healthcare, repairs, maintenance, utilities, personal services
   - These are services, not tradeable goods
   
2. **HOUSING**: Rent, mortgage interest, property taxes, insurance
   - Housing expenses, not importable products
   
3. **FINANCIAL**: Bank fees, insurance premiums, interest payments
   - Financial services, not physical goods
   
4. **PREPARED_FOOD**: Restaurant meals, catering, food service
   - Prepared on-site, not imported goods
   
5. **OTHER**: Miscellaneous reasons
   - May include very specific goods not captured in HS10

### Why UCCs Are Unmatched
The Consumer Expenditure Survey tracks ALL consumer spending, including:
- Services (which cannot be "imported")
- Housing costs (not tradeable goods)
- Financial services
- Restaurant meals (prepared locally)

HS10 codes only cover tradeable goods that cross borders. This fundamental difference explains why many UCC codes have no HS10 match.

## Limitations and Caveats

1. **Semantic Matching Imperfections**: Algorithm may miss some valid matches or create false positives
2. **Aggregation Levels**: HS10 codes are very specific (10 digits), UCCs are more aggregated
3. **Definition Differences**: HS10 focuses on importability, UCC focuses on consumer expenditure categories
4. **Demographic Assumptions**: 25% split for apparel assumes equal distribution (may not reflect reality)
5. **Time Period**: UCC data from 2017-2019; consumption patterns may have changed

## Usage Recommendations

1. **Review matches manually** before using for analysis, especially LOW confidence matches
2. **Consider aggregating** to higher levels (HS6, HS4) for more robust analysis
3. **Use weights** when calculating import exposure for apparel/footwear items
4. **Validate** with domain experts in specific product categories
5. **Update periodically** as both HS and UCC classifications evolve

## Code Replication
The complete matching algorithm is implemented in `create_concordance.py` with:
- Clear comments explaining each step
- Modular functions for reusability
- Proper string handling to preserve code formats
- Configurable confidence thresholds

## Contact
For questions or improvements, please open an issue in the repository.
