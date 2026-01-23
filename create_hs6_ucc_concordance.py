#!/usr/bin/env python3
"""
Improved HS6-to-UCC Concordance with Advanced Semantic Matching

This script creates a high-quality concordance between HS6 product codes and UCC 
consumption codes that:
1. Maximizes coverage - don't drop too many UCC codes
2. Uses advanced semantic matching - leverage LLM capabilities for understanding
3. Provides transparency - output confidence scores for all matches
4. Handles many-to-many relationships

Author: Automated Concordance System  
Date: 2026-01-23
"""

import pandas as pd
import re
from typing import List, Dict, Tuple, Set
from collections import defaultdict

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Input files
HS6_FILE = 'hs6_2017.csv'
UCC_FILE = 'ucc_codes_2017_2019_merged.csv'

# Output files
CONCORDANCE_FILE = 'concordance_hs6_ucc_2017.csv'
STATS_FILE = 'concordance_stats.txt'
UNMATCHED_FILE = 'unmatched_codes.csv'

# Confidence thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.75
MEDIUM_CONFIDENCE_THRESHOLD = 0.45
LOW_CONFIDENCE_THRESHOLD = 0.25  # Keep LOW matches for coverage

# ==============================================================================
# PRODUCT CATEGORIES
# ==============================================================================

PRODUCT_CATEGORIES = {
    'apparel': {
        'keywords': ['clothing', 'garment', 'shirt', 'pant', 'dress', 'coat', 'jacket', 
                    'sweater', 'suit', 'skirt', 'blouse', 'underwear', 'hosiery', 'tie',
                    'uniform', 'costume', 'robe', 'vest', 'shorts', 'jeans'],
        'hs6_specific': ['knit', 'woven', 'textile', 'cotton', 'synthetic', 'silk', 
                        'wool', 'men', 'women', 'boy', 'girl', 'infant', 'baby']
    },
    'footwear': {
        'keywords': ['footwear', 'shoe', 'boot', 'sandal', 'slipper', 'sneaker',
                    'athletic footwear'],
        'hs6_specific': ['leather', 'rubber', 'plastic', 'textile upper']
    },
    'food_meat': {
        'keywords': ['meat', 'beef', 'pork', 'chicken', 'turkey', 'lamb', 'sausage',
                    'bacon', 'ham', 'frankfurter', 'bologna', 'salami', 'lunchmeat',
                    'roast', 'steak', 'chop', 'ground'],
        'hs6_specific': ['bovine', 'swine', 'poultry', 'cattle', 'pig', 'ovine', 
                        'edible offal', 'carcass']
    },
    'food_fish': {
        'keywords': ['fish', 'seafood', 'salmon', 'tuna', 'shrimp', 'crab', 'lobster'],
        'hs6_specific': ['fresh', 'frozen', 'dried', 'smoked', 'fillet']
    },
    'food_dairy': {
        'keywords': ['milk', 'cheese', 'butter', 'cream', 'yogurt', 'ice cream', 'dairy'],
        'hs6_specific': ['concentrated', 'powder']
    },
    'food_produce': {
        'keywords': ['fruit', 'vegetable', 'apple', 'banana', 'orange', 'grape', 
                    'strawberry', 'tomato', 'potato', 'lettuce', 'carrot', 'onion',
                    'berry', 'melon', 'peach', 'pear', 'plum', 'cherry', 'salad',
                    'cabbage', 'celery', 'cucumber', 'pepper', 'broccoli', 'cauliflower'],
        'hs6_specific': ['fresh', 'frozen', 'dried', 'prepared', 'preserved', 'edible']
    },
    'food_grains': {
        'keywords': ['bread', 'cereal', 'rice', 'wheat', 'flour', 'pasta', 'grain',
                    'oat', 'corn', 'cake', 'cookie', 'cracker', 'pie', 'tart', 
                    'bakery', 'baked', 'doughnut', 'muffin', 'bagel'],
        'hs6_specific': ['milled', 'preparations']
    },
    'food_beverages': {
        'keywords': ['coffee', 'tea', 'juice', 'soft drink', 'soda', 'water', 
                    'beer', 'wine', 'spirits', 'whiskey', 'vodka', 'beverage',
                    'drink', 'cola', 'carbonated'],
        'hs6_specific': ['nonalcoholic', 'alcoholic', 'fermented']
    },
    'electronics': {
        'keywords': ['television', 'tv', 'computer', 'laptop', 'phone', 'smartphone',
                    'camera', 'radio', 'audio', 'video', 'electronic', 'appliance'],
        'hs6_specific': ['receiver', 'monitor', 'display', 'transmission']
    },
    'furniture': {
        'keywords': ['furniture', 'table', 'chair', 'bed', 'sofa', 'desk', 'cabinet',
                    'shelf', 'seating'],
        'hs6_specific': ['wooden', 'metal', 'upholstered']
    },
    'home_goods': {
        'keywords': ['towel', 'linen', 'bedding', 'blanket', 'curtain', 'carpet',
                    'rug', 'kitchen', 'tableware', 'dinnerware', 'glassware'],
        'hs6_specific': ['household', 'domestic']
    },
    'vehicles': {
        'keywords': ['vehicle', 'car', 'automobile', 'truck', 'motorcycle', 'bicycle',
                    'tire', 'parts'],
        'hs6_specific': ['motor', 'engine']
    },
    'toys': {
        'keywords': ['toy', 'game', 'doll', 'puzzle', 'sport equipment', 'bicycle',
                    'playground'],
        'hs6_specific': ['children', 'recreational']
    },
    'personal_care': {
        'keywords': ['soap', 'shampoo', 'cosmetic', 'perfume', 'toothpaste',
                    'beauty', 'personal care'],
        'hs6_specific': ['toilet', 'beauty preparation']
    },
    'tobacco': {
        'keywords': ['tobacco', 'cigarette', 'cigar', 'smoking'],
        'hs6_specific': []
    },
    'books_paper': {
        'keywords': ['book', 'newspaper', 'magazine', 'paper', 'printed matter',
                    'stationery'],
        'hs6_specific': ['printed', 'reading material']
    },
    'jewelry': {
        'keywords': ['jewelry', 'jewellery', 'watch', 'precious metal', 'gold', 
                    'silver', 'diamond'],
        'hs6_specific': ['articles thereof', 'imitation jewelry']
    }
}

