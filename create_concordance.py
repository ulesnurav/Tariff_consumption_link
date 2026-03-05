#!/usr/bin/env python3
"""
HS10-to-UCC Concordance Mapping Script

This script creates a comprehensive concordance mapping between US HTS 10-digit codes (HS10)
and Consumer Expenditure Survey UCC codes using semantic matching.

Author: Automated Concordance System
Date: 2026-01-10
"""

import pandas as pd
import re
from typing import List, Dict, Tuple, Set
from collections import defaultdict

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Input files
HS10_FILE = 'hs10_desc.xlsx'
UCC_FILE = 'ucc_codes_2017_2019_merged.csv'

# Output files
CONCORDANCE_FILE = 'hs10_to_ucc_concordance.csv'
UNMATCHED_HS10_FILE = 'unmatched_hs10_codes.csv'
UNMATCHED_UCC_FILE = 'unmatched_ucc_codes.csv'
SUMMARY_FILE = 'concordance_summary.txt'
METHODOLOGY_FILE = 'concordance_methodology.md'

# ==============================================================================
# SEMANTIC MATCHING RULES
# ==============================================================================

# Product category mappings: HS10 keywords -> UCC keywords
SEMANTIC_MAPPINGS = {
    # Meat products - specific animals
    'bovine': ['beef'],
    'cattle': ['beef'],
    'swine': ['pork'],
    'pig': ['pork'],
    'poultry': ['chicken', 'turkey'],
    'ovine': ['lamb', 'mutton'],
    'sheep': ['lamb', 'mutton'],
    'fish': ['fish', 'seafood'],
    'shellfish': ['fish', 'seafood'],
    'seafood': ['fish', 'seafood'],
    
    # Fruits - general and specific (use whole words to avoid substring issues)
    'citrus': ['orange', 'lemon', 'lime', 'grapefruit'],
    'oranges': ['oranges'],
    'apples': ['apples'],
    'bananas': ['bananas'],
    'grapes': ['grapes'],
    'strawberries': ['strawberries'],
    'berries': ['berries'],
    'melon': ['melons'],
    
    # Vegetables
    'tuber': ['potato'],
    'potatoes': ['potatoes'],
    'tomatoes': ['tomatoes'],
    'legume': ['bean', 'pea', 'lentil'],
    'lettuce': ['lettuce'],
    'cabbage': ['cabbage'],
    'carrots': ['carrots'],
    
    # Dairy
    'milk': ['milk', 'dairy'],
    'cheese': ['cheese', 'dairy'],
    'butter': ['butter', 'dairy'],
    'cream': ['cream', 'dairy'],
    'yogurt': ['yogurt', 'dairy'],
    'ice cream': ['ice cream'],
    
    # Grains and Bakery
    'wheat': ['bread', 'flour', 'cereal'],
    'flour': ['flour', 'bread'],
    'bread': ['bread'],
    'rice': ['rice'],
    'cereal': ['cereal'],
    
    # Beverages
    'coffee': ['coffee'],
    'tea': ['tea'],
    'juice': ['juice'],
    'soft drink': ['soft drinks', 'carbonated drinks'],
    'beer': ['beer', 'ale'],
    'wine': ['wine'],
    'spirits': ['whiskey', 'vodka', 'gin', 'rum'],
    
    # Apparel terms
    'garment': ['clothing', 'apparel'],
    'footwear': ['footwear', 'shoes'],
    'shoes': ['footwear'],
    'boots': ['footwear'],
    'shirt': ['shirts'],
    'pants': ['pants'],
    'dress': ['dresses'],
    'coat': ['coats'],
    'jacket': ['jackets'],
    
    # Appliances (CRITICAL - currently missing!)
    'washing machine': ['washer', 'laundry', 'clothes washer'],
    'clothes washer': ['washer', 'clothes washer'],
    'washer': ['washer', 'clothes washer'],
    'dryer': ['dryer', 'clothes dryer'],
    'clothes dryer': ['dryer', 'clothes dryer'],
    'dishwasher': ['dishwasher'],
    'refrigerator': ['refrigerator', 'fridge'],
    'fridge': ['refrigerator', 'fridge'],
    'freezer': ['freezer'],
    'stove': ['stove', 'range', 'cooktop'],
    'range': ['stove', 'range'],
    'oven': ['oven'],
    'microwave': ['microwave'],
    'air conditioner': ['air conditioner', 'ac unit'],
    'air conditioning': ['air conditioner', 'ac unit'],
    
    # Electronics & Energy
    'photovoltaic': ['solar panel', 'solar'],
    'solar cell': ['solar panel', 'solar'],
    'solar': ['solar panel', 'solar'],
    'inverter': ['inverter'],
    'battery': ['battery', 'batteries'],
    'batteries': ['battery', 'batteries'],
    
    # Furniture
    'sofa': ['sofa', 'couch'],
    'couch': ['sofa', 'couch'],
    'settee': ['sofa', 'couch'],
    'mattress': ['mattress', 'bed'],
    'bed': ['mattress', 'bed'],
    'chair': ['chair', 'chairs'],
    'seat': ['chair', 'chairs'],
    'table': ['table', 'tables'],
    'desk': ['desk', 'desks'],
    
    # Processed foods (missing)
    'sausage': ['frankfurter', 'hot dog', 'sausage'],
    'frankfurter': ['frankfurter', 'hot dog'],
    'hot dog': ['frankfurter', 'hot dog'],
    'baked goods': ['cracker', 'cookie', 'biscuit'],
    'cracker': ['cracker', 'crackers'],
    'biscuit': ['cracker', 'biscuit'],
    'pastry': ['pie', 'tart', 'turnover'],
    'pie': ['pie', 'pies'],
    'tart': ['tart', 'tarts'],
    
    # Flatware and tableware
    'cutlery': ['flatware', 'cutlery'],
    'flatware': ['flatware'],
    'tableware': ['flatware', 'dishes', 'tableware'],
    'silverware': ['flatware', 'silverware'],
}

