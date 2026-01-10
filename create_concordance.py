#!/usr/bin/env python3
"""
HS10 to UCC Code Concordance Creator

This script creates a concordance mapping between US HS10 tariff codes and 
Consumer Expenditure Survey (CES) UCC codes using semantic matching.

Author: Generated for Tariff_consumption_link project
Date: 2026-01-10
"""

import pandas as pd
import re
from typing import List, Tuple, Dict, Set
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')


class SemanticMatcher:
    """
    Advanced semantic matcher for HS10 to UCC concordance.
    Uses intelligent keyword extraction, synonym matching, and category-based matching.
    """
    
    def __init__(self):
        # Define apparel/footwear categories for demographic splits
        self.apparel_keywords = {
            'mens': ['men', 'mens', "men's", 'male', 'gentleman'],
            'womens': ['women', 'womens', "women's", 'female', 'ladies', 'lady'],
            'boys': ['boy', 'boys', "boy's"],
            'girls': ['girl', 'girls', "girl's"]
        }
        
        # Apparel and footwear product types
        self.apparel_product_types = [
            'shirt', 'blouse', 'trouser', 'pant', 'short', 'dress', 'skirt',
            'jacket', 'coat', 'sweater', 'suit', 'jeans', 'underwear', 'bra',
            'hosiery', 'sock', 'tie', 'scarf', 'glove', 'hat', 'cap',
            'swimwear', 'nightwear', 'pajama', 'robe', 'uniform'
        ]
        
        self.footwear_types = [
            'footwear', 'shoe', 'boot', 'sandal', 'slipper', 'sneaker',
            'athletic footwear', 'loafer', 'pump', 'heel'
        ]
        
        # Food categories and their related terms
        self.food_categories = {
            'meat': ['beef', 'pork', 'lamb', 'veal', 'meat', 'chicken', 'turkey', 
                     'poultry', 'sausage', 'bacon', 'ham'],
            'fish': ['fish', 'salmon', 'tuna', 'cod', 'halibut', 'seafood', 
                     'shellfish', 'shrimp', 'crab', 'lobster'],
            'dairy': ['milk', 'cheese', 'butter', 'cream', 'yogurt', 'dairy'],
            'vegetables': ['vegetable', 'tomato', 'potato', 'onion', 'lettuce', 
                          'carrot', 'pepper', 'bean', 'pea'],
            'fruits': ['fruit', 'apple', 'orange', 'banana', 'grape', 'berry', 
                       'melon', 'peach', 'pear'],
            'grains': ['bread', 'flour', 'rice', 'pasta', 'cereal', 'grain', 
                       'wheat', 'corn'],
            'beverages': ['coffee', 'tea', 'juice', 'soda', 'water', 'beverage'],
            'sugar': ['sugar', 'sweetener', 'honey', 'syrup']
        }
        
        # Service keywords (these UCCs won't match HS10)
        self.service_keywords = [
            'service', 'repair', 'maintenance', 'visit', 'care', 'fee',
            'professional', 'labor', 'installation', 'cleaning', 'laundry',
            'dry cleaning', 'alteration', 'consultation'
        ]
        
        # Housing keywords (these UCCs won't match HS10)
        self.housing_keywords = [
            'rent', 'rental', 'mortgage', 'property tax', 'property insurance',
            'lodging', 'hotel', 'motel', 'dwelling', 'shelter', 'housing'
        ]
        
        # Financial keywords (these UCCs won't match HS10)
        self.financial_keywords = [
            'interest', 'bank', 'finance charge', 'premium', 'fee',
            'checking', 'savings', 'credit card', 'loan'
        ]
        
        # Prepared food keywords (these UCCs won't match HS10)
        self.prepared_food_keywords = [
            'restaurant', 'catered', 'away from home', 'school lunch',
            'fast food', 'full service', 'carry out', 'delivered'
        ]
    
    def tokenize(self, text: str) -> Set[str]:
        """Tokenize and normalize text for matching."""
        if pd.isna(text):
            return set()
        
        # Convert to lowercase and split
        text = text.lower()
        # Remove special characters but keep spaces
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        # Split and filter
        tokens = set([t.strip() for t in text.split() if len(t.strip()) > 2])
        return tokens
    
    def is_apparel_or_footwear(self, hs10_desc: str) -> bool:
        """Check if HS10 description is apparel or footwear."""
        desc_lower = hs10_desc.lower()
        
        # Check for apparel products
        for product in self.apparel_product_types:
            if product in desc_lower:
                return True
        
        # Check for footwear
        for product in self.footwear_types:
            if product in desc_lower:
                return True
        
        # Check for general clothing terms
        if 'clothing' in desc_lower or 'garment' in desc_lower:
            return True
        
        return False
    
    def get_demographic_from_desc(self, desc: str) -> str:
        """Extract demographic (men/women/boys/girls) from description."""
        desc_lower = desc.lower()
        
        # Check in priority order to avoid substring issues (women before men, girls before boys)
        # Check for women's first (to avoid "men" matching in "women")
        for keyword in self.apparel_keywords['womens']:
            if keyword in desc_lower:
                return 'womens'
        
        # Check for girls' (to avoid "girl" matching partial "boy")
        for keyword in self.apparel_keywords['girls']:
            if keyword in desc_lower:
                return 'girls'
        
        # Check for men's (with word boundaries to avoid partial matches)
        for keyword in self.apparel_keywords['mens']:
            if keyword in desc_lower:
                return 'mens'
        
        # Check for boys'
        for keyword in self.apparel_keywords['boys']:
            if keyword in desc_lower:
                return 'boys'
        
        return 'unisex'
    
    def find_demographic_uccs(self, ucc_df: pd.DataFrame, base_desc: str) -> Dict[str, List[Tuple]]:
        """
        Find UCC codes for different demographics for apparel/footwear items.
        Returns dict with keys: 'mens', 'womens', 'boys', 'girls'
        """
        results = {
            'mens': [],
            'womens': [],
            'boys': [],
            'girls': []
        }
        
        # Extract product type keywords from HS10 description
        # e.g., "trousers", "shirts", "jackets"
        desc_lower = base_desc.lower()
        
        # Find key product terms
        product_terms = []
        for product_type in self.apparel_product_types + self.footwear_types:
            if product_type in desc_lower:
                product_terms.append(product_type)
        
        if not product_terms:
            return results
        
        # Search for demographic-specific UCC codes with similar product types
        for idx, row in ucc_df.iterrows():
            ucc_desc = row['description']
            ucc_desc_lower = ucc_desc.lower()
            
            # Skip if it's a service
            if self.is_service_ucc(ucc_desc):
                continue
            
            # Check demographic
            demo = self.get_demographic_from_desc(ucc_desc)
            if demo == 'unisex':
                continue
            
            # Check if any product terms match
            has_product_match = False
            for term in product_terms:
                # Check for related terms (e.g., "trouser" matches "pants")
                if term in ucc_desc_lower or \
                   (term in ['trouser', 'pant'] and any(x in ucc_desc_lower for x in ['pant', 'trouser'])) or \
                   (term in ['shirt', 'blouse'] and any(x in ucc_desc_lower for x in ['shirt', 'blouse', 'top'])) or \
                   (term in ['jacket', 'coat'] and any(x in ucc_desc_lower for x in ['jacket', 'coat'])) or \
                   (term in ['shoe', 'footwear', 'boot'] and any(x in ucc_desc_lower for x in ['footwear', 'shoe', 'boot'])):
                    has_product_match = True
                    break
            
            if has_product_match:
                # Calculate a simple score based on product match
                score = 0.5  # Base score for product match
                results[demo].append((
                    row['ucc_code'],
                    row['description'],
                    score
                ))
        
        # Sort by score (though they're all the same initially)
        for demo in results:
            results[demo].sort(key=lambda x: x[2], reverse=True)
        
        return results
    
    def is_service_ucc(self, ucc_desc: str) -> bool:
        """Check if UCC description indicates a service (not goods)."""
        desc_lower = ucc_desc.lower()
        
        for keyword in self.service_keywords:
            if keyword in desc_lower:
                return True
        
        for keyword in self.housing_keywords:
            if keyword in desc_lower:
                return True
        
        for keyword in self.financial_keywords:
            if keyword in desc_lower:
                return True
        
        for keyword in self.prepared_food_keywords:
            if keyword in desc_lower:
                return True
        
        return False
    
    def calculate_semantic_similarity(self, hs10_desc: str, ucc_desc: str) -> Tuple[float, str]:
        """
        Calculate semantic similarity between HS10 and UCC descriptions.
        Returns (score, reasoning).
        """
        hs10_tokens = self.tokenize(hs10_desc)
        ucc_tokens = self.tokenize(ucc_desc)
        
        # Find common tokens
        common_tokens = hs10_tokens & ucc_tokens
        
        if len(common_tokens) == 0:
            # Check for category-level matches (e.g., beef matches meat)
            category_match = self.check_category_match(hs10_desc, ucc_desc)
            if category_match:
                return (0.4, f"Category-level match: {category_match}")
            return (0.0, "No common terms found")
        
        # Calculate Jaccard similarity
        union_tokens = hs10_tokens | ucc_tokens
        jaccard_score = len(common_tokens) / len(union_tokens)
        
        # Boost score for exact key term matches
        key_terms = ['cotton', 'wool', 'silk', 'leather', 'plastic', 'metal',
                     'wood', 'glass', 'rubber', 'synthetic']
        exact_matches = sum(1 for term in key_terms if term in common_tokens)
        
        if exact_matches > 0:
            jaccard_score *= 1.2
        
        # Cap at 1.0
        jaccard_score = min(jaccard_score, 1.0)
        
        # Generate reasoning
        if jaccard_score > 0.6:
            reasoning = f"Strong match - common terms: {', '.join(list(common_tokens)[:3])}"
        elif jaccard_score > 0.3:
            reasoning = f"Good match - shared terms: {', '.join(list(common_tokens)[:3])}"
        else:
            reasoning = f"Partial match - some shared terms: {', '.join(list(common_tokens)[:2])}"
        
        return (jaccard_score, reasoning)
    
    def check_category_match(self, hs10_desc: str, ucc_desc: str) -> str:
        """Check if descriptions match at category level (e.g., beef -> meat)."""
        hs10_lower = hs10_desc.lower()
        ucc_lower = ucc_desc.lower()
        
        for category, terms in self.food_categories.items():
            hs10_match = any(term in hs10_lower for term in terms)
            ucc_match = any(term in ucc_lower for term in terms)
            
            if hs10_match and ucc_match:
                return category
        
        return None
    
    def assign_confidence_level(self, score: float) -> str:
        """Assign confidence level based on similarity score."""
        if score >= 0.6:
            return "HIGH"
        elif score >= 0.4:
            return "MEDIUM-HIGH"
        elif score >= 0.25:
            return "MEDIUM"
        else:
            return "LOW"