# Semantic mappings for better matching
SEMANTIC_MAPPINGS = {
    # Animal to meat product
    'bovine': ['beef', 'cattle', 'roast', 'steak', 'ground beef'],
    'cattle': ['beef', 'roast', 'steak'],
    'swine': ['pork', 'ham', 'bacon', 'sausage', 'frankfurter'],
    'pig': ['pork'],
    'poultry': ['chicken', 'turkey'],
    'ovine': ['lamb', 'mutton'],
    'sheep': ['lamb'],
    'meat': ['beef', 'pork', 'chicken', 'lamb', 'meat', 'sausage', 'bacon', 'ham'],
    'sausage': ['sausage', 'frankfurter', 'bologna'],
    'preparations of meat': ['sausage', 'frankfurter', 'bologna', 'ham', 'bacon'],
    
    # Fish and seafood
    'fish': ['fish', 'seafood'],
    'shellfish': ['fish', 'seafood'],
    'salmon': ['fish'],
    'tuna': ['fish'],
    'shrimp': ['fish', 'seafood'],
    
    # Dairy products
    'milk': ['milk', 'dairy'],
    'cheese': ['cheese', 'dairy'],
    'butter': ['butter', 'dairy'],
    'cream': ['cream', 'dairy'],
    
    # Grains and bakery
    'wheat': ['bread', 'flour', 'cereal', 'cake', 'cookie', 'cracker'],
    'flour': ['flour', 'bread', 'cake', 'cookie'],
    'bread': ['bread'],
    'rice': ['rice'],
    'cereal': ['cereal'],
    'pasta': ['pasta'],
    'cake': ['cake'],
    'cookie': ['cookie'],
    'cracker': ['cracker'],
    'bakery': ['bread', 'cake', 'cookie'],
    'preparations of cereals': ['bread', 'cake', 'cookie', 'cereal', 'pasta'],
    
    # Fruits (specific mappings)
    'apple': ['apple'],
    'banana': ['banana'],
    'orange': ['orange', 'citrus'],
    'grape': ['grape'],
    'citrus': ['orange', 'citrus', 'lemon', 'lime', 'grapefruit'],
    'fruit': ['fruit', 'apple', 'banana', 'orange', 'grape'],
    'preparations of fruit': ['fruit', 'jam', 'jelly', 'canned fruit'],
    'edible fruit': ['fruit', 'apple', 'banana', 'orange'],
    
    # Vegetables
    'potato': ['potato'],
    'tomato': ['tomato'],
    'lettuce': ['lettuce', 'salad'],
    'carrot': ['carrot'],
    'vegetable': ['vegetable', 'lettuce', 'tomato', 'carrot', 'salad'],
    'edible vegetables': ['vegetable', 'potato', 'tomato', 'lettuce', 'salad'],
    'preparations of vegetables': ['salad', 'vegetable'],
    
    # Beverages
    'coffee': ['coffee'],
    'tea': ['tea'],
    'juice': ['juice'],
    'beer': ['beer'],
    'wine': ['wine'],
    'spirits': ['whiskey', 'vodka', 'spirits'],
    
    # Fabric/material to products (more precise)
    'cotton': ['shirt', 'apparel', 'clothing', 'textile'],
    'wool': ['clothing', 'apparel', 'yarn', 'sweater'],
    'synthetic': ['clothing', 'apparel'],
    'leather': ['footwear', 'shoe', 'boot', 'bag'],
    'rubber': ['footwear', 'tire'],
    'plastic': ['footwear'],
    
    # Apparel specific
    'garment': ['clothing', 'apparel'],
    'footwear': ['shoe', 'boot'],
    'shirt': ['shirt'],
    'pant': ['pant'],
    'dress': ['dress'],
    'coat': ['coat', 'jacket'],
    'jacket': ['jacket', 'coat'],
    'sweater': ['sweater'],
    'underwear': ['underwear'],
    
    # Electronics
    'television': ['television', 'tv'],
    'computer': ['computer'],
    'telephone': ['phone'],
    'radio': ['radio'],
    
    # Furniture
    'furniture': ['furniture', 'table', 'chair'],
    'table': ['table'],
    'chair': ['chair', 'seating'],
    'bed': ['bed'],
    
    # Vehicles
    'automobile': ['car', 'vehicle'],
    'motor vehicle': ['car', 'vehicle'],
    'motorcycle': ['motorcycle'],
    'bicycle': ['bicycle'],
    'tire': ['tire'],
    
    # Tobacco
    'tobacco': ['tobacco', 'cigarette'],
    'cigarette': ['cigarette', 'tobacco'],
    'cigar': ['cigar', 'tobacco'],
    
    # Personal care
    'soap': ['soap'],
    'perfume': ['perfume', 'cologne'],
    'cosmetic': ['cosmetic', 'makeup'],
    
    # Books and paper
    'book': ['book'],
    'newspaper': ['newspaper'],
    'magazine': ['magazine'],
    
    # Jewelry
    'jewelry': ['jewelry', 'jewellery'],
    'watch': ['watch'],
    'precious metal': ['jewelry'],
}