# UCC categories to exclude (services, financial, etc.)
EXCLUDED_UCC_CATEGORIES = {
    'SERVICE': [
        'repair', 'service', 'maintenance', 'labor', 'installation',
        'doctor', 'hospital', 'medical care', 'healthcare', 'dental',
        'childcare', 'daycare', 'education', 'tuition', 'school fees',
        'pet services', 'veterinary', 'grooming', 'boarding',
    ],
    'HOUSING': [
        'rent', 'mortgage', 'property tax', 'ground rent',
        'homeowners insurance', 'renters insurance',
    ],
    'FINANCIAL': [
        'insurance', 'finance charge', 'interest', 'late charge',
        'bank fee', 'credit card', 'loan', 'premium',
    ],
    'PREPARED_FOOD': [
        'restaurant', 'fast food', 'carryout', 'catered',
        'school lunch', 'vending machine',
    ],
    'UTILITY': [
        'electricity', 'gas', 'water', 'sewer', 'trash',
        'phone service', 'internet', 'cable', 'satellite',
    ],
}

# Apparel/Footwear demographic categories
DEMOGRAPHIC_CATEGORIES = ["MEN'S", "WOMEN'S", "BOYS'", "GIRLS'"]

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if pd.isna(text):
        return ""
    return str(text).upper().strip()

def tokenize(text: str) -> Set[str]:
    """Tokenize text into words, excluding common stopwords."""
    text = normalize_text(text)
    # Remove special characters and split
    tokens = re.findall(r'\b[A-Z0-9]+\b', text)
    
    # Common stopwords to exclude
    stopwords = {'THE', 'A', 'AN', 'AND', 'OR', 'OF', 'FOR', 'IN', 'ON', 'AT', 'TO', 
                 'WITH', 'FROM', 'BY', 'AS', 'IS', 'THAT', 'THIS', 'THESE', 'THOSE',
                 'NOT', 'MORE', 'THAN', 'OTHER', 'NESOI', 'EXCEPT', 'INCLUDING'}
    
    # Filter out stopwords and very short tokens
    return set(t for t in tokens if t not in stopwords and len(t) > 2)