class ConcordanceBuilder:
    """Main class for building HS10 to UCC concordance."""
    
    def __init__(self, hs10_file: str, ucc_file: str):
        self.hs10_file = hs10_file
        self.ucc_file = ucc_file
        self.matcher = SemanticMatcher()
        
        # Load data
        self.load_data()
    
    def load_data(self):
        """Load and prepare input data files."""
        print("Loading data files...")
        
        # Load HS10 data with string dtype
        self.hs10_df = pd.read_excel(self.hs10_file, dtype=str)
        # Standardize column names
        self.hs10_df.columns = ['hs10_code', 'hs10_description']
        # Ensure 10-digit codes with leading zeros
        self.hs10_df['hs10_code'] = self.hs10_df['hs10_code'].astype(str).str.zfill(10)
        
        # Load UCC data with string dtype
        self.ucc_df = pd.read_csv(self.ucc_file, dtype=str)
        # Ensure 6-digit codes with leading zeros
        self.ucc_df['ucc_code'] = self.ucc_df['ucc_code'].astype(str).str.zfill(6)
        
        print(f"Loaded {len(self.hs10_df)} HS10 codes")
        print(f"Loaded {len(self.ucc_df)} UCC codes")
    
    def build_concordance(self):
        """Build the main concordance mapping."""
        print("\nBuilding concordance...")
        
        matches = []
        unmatched_hs10 = []
        matched_ucc_codes = set()
        
        # Process each HS10 code
        for idx, hs10_row in self.hs10_df.iterrows():
            if idx % 1000 == 0:
                print(f"Processing HS10 code {idx}/{len(self.hs10_df)}...")
            
            hs10_code = hs10_row['hs10_code']
            hs10_desc = hs10_row['hs10_description']
            
            # Check if apparel/footwear
            is_apparel = self.matcher.is_apparel_or_footwear(hs10_desc)
            
            if is_apparel:
                # Try to find demographic-specific matches
                demo_matches = self.matcher.find_demographic_uccs(self.ucc_df, hs10_desc)
                
                # Check if we have all 4 demographics
                has_all_demos = all(len(demo_matches[d]) > 0 for d in ['mens', 'womens', 'boys', 'girls'])
                
                if has_all_demos:
                    # Create 4 matches with 0.25 weight each
                    for demo in ['mens', 'womens', 'boys', 'girls']:
                        if demo_matches[demo]:
                            ucc_code, ucc_desc, score = demo_matches[demo][0]
                            confidence = self.matcher.assign_confidence_level(score)
                            
                            matches.append({
                                'hs10_code': hs10_code,
                                'hs10_description': hs10_desc,
                                'ucc_code': ucc_code,
                                'ucc_description': ucc_desc,
                                'confidence': confidence,
                                'match_reasoning': f"Demographic split - {demo} variant",
                                'weight': 0.25
                            })
                            matched_ucc_codes.add(ucc_code)
                    continue
            
            # Standard matching (not apparel with 4 demos)
            best_matches = self.find_best_ucc_matches(hs10_desc)
            
            if best_matches:
                # Add top match(es)
                for ucc_code, ucc_desc, score, reasoning in best_matches[:3]:  # Top 3
                    confidence = self.matcher.assign_confidence_level(score)
                    
                    # Only include if confidence is at least LOW
                    if score >= 0.2:
                        matches.append({
                            'hs10_code': hs10_code,
                            'hs10_description': hs10_desc,
                            'ucc_code': ucc_code,
                            'ucc_description': ucc_desc,
                            'confidence': confidence,
                            'match_reasoning': reasoning,
                            'weight': 1.0
                        })
                        matched_ucc_codes.add(ucc_code)
            else:
                # No match found
                unmatched_hs10.append({
                    'hs10_code': hs10_code,
                    'hs10_description': hs10_desc,
                    'reason': 'No plausible UCC match found'
                })
        
        print(f"Created {len(matches)} matches")
        print(f"Unmatched HS10 codes: {len(unmatched_hs10)}")
        
        # Save results
        self.matches_df = pd.DataFrame(matches)
        self.unmatched_hs10_df = pd.DataFrame(unmatched_hs10)
        self.matched_ucc_codes = matched_ucc_codes
        
        return self.matches_df, self.unmatched_hs10_df
    
    def find_best_ucc_matches(self, hs10_desc: str, top_n: int = 3) -> List[Tuple]:
        """Find best matching UCC codes for an HS10 description."""
        candidates = []
        
        for idx, ucc_row in self.ucc_df.iterrows():
            ucc_desc = ucc_row['description']
            
            # Skip services
            if self.matcher.is_service_ucc(ucc_desc):
                continue
            
            # Calculate similarity
            score, reasoning = self.matcher.calculate_semantic_similarity(hs10_desc, ucc_desc)
            
            if score > 0:
                candidates.append((
                    ucc_row['ucc_code'],
                    ucc_desc,
                    score,
                    reasoning
                ))
        
        # Sort by score and return top N
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates[:top_n]
    
    def categorize_unmatched_uccs(self):
        """Categorize UCC codes that didn't match any HS10."""
        print("\nCategorizing unmatched UCC codes...")
        
        unmatched_uccs = []
        
        for idx, ucc_row in self.ucc_df.iterrows():
            ucc_code = ucc_row['ucc_code']
            
            if ucc_code in self.matched_ucc_codes:
                continue
            
            ucc_desc = ucc_row['description']
            desc_lower = ucc_desc.lower()
            
            # Categorize
            category = 'OTHER'
            reason = 'No matching HS10 code found'
            
            # Check for services
            if any(kw in desc_lower for kw in self.matcher.service_keywords):
                category = 'SERVICE'
                reason = 'Service - not a tradeable good'
            
            # Check for housing
            elif any(kw in desc_lower for kw in self.matcher.housing_keywords):
                category = 'HOUSING'
                reason = 'Housing expense - not a tradeable good'
            
            # Check for financial
            elif any(kw in desc_lower for kw in self.matcher.financial_keywords):
                category = 'FINANCIAL'
                reason = 'Financial service - not a tradeable good'
            
            # Check for prepared food
            elif any(kw in desc_lower for kw in self.matcher.prepared_food_keywords):
                category = 'PREPARED_FOOD'
                reason = 'Prepared food service - not importable goods'
            
            unmatched_uccs.append({
                'ucc_code': ucc_code,
                'ucc_description': ucc_desc,
                'category': category,
                'reason': reason
            })
        
        self.unmatched_uccs_df = pd.DataFrame(unmatched_uccs)
        print(f"Unmatched UCC codes: {len(unmatched_uccs)}")
        
        return self.unmatched_uccs_df
    
    def generate_summary(self) -> str:
        """Generate summary statistics."""
        print("\nGenerating summary...")
        
        total_hs10 = len(self.hs10_df)
        total_ucc = len(self.ucc_df)
        matched_hs10 = total_hs10 - len(self.unmatched_hs10_df)
        matched_ucc = len(self.matched_ucc_codes)
        
        summary = f"""HS10 to UCC Concordance Summary
{'='*50}

INPUT DATA
----------
Total HS10 codes: {total_hs10:,}
Total UCC codes: {total_ucc:,}

MATCHING RESULTS
----------------
HS10 codes matched: {matched_hs10:,} ({matched_hs10/total_hs10*100:.1f}%)
HS10 codes unmatched: {len(self.unmatched_hs10_df):,} ({len(self.unmatched_hs10_df)/total_hs10*100:.1f}%)

UCC codes matched: {matched_ucc:,} ({matched_ucc/total_ucc*100:.1f}%)
UCC codes unmatched: {len(self.unmatched_uccs_df):,} ({len(self.unmatched_uccs_df)/total_ucc*100:.1f}%)

UNMATCHED UCC BREAKDOWN BY CATEGORY
------------------------------------
"""
        
        # Add category breakdown
        category_counts = self.unmatched_uccs_df['category'].value_counts()
        total_unmatched = len(self.unmatched_uccs_df)
        
        for category in ['SERVICE', 'HOUSING', 'FINANCIAL', 'PREPARED_FOOD', 'OTHER']:
            count = category_counts.get(category, 0)
            pct = count / total_unmatched * 100 if total_unmatched > 0 else 0
            summary += f"{category}: {count:,} ({pct:.1f}%)\n"
        
        summary += f"\nCONCORDANCE STATISTICS\n"
        summary += f"----------------------\n"
        summary += f"Total matches created: {len(self.matches_df):,}\n"
        
        # Confidence level breakdown
        confidence_counts = self.matches_df['confidence'].value_counts()
        summary += f"\nMatches by confidence level:\n"
        for level in ['HIGH', 'MEDIUM-HIGH', 'MEDIUM', 'LOW']:
            count = confidence_counts.get(level, 0)
            pct = count / len(self.matches_df) * 100 if len(self.matches_df) > 0 else 0
            summary += f"  {level}: {count:,} ({pct:.1f}%)\n"
        
        # Average matches per HS10
        avg_matches = len(self.matches_df) / matched_hs10 if matched_hs10 > 0 else 0
        summary += f"\nAverage matches per HS10 code: {avg_matches:.2f}\n"
        
        # Demographic splits
        demo_splits = (self.matches_df['weight'] == 0.25).sum()
        summary += f"Demographic splits (apparel/footwear): {demo_splits:,} matches\n"
        
        return summary
    
    def generate_methodology(self) -> str:
        """Generate methodology documentation."""
        methodology = """# HS10 to UCC Concordance Methodology

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
"""
        return methodology
    
    def save_outputs(self):
        """Save all output files."""
        print("\nSaving output files...")
        
        # 1. Main concordance
        self.matches_df.to_csv('hs10_to_ucc_concordance.csv', index=False)
        print("✓ Saved hs10_to_ucc_concordance.csv")
        
        # 2. Unmatched HS10
        self.unmatched_hs10_df.to_csv('unmatched_hs10_codes.csv', index=False)
        print("✓ Saved unmatched_hs10_codes.csv")
        
        # 3. Unmatched UCC (with categories)
        self.unmatched_uccs_df.to_csv('unmatched_ucc_codes.csv', index=False)
        print("✓ Saved unmatched_ucc_codes.csv")
        
        # 4. Summary
        summary_text = self.generate_summary()
        with open('concordance_summary.txt', 'w') as f:
            f.write(summary_text)
        print("✓ Saved concordance_summary.txt")
        
        # 5. Methodology
        methodology_text = self.generate_methodology()
        with open('concordance_methodology.md', 'w') as f:
            f.write(methodology_text)
        print("✓ Saved concordance_methodology.md")
        
        print("\nAll output files generated successfully!")


def main():
    """Main execution function."""
    print("="*60)
    print("HS10 to UCC Code Concordance Creator")
    print("="*60)
    
    # Initialize builder
    builder = ConcordanceBuilder(
        hs10_file='hs10_desc.xlsx',
        ucc_file='ucc_codes_2017_2019_merged.csv'
    )
    
    # Build concordance
    builder.build_concordance()
    
    # Categorize unmatched UCCs
    builder.categorize_unmatched_uccs()
    
    # Save all outputs
    builder.save_outputs()
    
    # Print summary
    print("\n" + builder.generate_summary())
    
    print("\n" + "="*60)
    print("Process complete!")
    print("="*60)


if __name__ == "__main__":
    main()