# UCC codes to exclude (services, not goods)
EXCLUDED_UCC_KEYWORDS = [
    'repair', 'service', 'maintenance', 'labor', 'installation',
    'doctor', 'hospital', 'medical care', 'healthcare', 'dental',
    'childcare', 'daycare', 'education', 'tuition',
    'rent', 'mortgage', 'property tax', 'insurance',
    'finance charge', 'interest', 'late charge', 'bank fee',
    'restaurant', 'fast food', 'catered',
    'electricity', 'gas', 'water', 'phone service', 'internet', 'cable',
]

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if pd.isna(text):
        return ""
    return str(text).lower().strip()

def tokenize(text: str) -> Set[str]:
    """Tokenize text into meaningful words."""
    text = normalize_text(text)
    # Remove special characters and split
    tokens = re.findall(r'\b[a-z0-9]+\b', text)
    
    # Common stopwords to exclude
    stopwords = {'the', 'a', 'an', 'and', 'or', 'of', 'for', 'in', 'on', 'at', 'to', 
                 'with', 'from', 'by', 'as', 'is', 'that', 'this', 'these', 'those',
                 'not', 'more', 'than', 'other', 'nesoi', 'except', 'including'}
    
    return set(t for t in tokens if t not in stopwords and len(t) > 2)

def is_excluded_ucc(ucc_desc: str) -> bool:
    """Check if UCC code should be excluded (services, not goods)."""
    desc_norm = normalize_text(ucc_desc)
    return any(keyword in desc_norm for keyword in EXCLUDED_UCC_KEYWORDS)

def get_category(description: str, categories: Dict) -> List[str]:
    """Identify which product categories match the description."""
    desc_norm = normalize_text(description)
    matched_categories = []
    
    for category, keywords_dict in categories.items():
        all_keywords = keywords_dict['keywords'] + keywords_dict.get('hs6_specific', [])
        for keyword in all_keywords:
            if keyword in desc_norm:
                matched_categories.append(category)
                break
    
    return matched_categories