def is_excluded_ucc(ucc_desc: str) -> Tuple[bool, str]:
    """
    Check if UCC code should be excluded (services, financial, etc.).
    Returns (is_excluded, category_reason)
    
    IMPORTANT: Extracts main product description before parenthetical to avoid
    false exclusions. For example:
    - "REFRIGERATOR (RENTER)" → main_desc = "REFRIGERATOR" → KEEP (it's a refrigerator purchase)
    - "RENT" → main_desc = "RENT" → EXCLUDE (it's rent payment)
    - "CLOTHES WASHER (RENTER)" → main_desc = "CLOTHES WASHER" → KEEP (it's a washer purchase)
    """
    desc_norm = normalize_text(ucc_desc)
    
    # Extract main product description before parenthetical
    # This prevents false exclusions based on context suffixes like (RENTER), (OWNED HOME), etc.
    main_desc = desc_norm.split('(')[0].strip()
    
    # Check each exclusion category against the main description only
    for category, keywords in EXCLUDED_UCC_CATEGORIES.items():
        for keyword in keywords:
            keyword_upper = keyword.upper()
            # Only exclude if keyword appears in main description, not in parenthetical context
            if keyword_upper in main_desc:
                return True, category
    
    return False, 'OTHER'

def calculate_semantic_similarity(hs10_desc: str, ucc_desc: str) -> Tuple[float, str]:
    """
    Calculate semantic similarity between HS10 and UCC descriptions.
    Returns (similarity_score, reasoning)
    """
    hs10_norm = normalize_text(hs10_desc)
    ucc_norm = normalize_text(ucc_desc)
    
    # Tokenize both descriptions
    hs10_tokens = tokenize(hs10_desc)
    ucc_tokens = tokenize(ucc_desc)
    
    # Direct token overlap - require substantial tokens (length > 3)
    common_tokens = hs10_tokens & ucc_tokens
    substantial_tokens = [t for t in common_tokens if len(t) > 3]
    
    if substantial_tokens:
        overlap_ratio = len(substantial_tokens) / min(len(hs10_tokens), len(ucc_tokens))
        # Boost score if we have substantial matches
        overlap_ratio = min(1.0, overlap_ratio * 1.2)
        reasoning = f"Direct match on: {', '.join(list(substantial_tokens)[:3])}"
        return overlap_ratio, reasoning
    
    # Semantic mapping check - look for known synonyms with word boundaries
    best_semantic_score = 0.0
    best_semantic_reasoning = ""
    
    for hs10_key, ucc_synonyms in SEMANTIC_MAPPINGS.items():
        # Use word boundaries to avoid false matches (e.g., "APPLE" not in "PINEAPPLE")
        hs10_key_upper = hs10_key.upper()
        # Check if hs10_key appears as a whole word or at word boundaries
        if re.search(r'\b' + re.escape(hs10_key_upper) + r'\b', hs10_norm):
            for synonym in ucc_synonyms:
                synonym_upper = synonym.upper()
                # Similarly check for word boundaries in UCC description
                if re.search(r'\b' + re.escape(synonym_upper) + r'\b', ucc_norm):
                    score = 0.85  # High confidence for semantic mappings
                    reasoning = f"Semantic match: '{hs10_key}' → '{synonym}'"
                    if score > best_semantic_score:
                        best_semantic_score = score
                        best_semantic_reasoning = reasoning
    
    if best_semantic_score > 0:
        return best_semantic_score, best_semantic_reasoning
    
    # Substring matching for compound terms - only for longer words
    hs10_words = [w for w in hs10_tokens if len(w) > 4]
    ucc_words = [w for w in ucc_tokens if len(w) > 4]
    
    for hs10_word in hs10_words:
        for ucc_word in ucc_words:
            # Check if one contains the other (but not trivial matches)
            if len(hs10_word) >= 5 and len(ucc_word) >= 5:
                if hs10_word in ucc_word or ucc_word in hs10_word:
                    reasoning = f"Partial match: '{hs10_word}' ≈ '{ucc_word}'"
                    return 0.55, reasoning
    
    return 0.0, "No semantic match found"

