# HS6 to UCC Concordance Methodology

## Introduction

### Purpose
This concordance maps Harmonized System 6-digit (HS6) trade classification codes to Universal Classification Code (UCC) consumption categories used in the Consumer Expenditure Survey (CE). The concordance enables researchers to link international trade data to household consumption patterns.

### Data Sources
- **HS6 Codes**: hs6_2017.csv (5388 codes from HS 2017 revision)
- **UCC Codes**: ucc.csv (617 consumption categories)
- **Date Created**: 2026-01-08

### Matching Method
Enhanced semantic matching using:
1. Comprehensive product keyword mapping dictionaries
2. Category-specific matching algorithms
3. Keyword-based indexing and search
4. Special handling for apparel and footwear demographics
5. Semantic search with keyword overlap scoring

## Methodology Overview

### Semantic Matching Approach
The concordance uses a multi-tiered matching system:

1. **Direct Keyword Mapping**: Product-specific dictionaries map common food and household items directly to UCC codes
2. **Demographic Splitting**: Apparel and footwear split equally across gender/age categories
3. **Semantic Search**: For products without direct mappings, keyword overlap scoring identifies best matches
4. **Confidence Scoring**: All matches assigned confidence levels based on keyword overlap

### Confidence Level Criteria
- **HIGH**: 3+ overlapping keywords between HS6 and UCC descriptions
- **MEDIUM-HIGH**: 2 overlapping keywords
- **MEDIUM**: 1 overlapping keyword
- **LOW**: Match based on category logic but minimal keyword overlap

### Handling of Edge Cases

#### Apparel (HS Chapters 61-62)
**Critical Methodology**: Equal 25% split across demographics

HS6 apparel codes don't specify demographics, but UCC codes do. Solution:
- Each apparel HS6 creates 4 mappings: Men's (25%), Women's (25%), Boys' (25%), Girls' (25%)
- Apparel type (tops, bottoms, outerwear, etc.) identified from description
- Best matching UCC category selected for each demographic

**Example**: HS6 610910 'T-shirts, cotton, knitted' → 4 mappings:
1. Men's Shirts (25%)
2. Women's Tops (25%)
3. Boys' Shirts (25%)
4. Girls' Tops (25%)

#### Footwear (HS Chapter 64)
Similar to apparel: 25% split across demographics (men/women/boys/girls)

#### Services
UCC codes for services (healthcare, education, repairs, utilities, etc.) tagged with Is_Service=YES and have no HS6 matches (HS6 only classifies physical goods).

#### Industrial vs Consumer Goods
HS6 codes for industrial equipment, raw materials, breeding animals, and capital equipment marked as unmatched with appropriate reasoning.

## Detailed Matching Logic by Category

### Live Animals & Meat Products (HS Ch 01-02)
- Live animals for breeding → No match (agricultural input)
- Bovine meat → Ground beef, beef roasts, beef steaks based on cuts
- Pork → Pork chops, other pork (roasts/ribs), ham, bacon
- Poultry → Chicken vs turkey distinction
- Processed meats → Lunchmeats, sausages

### Fish & Seafood (HS Ch 03)
- Fresh/chilled fish → Fresh fish & shellfish
- Frozen/processed fish → Processed fish and seafood
- Live ornamental fish → No match (not for consumption)

### Dairy Products (HS Ch 04)
- Milk products → Fresh milk (various fat contents)
- Cheese → Cheese category
- Butter → Butter category
- Yogurt/cream → Other dairy products

### Fruits & Vegetables (HS Ch 07-08)
- Fresh fruits by type: Apples, bananas, oranges, other fruit
- Fresh vegetables: Potatoes, lettuce, tomatoes, other vegetables
- Frozen → Frozen fruits/vegetables
- Canned → Canned fruits/vegetables

### Processed Foods (HS Ch 11, 19, 20)
- Flours → Flour and prepared mixes
- Cereals → Breakfast cereal
- Baked goods → Bread, cakes, cookies, etc.
- Canned/preserved → Appropriate preserved food categories

### Beverages (HS Ch 09, 22)
- Coffee → Roasted coffee, instant coffee
- Tea → Tea category
- Juices → Fresh fruit juice
- Soft drinks → Carbonated drinks
- Alcoholic: Beer, wine, spirits mapped to respective UCC categories

### Apparel (HS Ch 61-62)
See detailed methodology above - 25% demographic splits

### Footwear (HS Ch 64)
25% splits across men's/women's/boys'/girls' footwear categories

### Furniture & Household Goods (HS Ch 94)
- Bedroom furniture → Bedroom furniture UCC
- Living room → Living room furniture UCC
- Kitchen → Kitchen/dining furniture UCC
- Mattresses → Mattress category

### Electronics (HS Ch 85)
- Televisions → Television UCC
- Computers → Computer equipment UCC
- Phones → Telephone equipment UCC
- Audio equipment → Audio equipment categories

### Household Appliances (HS Ch 84, 85)
- Refrigerators/freezers → Refrigerator UCC
- Washing machines → Washer UCC
- Dryers → Dryer UCC
- Other appliances → Appropriate appliance categories

## Service UCCs

Total service UCCs identified: 282

Service categories have no HS6 matches because HS6 only classifies physical tradeable goods.

## Limitations and Caveats

1. **Demographic Ambiguity**: Apparel/footwear use equal 25% splits - actual consumer distribution may vary
2. **Industrial vs Consumer**: Some HS6 codes have both industrial and consumer applications
3. **Quality Tiers**: HS6 and UCC may group products differently by quality/price
4. **Multiple Plausible Mappings**: Some products could reasonably map to multiple UCCs
5. **Temporal**: HS6 2017 revision; updates needed for newer HS versions
6. **Keyword Limitations**: Matching based on keyword overlap may miss semantic relationships

## Replication Instructions

To replicate:
1. Obtain hs6_2017.csv and ucc.csv
2. Run: `python create_concordance_enhanced.py`
3. Review outputs for quality
4. Manual review recommended for LOW confidence matches

## Quality Control

- Systematic processing of all HS6 codes
- Consistent application of matching rules
- Transparency in assumptions (especially apparel splits)
- Statistical validation through summary reports