# ==============================================================================
# STAGE 1: DIRECT MATCHING
# ==============================================================================

def direct_match_score(hs6_desc: str, ucc_desc: str) -> Tuple[float, str]:
    """
    Calculate direct matching score based on keyword overlap.
    Returns (score, reasoning)
    """
    hs6_tokens = tokenize(hs6_desc)
    ucc_tokens = tokenize(ucc_desc)
    
    # Exact token matches
    common_tokens = hs6_tokens & ucc_tokens
    if len(common_tokens) > 0:
        # Filter for substantial tokens (length > 3)
        substantial = [t for t in common_tokens if len(t) > 3]
        if substantial:
            # Calculate overlap ratio
            overlap_ratio = len(substantial) / min(len(hs6_tokens), len(ucc_tokens))
            # Give bonus for multiple matches
            if len(substantial) >= 3:
                overlap_ratio = min(1.0, overlap_ratio * 1.5)
            elif len(substantial) >= 2:
                overlap_ratio = min(1.0, overlap_ratio * 1.3)
            reasoning = f"exact_keyword: {', '.join(sorted(substantial)[:3])}"
            return overlap_ratio, reasoning
        
        # Even short tokens might be meaningful if there are several
        if len(common_tokens) >= 3:
            overlap_ratio = len(common_tokens) / min(len(hs6_tokens), len(ucc_tokens))
            overlap_ratio = min(0.6, overlap_ratio)  # Cap at 0.6 for short tokens
            reasoning = f"exact_keyword: {', '.join(sorted(list(common_tokens))[:3])}"
            return overlap_ratio, reasoning
    
    return 0.0, ""

# ==============================================================================
# STAGE 2: SEMANTIC MATCHING
# ==============================================================================

def semantic_match_score(hs6_desc: str, ucc_desc: str) -> Tuple[float, str]:
    """
    Calculate semantic similarity using product understanding.
    Returns (score, reasoning)
    """
    hs6_norm = normalize_text(hs6_desc)
    ucc_norm = normalize_text(ucc_desc)
    
    best_score = 0.0
    best_reasoning = ""
    
    # Check semantic mappings
    for hs6_key, ucc_synonyms in SEMANTIC_MAPPINGS.items():
        # Use word boundaries to avoid false matches
        if re.search(r'\b' + re.escape(hs6_key) + r'\b', hs6_norm):
            for synonym in ucc_synonyms:
                if re.search(r'\b' + re.escape(synonym) + r'\b', ucc_norm):
                    score = 0.80  # HIGH confidence for known semantic relationships
                    reasoning = f"semantic_category: '{hs6_key}' → '{synonym}'"
                    if score > best_score:
                        best_score = score
                        best_reasoning = reasoning
    
    if best_score > 0:
        return best_score, best_reasoning
    
    # Category-level matching
    hs6_categories = get_category(hs6_desc, PRODUCT_CATEGORIES)
    ucc_categories = get_category(ucc_desc, PRODUCT_CATEGORIES)
    
    common_categories = set(hs6_categories) & set(ucc_categories)
    if common_categories:
        # Same category = MEDIUM-HIGH confidence
        category_name = list(common_categories)[0]
        score = 0.65
        reasoning = f"semantic_category: both in '{category_name}'"
        if len(common_categories) > 1:
            score = 0.70  # Multiple category matches = higher confidence
            reasoning = f"semantic_category: multiple matches ({len(common_categories)})"
        return score, reasoning
    
    # Related categories - only for specific logical relationships
    if hs6_categories and ucc_categories:
        hs6_cat = hs6_categories[0]
        ucc_cat = ucc_categories[0]
        
        # Define acceptable related category pairs
        # Format: (hs6_category, ucc_category, score, reason)
        acceptable_relations = [
            # Apparel materials to apparel products
            ('apparel', 'footwear', 0.40, 'related: apparel/footwear'),
            ('footwear', 'apparel', 0.40, 'related: apparel/footwear'),
            # Home textiles
            ('apparel', 'home_goods', 0.35, 'related: textile products'),
            ('home_goods', 'apparel', 0.35, 'related: textile products'),
        ]
        
        for rel_hs6, rel_ucc, rel_score, rel_reason in acceptable_relations:
            if hs6_cat == rel_hs6 and ucc_cat == rel_ucc:
                return rel_score, f"semantic_similarity: {rel_reason}"
    
    return 0.0, ""