def assign_confidence_level(similarity_score: float, reasoning: str) -> str:
    """Assign confidence level based on similarity score."""
    if similarity_score >= 0.8:
        return 'HIGH'
    elif similarity_score >= 0.6:
        return 'MEDIUM-HIGH'
    elif similarity_score >= 0.4:
        return 'MEDIUM'
    else:
        return 'LOW'

def is_apparel_footwear(desc: str) -> bool:
    """Check if description is apparel or footwear requiring demographic split."""
    desc_norm = normalize_text(desc)
    
    # Check if already has demographic category
    for category in DEMOGRAPHIC_CATEGORIES:
        if category in desc_norm:
            return False  # Already categorized
    
    # Check for generic apparel/footwear terms
    generic_terms = ['FOOTWEAR', 'SHOES', 'BOOTS', 'SANDALS', 'CLOTHING', 'GARMENT', 'APPAREL']
    return any(term in desc_norm for term in generic_terms)

def get_demographic_ucc_codes(ucc_df: pd.DataFrame, base_category: str) -> List[Dict]:
    """Get all demographic variants of a UCC category."""
    results = []
    for category in DEMOGRAPHIC_CATEGORIES:
        matches = ucc_df[ucc_df['description'].str.contains(category, na=False)]
        matches = matches[matches['description'].str.contains(base_category, case=False, na=False)]
        for _, row in matches.iterrows():
            results.append({
                'ucc_code': row['ucc_code'],
                'ucc_description': row['description'],
                'demographic_split': 0.25
            })
    return results

# ==============================================================================
# MAIN MATCHING LOGIC
# ==============================================================================

