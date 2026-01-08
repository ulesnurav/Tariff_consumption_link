# HS6 to UCC Concordance Methodology

## Introduction

### Purpose
This concordance maps Harmonized System 6-digit (HS6) trade classification codes to Universal Classification Code (UCC) consumption categories used in the Consumer Expenditure Survey (CE). The concordance enables researchers to link international trade data to household consumption patterns.

### Data Sources
- **HS6 Codes**: hs6_2017.csv (5,388 codes from HS 2017 revision)
- **UCC Codes**: ucc.csv (617 consumption categories)
- **Date Created**: 2026-01-08

### Matching Method
Semantic matching using rule-based algorithms enhanced with keyword analysis. The approach combines:
1. Keyword extraction and overlap calculation
2. Product-specific matching rules
3. Category-based heuristics
4. Special handling for apparel and footwear

## Methodology Overview

### Semantic Matching Approach
The concordance uses a rule-based semantic matching system that:
- Analyzes product descriptions from both HS6 and UCC codes
- Identifies keyword overlaps and semantic similarities
- Applies category-specific matching rules
- Handles edge cases like apparel splits and services

### Confidence Level Criteria
- **HIGH**: Direct product match with clear one-to-one or one-to-few mapping
- **MEDIUM-HIGH**: Good semantic match with minor ambiguity
- **MEDIUM**: Plausible match requiring some interpretation
- **LOW**: Best available match but with significant uncertainty

### Handling of Edge Cases

#### Apparel (HS Chapters 61-62)
Apparel products present a unique challenge because HS6 codes typically don't distinguish by consumer demographic (men/women/boys/girls), while UCC codes do. **Solution**: Each apparel HS6 code is split equally across four demographic categories:
- 25% to Men's categories
- 25% to Women's categories
- 25% to Boys' categories
- 25% to Girls' categories

This equal distribution assumption is documented in the Multiple_Match_Note field.

#### Services
UCC codes representing services (healthcare, education, repairs, etc.) are tagged with Is_Service=YES and have no HS6 matches, as HS6 only classifies physical goods.

#### Industrial vs Consumer Goods
HS6 codes for industrial equipment, raw materials, and intermediate goods are marked as unmatched with appropriate reasoning.

## Detailed Matching Logic by Category

### Live Animals & Meat Products (HS Chapters 01-02)
**Strategy**: Match by animal type and cut specification
- Live animals for breeding: Generally no match (agricultural input)
- Fresh/frozen beef: Match to ground beef, roasts, steaks based on cut description
- Pork products: Match to pork chops, ham, bacon based on preparation
- Poultry: Distinguish chicken from turkey

### Apparel (HS Chapters 61-62)
**CRITICAL METHODOLOGY**: Equal 25% split across demographics
**Example**: HS6 610910 'T-shirts, cotton, knitted' creates 4 mappings:
1. To Men's Shirts (25%)
2. To Women's Tops (25%)
3. To Boys' Shirts (25%)
4. To Girls' Tops (25%)

## Service UCCs

Service UCC codes have no HS6 matches because HS6 only classifies tradeable goods.
Total service UCCs identified: 250

## Limitations and Caveats

1. **Gender/Age Ambiguity**: Apparel and footwear use equal splits due to lack of demographic detail in HS6
2. **Industrial vs Consumer**: Some HS6 codes may have both industrial and consumer uses
3. **Quality Differences**: HS6 and UCC may group products differently by quality/price
4. **Multiple Plausible Mappings**: Some products could reasonably map to multiple UCCs
5. **Time Period**: HS6 uses 2017 revision; updates may be needed for newer HS versions

## Replication Instructions

To replicate this concordance:
1. Obtain hs6_2017.csv and ucc.csv data files
2. Run the matching script: `python create_concordance.py`
3. Review output files for quality
4. Manual review recommended for ambiguous matches

## Quality Control

Quality assurance steps:
- Systematic processing of all HS6 codes
- Consistent application of matching rules
- Documentation of all assumptions and special cases
- Statistical summaries for validation