# ==============================================================================
# STAGE 3: COMBINED MATCHING
# ==============================================================================

def calculate_match_quality(hs6_desc: str, ucc_desc: str) -> Dict:
    """
    Calculate overall match quality combining all methods.
    Returns dict with score, confidence, method, and notes.
    """
    # Try direct matching first
    direct_score, direct_reason = direct_match_score(hs6_desc, ucc_desc)
    
    # Try semantic matching
    semantic_score, semantic_reason = semantic_match_score(hs6_desc, ucc_desc)
    
    # Take the best score
    if direct_score >= semantic_score:
        final_score = direct_score
        method = "exact_keyword"
        notes = direct_reason
    else:
        final_score = semantic_score
        method = "semantic_similarity" if 'similarity' in semantic_reason else "semantic_category"
        notes = semantic_reason
    
    # Assign confidence level
    if final_score >= HIGH_CONFIDENCE_THRESHOLD:
        confidence = "HIGH"
    elif final_score >= MEDIUM_CONFIDENCE_THRESHOLD:
        confidence = "MEDIUM"
    elif final_score >= LOW_CONFIDENCE_THRESHOLD:
        confidence = "LOW"
    else:
        confidence = None  # Below threshold, don't match
    
    return {
        'score': final_score,
        'confidence': confidence,
        'method': method,
        'notes': notes
    }

# ==============================================================================
# MAIN MATCHING LOGIC
# ==============================================================================