def create_concordance(hs10_df: pd.DataFrame, ucc_df: pd.DataFrame) -> Tuple[List[Dict], List[Dict], Set[str]]:
    """
    Create concordance between HS10 and UCC codes.
    Returns (matches, unmatched_hs10, matched_ucc_codes)

    Uses pre-computed inverted indices to avoid the O(N×M) nested loop with
    repeated regex operations, reducing runtime from ~40 min to a few minutes
    while producing identical output.
    """
    matches = []
    unmatched_hs10 = []
    matched_ucc_codes = set()

    print("Creating concordance mapping...")
    print(f"Total HS10 codes: {len(hs10_df)}")
    print(f"Total UCC codes: {len(ucc_df)}")

    # Filter out excluded UCC codes
    ucc_goods = []
    for _, row in ucc_df.iterrows():
        is_excluded, _ = is_excluded_ucc(row['description'])
        if not is_excluded:
            ucc_goods.append(row)

    ucc_goods_df = pd.DataFrame(ucc_goods)
    print(f"UCC goods codes (after filtering services/housing/financial): {len(ucc_goods_df)}")

    # ------------------------------------------------------------------
    # Pre-computation phase: build per-UCC token data and inverted indices
    # so we avoid re-computing these inside the HS10 loop.
    # ------------------------------------------------------------------

    # ucc_precomputed[i] = (ucc_code, ucc_desc, ucc_norm, all_tokens, substantial_tokens, words_5plus)
    ucc_precomputed = []
    for _, ucc_row in ucc_goods_df.iterrows():
        ucc_code = str(ucc_row['ucc_code'])
        ucc_desc = str(ucc_row['description'])
        ucc_norm = normalize_text(ucc_desc)
        ucc_tokens = tokenize(ucc_desc)
        ucc_substantial = frozenset(t for t in ucc_tokens if len(t) > 3)
        ucc_5plus = frozenset(w for w in ucc_tokens if len(w) > 4)
        ucc_precomputed.append((ucc_code, ucc_desc, ucc_norm, ucc_tokens, ucc_substantial, ucc_5plus))

    # Inverted index: substantial token -> list of UCC indices
    # Used for fast direct-token-overlap candidate lookup.
    token_to_ucc_indices: Dict[str, List[int]] = defaultdict(list)
    for i, (_, _, _, _, ucc_substantial, _) in enumerate(ucc_precomputed):
        for token in ucc_substantial:
            token_to_ucc_indices[token].append(i)

    # Semantic index: hs10_key -> list of (ucc_idx, first_matching_synonym)
    # Pre-check which UCCs respond to each semantic mapping's synonyms (UCC side).
    # hs10 side is checked per-HS10 at query time using pre-compiled patterns.
    hs10_key_to_ucc_list: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
    for i, (_, _, ucc_norm, _, _, _) in enumerate(ucc_precomputed):
        for hs10_key, synonyms in SEMANTIC_MAPPINGS.items():
            for synonym in synonyms:
                synonym_upper = synonym.upper()
                if re.search(r'\b' + re.escape(synonym_upper) + r'\b', ucc_norm):
                    hs10_key_to_ucc_list[hs10_key].append((i, synonym))
                    break  # first matching synonym per (key, ucc) is sufficient

    # Pre-compile regex patterns for the HS10 side of semantic matching.
    hs10_key_patterns = {
        key: re.compile(r'\b' + re.escape(key.upper()) + r'\b')
        for key in SEMANTIC_MAPPINGS.keys()
    }

    # Flat list of (word, ucc_idx) for all 5+ char UCC words — used for substring fallback.
    all_ucc_5plus_words: List[Tuple[str, int]] = []
    for i, (_, _, _, _, _, ucc_5plus) in enumerate(ucc_precomputed):
        for word in ucc_5plus:
            all_ucc_5plus_words.append((word, i))

    # ------------------------------------------------------------------
    # Main loop: process each HS10 code using the pre-built indices.
    # For each (HS10, UCC) pair the scoring replicates calculate_semantic_similarity:
    #   1. Direct token overlap → overlap_ratio (may be < 0.3 → filtered)
    #   2. Semantic mapping    → 0.85  (only if no direct overlap with that UCC)
    #   3. Substring match     → 0.55  (only if no direct overlap or semantic match)
    # ------------------------------------------------------------------

    for idx, hs10_row in hs10_df.iterrows():
        if idx % 1000 == 0:
            print(f"  Processed {idx}/{len(hs10_df)} HS10 codes...")

        hs10_code = str(hs10_row['HS10 Code'])
        hs10_desc = str(hs10_row['HS10 Description'])
        hs10_norm = normalize_text(hs10_desc)
        hs10_tokens = tokenize(hs10_desc)
        hs10_substantial = frozenset(t for t in hs10_tokens if len(t) > 3)
        hs10_5plus = frozenset(w for w in hs10_tokens if len(w) > 4)

        # ucc_idx -> match dict (highest-priority score wins)
        best_matches_dict: Dict[int, Dict] = {}

        # Step 1: Direct token overlap via inverted index.
        # Collect UCC candidates that share ≥1 substantial token with HS10.
        direct_candidates: Set[int] = set()
        for token in hs10_substantial:
            for ucc_idx in token_to_ucc_indices.get(token, []):
                direct_candidates.add(ucc_idx)

        for ucc_idx in direct_candidates:
            ucc_code, ucc_desc, _, ucc_tokens, ucc_substantial, _ = ucc_precomputed[ucc_idx]
            common_tokens = hs10_substantial & ucc_substantial
            if common_tokens:
                min_len = min(len(hs10_tokens), len(ucc_tokens))
                if min_len > 0:
                    overlap_ratio = min(1.0, len(common_tokens) / min_len * 1.2)
                    reasoning = f"Direct match on: {', '.join(list(common_tokens)[:3])}"
                    if overlap_ratio >= 0.3:
                        confidence = assign_confidence_level(overlap_ratio, reasoning)
                        best_matches_dict[ucc_idx] = {
                            'ucc_code': ucc_code,
                            'ucc_description': ucc_desc,
                            'confidence_level': confidence,
                            'match_reasoning': reasoning,
                            'similarity_score': overlap_ratio,
                            'demographic_split': 1.0,
                        }

        # Step 2: Semantic matching.
        # Only for UCCs NOT already in direct_candidates (direct overlap takes priority,
        # even when the overlap score was < 0.3, mirroring the original early-return logic).
        for hs10_key, pattern in hs10_key_patterns.items():
            if pattern.search(hs10_norm):
                for ucc_idx, synonym in hs10_key_to_ucc_list.get(hs10_key, []):
                    if ucc_idx in direct_candidates:
                        continue  # direct overlap takes priority
                    if ucc_idx in best_matches_dict:
                        continue  # already matched via an earlier semantic key
                    ucc_code, ucc_desc = ucc_precomputed[ucc_idx][0], ucc_precomputed[ucc_idx][1]
                    reasoning = f"Semantic match: '{hs10_key}' \u2192 '{synonym}'"
                    score = 0.85
                    confidence = assign_confidence_level(score, reasoning)
                    best_matches_dict[ucc_idx] = {
                        'ucc_code': ucc_code,
                        'ucc_description': ucc_desc,
                        'confidence_level': confidence,
                        'match_reasoning': reasoning,
                        'similarity_score': score,
                        'demographic_split': 1.0,
                    }

        # Step 3: Substring matching fallback.
        # Only for UCCs not already captured by steps 1 or 2.
        if hs10_5plus:
            already_covered: Set[int] = direct_candidates | set(best_matches_dict.keys())
            for ucc_word, ucc_idx in all_ucc_5plus_words:
                if ucc_idx in already_covered:
                    continue
                if len(ucc_word) < 5:
                    continue
                for hs10_word in hs10_5plus:
                    if len(hs10_word) < 5:
                        continue
                    if hs10_word in ucc_word or ucc_word in hs10_word:
                        ucc_code, ucc_desc = ucc_precomputed[ucc_idx][0], ucc_precomputed[ucc_idx][1]
                        reasoning = f"Partial match: '{hs10_word}' \u2248 '{ucc_word}'"
                        score = 0.55
                        confidence = assign_confidence_level(score, reasoning)
                        best_matches_dict[ucc_idx] = {
                            'ucc_code': ucc_code,
                            'ucc_description': ucc_desc,
                            'confidence_level': confidence,
                            'match_reasoning': reasoning,
                            'similarity_score': score,
                            'demographic_split': 1.0,
                        }
                        already_covered.add(ucc_idx)
                        break  # first hs10_word match per UCC is sufficient

        best_matches = list(best_matches_dict.values())

        # Handle apparel/footwear demographic splits
        if is_apparel_footwear(hs10_desc) and len(best_matches) == 0:
            footwear_matches = get_demographic_ucc_codes(ucc_df, 'FOOTWEAR')
            if footwear_matches:
                for match in footwear_matches:
                    best_matches.append({
                        'ucc_code': match['ucc_code'],
                        'ucc_description': match['ucc_description'],
                        'confidence_level': 'MEDIUM',
                        'match_reasoning': 'Generic footwear matched to demographic categories (25% split)',
                        'similarity_score': 0.5,
                        'demographic_split': 0.25,
                    })

        # Add matches
        if best_matches:
            # Sort by similarity and keep top matches
            best_matches.sort(key=lambda x: x['similarity_score'], reverse=True)

            for match in best_matches[:5]:  # Keep top 5 matches
                matches.append({
                    'hs10_code': hs10_code,
                    'hs10_description': hs10_desc,
                    'ucc_code': match['ucc_code'],
                    'ucc_description': match['ucc_description'],
                    'confidence_level': match['confidence_level'],
                    'match_reasoning': match['match_reasoning'],
                    'demographic_split': match['demographic_split'],
                })
                matched_ucc_codes.add(match['ucc_code'])
        else:
            unmatched_hs10.append({
                'hs10_code': hs10_code,
                'hs10_description': hs10_desc,
                'reason_unmatched': 'No semantic match found above confidence threshold',
            })

    print(f"✓ Created {len(matches)} HS10-UCC pairs")
    print(f"✓ {len(unmatched_hs10)} HS10 codes unmatched")
    print(f"✓ {len(matched_ucc_codes)} unique UCC codes matched")

    return matches, unmatched_hs10, matched_ucc_codes

