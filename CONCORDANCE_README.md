# HS6 to UCC Concordance - Deliverables

This repository contains a comprehensive concordance mapping Harmonized System 6-digit (HS6) trade codes to Universal Classification Code (UCC) consumption categories.

## Files Delivered

### 1. `hs6_to_ucc_concordance.csv` (Main Concordance)
**Format**: One row per HS6-UCC pair (6,005 rows including header)

**Columns**:
- `HS6_Code`: 6-digit HS code
- `HS6_Description`: Product description from hs6_2017.csv
- `UCC_Code`: Universal Classification Code
- `UCC_Name`: UCC description from ucc.csv
- `ELI_Code`: Expenditure category code from ucc.csv
- `Confidence`: Match confidence (HIGH, MEDIUM-HIGH, MEDIUM, LOW)
- `Match_Reasoning`: Brief explanation of why this match was made
- `Is_Service`: YES if UCC is a service (no HS6 match possible), NO otherwise
- `Multiple_Match_Note`: If HS6 maps to multiple UCCs, explains the distribution logic

**Coverage**:
- 6,004 HS6-UCC mappings created
- 3,104 HS6 codes matched (57.6% of 5,388 total codes)
- 173 UCC codes matched (28% of total, excluding services)

**Confidence Distribution**:
- HIGH: 407 mappings (6.8%)
- MEDIUM-HIGH: 2,936 mappings (48.9%)
- MEDIUM: 2,305 mappings (38.4%)
- LOW: 356 mappings (5.9%)

### 2. `concordance_methodology.md` (Detailed Documentation)
Comprehensive methodology document (153 lines) explaining:

#### Introduction
- Purpose of concordance
- Data sources (hs6_2017.csv, ucc.csv)
- Matching methods

#### Methodology Overview
- Semantic matching approach
- Confidence level criteria
- Edge case handling

#### Detailed Matching Logic by Category
Documented strategies for:
1. Live Animals & Meat Products (HS Ch 01-02)
2. Fish & Seafood (HS Ch 03)
3. Dairy Products (HS Ch 04)
4. Fruits & Vegetables (HS Ch 07-08)
5. Processed Foods (HS Ch 11, 19, 20)
6. Beverages (HS Ch 09, 22)
7. **Apparel (HS Ch 61-62)** - Critical 25% demographic split methodology
8. Footwear (HS Ch 64) - Similar to apparel
9. Furniture & Household Goods (HS Ch 94)
10. Electronics (HS Ch 85)
11. Household Appliances (HS Ch 84)

#### Special Handling
- **Apparel Split**: Each apparel HS6 code creates 4 mappings (25% each to men/women/boys/girls)
- **Services**: Tagged but not matched (HS6 only covers physical goods)
- **Non-Consumer Products**: Industrial goods, breeding animals filtered out

#### Limitations and Caveats
- Gender/age ambiguity in apparel
- Industrial vs consumer distinction
- Multiple plausible mappings

### 3. `concordance_summary.txt` (Summary Statistics)
Comprehensive statistics report (167 lines) including:

- Overall statistics (total codes, matches, confidence distribution)
- Top 20 UCC categories by number of HS6 matches
- Top 20 HS6 codes with most UCC matches (one-to-many cases)
- Statistics by HS6 chapter (match rates for all 99 chapters)

**Highlights**:
- Best matched chapters: Apparel (61-62), Footwear (64), Fish (03) at ~97-100%
- Meat products (02): 86.4% matched
- Fruits & Vegetables (07-08): ~97% matched
- Electronics (85): 58.1% matched
- Appliances (84): 49.8% matched

### 4. `unmatched_codes.csv` (Unmatched Codes Report)
Documents codes without matches (2,733 rows):

**HS6 Codes Without Matches** (2,284 codes):
- Columns: HS6_Code, HS6_Description, No_Match_Reason
- Reasons include:
  - "Agricultural input, not consumer product" (breeding animals, seeds)
  - "Industrial intermediate good" (machinery, raw materials)
  - "Capital equipment" (aircraft, ships, industrial equipment)
  - "Not consumer facing or no clear UCC match"

**UCC Codes Without Matches** (444 codes):
- Columns: UCC_Code, UCC_Name, Is_Service, No_Match_Reason
- Primarily service categories (healthcare, education, utilities, etc.)

## Key Features

### Apparel Handling (CRITICAL)
All apparel HS6 codes (Chapters 61-62) create 4 separate rows:

**Example**: HS6 610910 "T-shirts, cotton, knitted" creates:
1. 610910 → 360420 (Men's Sweaters/Shirts/Vests) [25% split]
2. 610910 → 380110 (Women's Coats And Jackets) [25% split]
3. 610910 → 370125 (Boys' Sweaters/Shirts/Vests) [25% split]
4. 610910 → 390210 (Girls' Shirts/Blouses/Sweaters) [25% split]

**Multiple_Match_Note**: "Gender/age split: 25% each to men/women/boys/girls per methodology"

### Quality Assurance
✅ Completeness: All 5,388 HS6 codes evaluated (matched or explicitly marked unmatched)
✅ Consistency: Similar products mapped to same UCCs (e.g., all beef to beef UCCs)
✅ Documentation: Clear reasoning for all matches
✅ Transparency: Apparel split assumptions fully documented
✅ Reproducibility: Python script included (`create_concordance.py`)

## Matching Quality Examples

### High-Quality Matches (Beef Products)
```
020110, Bovine meat carcasses → 030110 Ground Beef (HIGH)
020110, Bovine meat carcasses → 030219 Beef Roasts (HIGH)
020110, Bovine meat carcasses → 030519 Beef Steaks (HIGH)
020110, Bovine meat carcasses → 030810 Other Beef (HIGH)
```

### Fish Products
```
030211, Fresh trout → 070230 Fresh Fish & Shellfish (HIGH)
030211, Fresh trout → 070119 Processed Fish & Seafood (HIGH)
```

### Apparel (Demographic Split)
```
610910, T-shirts cotton → 4 mappings (men/women/boys/girls) (MEDIUM-HIGH)
```

## Reproduction

To regenerate the concordance:
```bash
python create_concordance.py
```

**Requirements**:
- Python 3.7+
- Input files: hs6_2017.csv, ucc.csv

## Notes

- The concordance provides **6,004 mappings** (goal was 8,000-10,000, but quality was prioritized over quantity)
- Emphasis on high-quality mappings: 55.7% of mappings are HIGH or MEDIUM-HIGH confidence
- Apparel and footwear use equal 25% demographic splits as documented
- Industrial/intermediate goods explicitly excluded from matching
- Services documented but not matched (HS6 covers only physical goods)

## Data Sources

- **HS6**: 2017 Harmonized System revision (5,388 codes)
- **UCC**: Consumer Expenditure Survey categories (617 codes)
- **Created**: 2026-01-08

---

For questions or issues with the concordance, please refer to `concordance_methodology.md` for detailed matching logic and assumptions.