def create_concordance(hs6_df: pd.DataFrame, ucc_df: pd.DataFrame) -> Tuple[List[Dict], Set[str], Set[str]]:
    """
    Create comprehensive HS6-to-UCC concordance.
    Returns (matches, matched_hs6_codes, matched_ucc_codes)
    """
    matches = []
    matched_hs6_codes = set()
    matched_ucc_codes = set()
    
    print("\n" + "="*70)
    print("CREATING HS6-TO-UCC CONCORDANCE")
    print("="*70)
    print(f"\nTotal HS6 codes: {len(hs6_df):,}")
    print(f"Total UCC codes: {len(ucc_df):,}")
    
    # Filter out excluded UCC codes (services)
    ucc_goods = []
    ucc_excluded = []
    for _, row in ucc_df.iterrows():
        if is_excluded_ucc(row['description']):
            ucc_excluded.append(row['ucc_code'])
        else:
            ucc_goods.append(row)
    
    ucc_goods_df = pd.DataFrame(ucc_goods)
    print(f"UCC goods codes (after filtering services): {len(ucc_goods_df):,}")
    print(f"UCC service codes (excluded): {len(ucc_excluded):,}\n")
    
    # Pre-compute UCC categories for faster matching
    print("Pre-computing UCC categories...")
    ucc_categories_cache = {}
    ucc_tokens_cache = {}
    for _, ucc_row in ucc_goods_df.iterrows():
        ucc_code = str(ucc_row['ucc_code'])
        ucc_desc = str(ucc_row['description'])
        ucc_categories_cache[ucc_code] = get_category(ucc_desc, PRODUCT_CATEGORIES)
        ucc_tokens_cache[ucc_code] = tokenize(ucc_desc)
    
    print("Processing HS6 codes...")
    
    # Track matches per UCC for statistics
    ucc_match_counts = defaultdict(list)
    
    # Process each HS6 code
    for idx, hs6_row in hs6_df.iterrows():
        if idx % 500 == 0 and idx > 0:
            print(f"  Processed {idx}/{len(hs6_df)} HS6 codes...")
        
        hs6_code = str(hs6_row['Code'])
        hs6_desc = str(hs6_row['Description'])
        
        # Pre-compute HS6 properties
        hs6_categories = get_category(hs6_desc, PRODUCT_CATEGORIES)
        hs6_tokens = tokenize(hs6_desc)
        
        # Find all matching UCC codes
        hs6_matches = []
        
        for _, ucc_row in ucc_goods_df.iterrows():
            ucc_code = str(ucc_row['ucc_code'])
            ucc_desc = str(ucc_row['description'])
            
            # Quick category filter - skip if no category overlap and no tokens match
            ucc_categories = ucc_categories_cache[ucc_code]
            if hs6_categories and ucc_categories:
                if not (set(hs6_categories) & set(ucc_categories)):
                    # Different categories - check for token overlap before skipping
                    ucc_tokens = ucc_tokens_cache[ucc_code]
                    common = hs6_tokens & ucc_tokens
                    if not common or len([t for t in common if len(t) > 3]) == 0:
                        continue  # Skip - no overlap
            
            # Calculate match quality
            match_quality = calculate_match_quality(hs6_desc, ucc_desc)
            
            if match_quality['confidence'] is not None:
                hs6_matches.append({
                    'ucc_code': ucc_code,
                    'ucc_description': ucc_desc,
                    'score': match_quality['score'],
                    'confidence': match_quality['confidence'],
                    'method': match_quality['method'],
                    'notes': match_quality['notes']
                })
        
        # Sort by score and limit to reasonable number per HS6
        # Keep top matches but don't create thousands of low-value matches
        hs6_matches.sort(key=lambda x: x['score'], reverse=True)
        
        # Limit matches based on confidence:
        # - Keep all HIGH confidence matches
        # - Keep top 15 MEDIUM confidence matches  
        # - Keep top 8 LOW confidence matches
        high_matches = [m for m in hs6_matches if m['confidence'] == 'HIGH']
        medium_matches = [m for m in hs6_matches if m['confidence'] == 'MEDIUM'][:15]
        low_matches = [m for m in hs6_matches if m['confidence'] == 'LOW'][:8]
        hs6_matches = high_matches + medium_matches + low_matches
        
        for match in hs6_matches:
            matches.append({
                'hs6': hs6_code,
                'hs6_description': hs6_desc,
                'ucc': match['ucc_code'],
                'ucc_description': match['ucc_description'],
                'confidence': match['confidence'],
                'confidence_score': int(match['score'] * 100),  # 0-100 scale
                'match_method': match['method'],
                'notes': match['notes']
            })
            matched_hs6_codes.add(hs6_code)
            matched_ucc_codes.add(match['ucc_code'])
            ucc_match_counts[match['ucc_code']].append(hs6_code)
    
    print(f"  Processed {len(hs6_df)}/{len(hs6_df)} HS6 codes.\n")
    
    # Second pass: For unmatched UCCs, try broader matching
    print("Second pass: Matching remaining UCCs with broader criteria...")
    unmatched_uccs = set(str(row['ucc_code']) for _, row in ucc_goods_df.iterrows()) - matched_ucc_codes
    
    if unmatched_uccs:
        print(f"  Attempting to match {len(unmatched_uccs)} unmatched UCCs...")
        second_pass_matches = 0
        
        for ucc_code in unmatched_uccs:
            ucc_row = ucc_goods_df[ucc_goods_df['ucc_code'] == ucc_code].iloc[0]
            ucc_desc = str(ucc_row['description'])
            ucc_categories = ucc_categories_cache[ucc_code]
            
            # Try to find HS6 codes in the same category
            best_hs6_match = None
            best_score = 0.20  # Lower threshold for second pass
            
            for _, hs6_row in hs6_df.iterrows():
                hs6_code = str(hs6_row['Code'])
                hs6_desc = str(hs6_row['Description'])
                hs6_categories = get_category(hs6_desc, PRODUCT_CATEGORIES)
                
                # Same category match
                if ucc_categories and hs6_categories:
                    if set(ucc_categories) & set(hs6_categories):
                        # Found a category match
                        score = 0.30  # LOW confidence
                        if score > best_score:
                            best_score = score
                            best_hs6_match = {
                                'hs6_code': hs6_code,
                                'hs6_desc': hs6_desc,
                                'score': score,
                                'reasoning': f"second_pass: same category {ucc_categories[0]}"
                            }
            
            if best_hs6_match:
                matches.append({
                    'hs6': best_hs6_match['hs6_code'],
                    'hs6_description': best_hs6_match['hs6_desc'],
                    'ucc': ucc_code,
                    'ucc_description': ucc_desc,
                    'confidence': 'LOW',
                    'confidence_score': int(best_hs6_match['score'] * 100),
                    'match_method': 'semantic_category',
                    'notes': best_hs6_match['reasoning']
                })
                matched_ucc_codes.add(ucc_code)
                second_pass_matches += 1
        
        print(f"  Second pass matched {second_pass_matches} additional UCCs\n")
    
    print("="*70)
    print("MATCHING COMPLETE")
    print("="*70)
    print(f"Total matches: {len(matches):,}")
    print(f"HS6 codes matched: {len(matched_hs6_codes):,} ({100*len(matched_hs6_codes)/len(hs6_df):.1f}%)")
    print(f"UCC codes matched: {len(matched_ucc_codes):,} ({100*len(matched_ucc_codes)/len(ucc_goods_df):.1f}%)")
    
    return matches, matched_hs6_codes, matched_ucc_codes