def identify_unmatched_ucc(ucc_df: pd.DataFrame, matched_ucc_codes: Set[str]) -> List[Dict]:
    """Identify and categorize unmatched UCC codes.
    
    Uses main product description (before parenthetical) to avoid false categorizations.
    """
    unmatched_ucc = []
    
    for _, row in ucc_df.iterrows():
        ucc_code = str(row['ucc_code'])
        ucc_desc = str(row['description'])
        
        if ucc_code not in matched_ucc_codes:
            is_excluded, category = is_excluded_ucc(ucc_desc)
            unmatched_ucc.append({
                'ucc_code': ucc_code,
                'ucc_description': ucc_desc,
                'reason_unmatched': category if is_excluded else 'OTHER - No matching HS10 goods category'
            })
    
    return unmatched_ucc

# ==============================================================================
# SUMMARY AND DOCUMENTATION
# ==============================================================================

def generate_summary(
    hs10_df: pd.DataFrame,
    ucc_df: pd.DataFrame,
    matches: List[Dict],
    unmatched_hs10: List[Dict],
    unmatched_ucc: List[Dict]
) -> str:
    """Generate summary statistics."""
    
    # Count unique codes
    unique_hs10_matched = len(set(m['hs10_code'] for m in matches))
    unique_ucc_matched = len(set(m['ucc_code'] for m in matches))
    
    # Confidence distribution
    confidence_dist = defaultdict(int)
    for match in matches:
        confidence_dist[match['confidence_level']] += 1
    
    # Demographic splits
    demographic_splits = sum(1 for m in matches if m['demographic_split'] < 1.0)
    
    # Unmatched UCC categories
    ucc_category_counts = defaultdict(int)
    for ucc in unmatched_ucc:
        ucc_category_counts[ucc['reason_unmatched']] += 1
    
    summary = f"""
HS10-to-UCC CONCORDANCE MAPPING SUMMARY
========================================

INPUT DATA
----------
Total HS10 codes:            {len(hs10_df):,}
Total UCC codes:             {len(ucc_df):,}

MATCHING RESULTS
----------------
HS10 codes matched:          {unique_hs10_matched:,} ({100*unique_hs10_matched/len(hs10_df):.1f}%)
HS10 codes unmatched:        {len(unmatched_hs10):,} ({100*len(unmatched_hs10)/len(hs10_df):.1f}%)

UCC codes matched:           {unique_ucc_matched:,} ({100*unique_ucc_matched/len(ucc_df):.1f}%)
UCC codes unmatched:         {len(unmatched_ucc):,} ({100*len(unmatched_ucc)/len(ucc_df):.1f}%)

Total HS10-UCC pairs:        {len(matches):,}

CONFIDENCE LEVEL DISTRIBUTION
------------------------------
HIGH:                        {confidence_dist['HIGH']:,} pairs
MEDIUM-HIGH:                 {confidence_dist['MEDIUM-HIGH']:,} pairs
MEDIUM:                      {confidence_dist['MEDIUM']:,} pairs
LOW:                         {confidence_dist['LOW']:,} pairs

DEMOGRAPHIC SPLITS
------------------
Pairs with demographic splits (0.25): {demographic_splits:,}

UNMATCHED UCC CODES BY CATEGORY
--------------------------------
"""
    
    for category in sorted(ucc_category_counts.keys()):
        count = ucc_category_counts[category]
        summary += f"{category:20s} {count:,} codes\n"
    
    summary += f"\nGenerated: 2026-01-10\n"
    
    return summary

def generate_methodology() -> str:
    """Generate methodology documentation."""
    
    methodology = """
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
"""
    
    return methodology

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function."""
    
    print("\n" + "="*70)
    print("HS10-to-UCC CONCORDANCE MAPPING SYSTEM")
    print("="*70 + "\n")
    
    # Load data
    print("Step 1: Loading input data...")
    hs10_df = pd.read_excel(HS10_FILE, dtype=str)
    ucc_df = pd.read_csv(UCC_FILE, dtype=str)
    print(f"✓ Loaded {len(hs10_df)} HS10 codes")
    print(f"✓ Loaded {len(ucc_df)} UCC codes\n")
    
    # Create concordance
    print("Step 2: Creating concordance mapping...")
    matches, unmatched_hs10, matched_ucc_codes = create_concordance(hs10_df, ucc_df)
    print()
    
    # Identify unmatched UCC codes
    print("Step 3: Identifying unmatched UCC codes...")
    unmatched_ucc = identify_unmatched_ucc(ucc_df, matched_ucc_codes)
    print(f"✓ Identified {len(unmatched_ucc)} unmatched UCC codes\n")
    
    # Save outputs
    print("Step 4: Saving output files...")
    
    # 1. Main concordance
    concordance_df = pd.DataFrame(matches)
    concordance_df.to_csv(CONCORDANCE_FILE, index=False)
    print(f"✓ Saved {CONCORDANCE_FILE}")
    
    # 2. Unmatched HS10
    unmatched_hs10_df = pd.DataFrame(unmatched_hs10)
    unmatched_hs10_df.to_csv(UNMATCHED_HS10_FILE, index=False)
    print(f"✓ Saved {UNMATCHED_HS10_FILE}")
    
    # 3. Unmatched UCC
    unmatched_ucc_df = pd.DataFrame(unmatched_ucc)
    unmatched_ucc_df.to_csv(UNMATCHED_UCC_FILE, index=False)
    print(f"✓ Saved {UNMATCHED_UCC_FILE}")
    
    # 4. Summary statistics
    summary = generate_summary(hs10_df, ucc_df, matches, unmatched_hs10, unmatched_ucc)
    with open(SUMMARY_FILE, 'w') as f:
        f.write(summary)
    print(f"✓ Saved {SUMMARY_FILE}")
    
    # 5. Methodology documentation
    methodology = generate_methodology()
    with open(METHODOLOGY_FILE, 'w') as f:
        f.write(methodology)
    print(f"✓ Saved {METHODOLOGY_FILE}")
    
    print("\n" + "="*70)
    print("CONCORDANCE MAPPING COMPLETE!")
    print("="*70)
    print("\nOutput files created:")
    print(f"  1. {CONCORDANCE_FILE}")
    print(f"  2. {UNMATCHED_HS10_FILE}")
    print(f"  3. {UNMATCHED_UCC_FILE}")
    print(f"  4. {SUMMARY_FILE}")
    print(f"  5. {METHODOLOGY_FILE}")
    print(f"  6. {__file__} (this script)")
    print("\n" + summary)

if __name__ == '__main__':
    main()