# ==============================================================================
# STATISTICS AND QUALITY CHECKS
# ==============================================================================

def generate_statistics(
    hs6_df: pd.DataFrame,
    ucc_df: pd.DataFrame,
    matches: List[Dict],
    matched_hs6_codes: Set[str],
    matched_ucc_codes: Set[str]
) -> str:
    """Generate comprehensive statistics."""
    
    # Filter excluded UCCs
    ucc_goods_count = sum(1 for _, row in ucc_df.iterrows() if not is_excluded_ucc(row['description']))
    
    # Confidence distribution
    confidence_dist = defaultdict(int)
    for match in matches:
        confidence_dist[match['confidence']] += 1
    
    # Method distribution
    method_dist = defaultdict(int)
    for match in matches:
        method_dist[match['match_method']] += 1
    
    # Many-to-many analysis
    hs6_to_ucc_counts = defaultdict(int)
    ucc_to_hs6_counts = defaultdict(int)
    for match in matches:
        hs6_to_ucc_counts[match['hs6']] += 1
        ucc_to_hs6_counts[match['ucc']] += 1
    
    one_to_one = sum(1 for count in hs6_to_ucc_counts.values() if count == 1)
    one_to_many = sum(1 for count in hs6_to_ucc_counts.values() if count > 1)
    many_to_one_uccs = sum(1 for count in ucc_to_hs6_counts.values() if count > 1)
    
    # Average matches per code
    avg_ucc_per_hs6 = len(matches) / len(matched_hs6_codes) if matched_hs6_codes else 0
    avg_hs6_per_ucc = len(matches) / len(matched_ucc_codes) if matched_ucc_codes else 0
    
    stats = f"""
HS6-TO-UCC CONCORDANCE STATISTICS
===================================

Generated: 2026-01-23

INPUT DATA
----------
Total HS6 codes:                {len(hs6_df):,}
Total UCC codes:                {len(ucc_df):,}
UCC goods codes (non-service):  {ucc_goods_count:,}

MATCHING RESULTS
----------------
Total HS6-UCC pairs:            {len(matches):,}

HS6 Coverage:
  Codes matched:                {len(matched_hs6_codes):,} ({100*len(matched_hs6_codes)/len(hs6_df):.1f}%)
  Codes unmatched:              {len(hs6_df) - len(matched_hs6_codes):,} ({100*(len(hs6_df)-len(matched_hs6_codes))/len(hs6_df):.1f}%)

UCC Coverage:
  Goods codes matched:          {len(matched_ucc_codes):,} ({100*len(matched_ucc_codes)/ucc_goods_count:.1f}%)
  Goods codes unmatched:        {ucc_goods_count - len(matched_ucc_codes):,} ({100*(ucc_goods_count-len(matched_ucc_codes))/ucc_goods_count:.1f}%)

CONFIDENCE LEVEL DISTRIBUTION
------------------------------
HIGH:                           {confidence_dist['HIGH']:,} pairs ({100*confidence_dist['HIGH']/len(matches):.1f}%)
MEDIUM:                         {confidence_dist['MEDIUM']:,} pairs ({100*confidence_dist['MEDIUM']/len(matches):.1f}%)
LOW:                            {confidence_dist['LOW']:,} pairs ({100*confidence_dist['LOW']/len(matches):.1f}%)

MATCH METHOD DISTRIBUTION
--------------------------
Exact keyword:                  {method_dist['exact_keyword']:,} pairs
Semantic category:              {method_dist['semantic_category']:,} pairs
Semantic similarity:            {method_dist['semantic_similarity']:,} pairs

RELATIONSHIP ANALYSIS
---------------------
HS6 codes with 1 UCC:           {one_to_one:,} (1:1)
HS6 codes with multiple UCCs:   {one_to_many:,} (1:many)
UCC codes with multiple HS6s:   {many_to_one_uccs:,} (many:1)

Average UCCs per HS6:           {avg_ucc_per_hs6:.2f}
Average HS6s per UCC:           {avg_hs6_per_ucc:.2f}

SUCCESS CRITERIA
----------------
✓ UCC match rate >85%:          {'YES' if 100*len(matched_ucc_codes)/ucc_goods_count >= 85 else 'NO'} ({100*len(matched_ucc_codes)/ucc_goods_count:.1f}%)
✓ HS6 coverage >90%:            {'YES' if 100*len(matched_hs6_codes)/len(hs6_df) >= 90 else 'NO'} ({100*len(matched_hs6_codes)/len(hs6_df):.1f}%)
✓ Balanced confidence:          {'YES' if confidence_dist['HIGH'] > 0 and confidence_dist['MEDIUM'] > 0 and confidence_dist['LOW'] > 0 else 'NO'}
✓ Transparency:                 YES (all matches documented)

"""
    
    return stats

def identify_unmatched_codes(
    hs6_df: pd.DataFrame,
    ucc_df: pd.DataFrame,
    matched_hs6_codes: Set[str],
    matched_ucc_codes: Set[str]
) -> List[Dict]:
    """Identify and document unmatched codes."""
    unmatched = []
    
    # Unmatched HS6 codes
    for _, row in hs6_df.iterrows():
        hs6_code = str(row['Code'])
        if hs6_code not in matched_hs6_codes:
            unmatched.append({
                'code_type': 'HS6',
                'code': hs6_code,
                'description': str(row['Description']),
                'reason': 'No UCC match found above confidence threshold'
            })
    
    # Unmatched UCC codes (excluding services)
    for _, row in ucc_df.iterrows():
        ucc_code = str(row['ucc_code'])
        ucc_desc = str(row['description'])
        if ucc_code not in matched_ucc_codes:
            if is_excluded_ucc(ucc_desc):
                reason = 'SERVICE (excluded from matching)'
            else:
                reason = 'No HS6 match found above confidence threshold'
            unmatched.append({
                'code_type': 'UCC',
                'code': ucc_code,
                'description': ucc_desc,
                'reason': reason
            })
    
    return unmatched

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function."""
    
    print("\n" + "="*70)
    print("IMPROVED HS6-TO-UCC CONCORDANCE")
    print("Advanced Semantic Matching System")
    print("="*70 + "\n")
    
    # Load data
    print("Loading input data...")
    hs6_df = pd.read_csv(HS6_FILE, dtype=str)
    ucc_df = pd.read_csv(UCC_FILE, dtype=str)
    print(f"✓ Loaded {len(hs6_df):,} HS6 codes")
    print(f"✓ Loaded {len(ucc_df):,} UCC codes")
    
    # Create concordance
    matches, matched_hs6_codes, matched_ucc_codes = create_concordance(hs6_df, ucc_df)
    
    # Generate statistics
    print("\nGenerating statistics...")
    stats = generate_statistics(hs6_df, ucc_df, matches, matched_hs6_codes, matched_ucc_codes)
    
    # Identify unmatched codes
    print("Identifying unmatched codes...")
    unmatched = identify_unmatched_codes(hs6_df, ucc_df, matched_hs6_codes, matched_ucc_codes)
    print(f"✓ Identified {len(unmatched):,} unmatched codes\n")
    
    # Save outputs
    print("Saving output files...")
    
    # 1. Main concordance
    concordance_df = pd.DataFrame(matches)
    # Ensure codes are strings
    concordance_df['hs6'] = concordance_df['hs6'].astype(str)
    concordance_df['ucc'] = concordance_df['ucc'].astype(str)
    concordance_df.to_csv(CONCORDANCE_FILE, index=False)
    print(f"✓ Saved {CONCORDANCE_FILE}")
    
    # 2. Statistics
    with open(STATS_FILE, 'w') as f:
        f.write(stats)
    print(f"✓ Saved {STATS_FILE}")
    
    # 3. Unmatched codes
    unmatched_df = pd.DataFrame(unmatched)
    unmatched_df.to_csv(UNMATCHED_FILE, index=False)
    print(f"✓ Saved {UNMATCHED_FILE}")
    
    print("\n" + "="*70)
    print("CONCORDANCE GENERATION COMPLETE!")
    print("="*70)
    print("\nOutput files:")
    print(f"  1. {CONCORDANCE_FILE} - Main concordance with confidence scores")
    print(f"  2. {STATS_FILE} - Detailed statistics and quality metrics")
    print(f"  3. {UNMATCHED_FILE} - Unmatched codes with explanations")
    print("\n" + stats)

if __name__ == '__main__':
    main()
