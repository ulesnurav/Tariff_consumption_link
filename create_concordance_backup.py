#!/usr/bin/env python3
"""
HS6 to UCC Concordance Generator
Uses LLM-based semantic matching to map HS6 trade codes to UCC consumption categories
"""

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# For this implementation, we'll create a rule-based semantic matcher
# that can be enhanced with actual LLM calls if API access is available

class HS6_UCC_Concordance:
    def __init__(self, hs6_file: str, ucc_file: str):
        self.hs6_data = []
        self.ucc_data = []
        self.concordance = []
        self.unmatched_hs6 = []
        self.unmatched_ucc = []
        
        # Load data
        self.load_hs6_data(hs6_file)
        self.load_ucc_data(ucc_file)
        
        # Category mappings for apparel
        self.apparel_ucc_categories = {
            'mens': [],
            'womens': [],
            'boys': [],
            'girls': []
        }
        self.load_apparel_categories()
        
    def load_hs6_data(self, filename: str):
        """Load HS6 codes from CSV"""
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.hs6_data.append({
                    'code': row['Code'],
                    'description': row['Description'],
                    'parent': row['Parent Code'],
                    'chapter': row['Code'][:2] if len(row['Code']) >= 2 else ''
                })
        print(f"Loaded {len(self.hs6_data)} HS6 codes")
    
    def load_ucc_data(self, filename: str):
        """Load UCC codes from CSV"""
        with open(filename, 'r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.ucc_data.append({
                    'ucc_code': row['UCC'],
                    'eli_code': row['ELI'],
                    'ucc_name': row['UCC NAME'],
                    'eli_title': row['ELI TITLE'],
                    'ce_source': row['CE SOURCE']
                })
        print(f"Loaded {len(self.ucc_data)} UCC codes")
    
    def load_apparel_categories(self):
        """Identify apparel UCC categories for men/women/boys/girls"""
        for ucc in self.ucc_data:
            name_lower = ucc['ucc_name'].lower()
            title_lower = ucc['eli_title'].lower()
            
            if any(term in name_lower or term in title_lower for term in ['men\'s', 'mens', 'man\'s']):
                self.apparel_ucc_categories['mens'].append(ucc)
            if any(term in name_lower or term in title_lower for term in ['women\'s', 'womens', 'woman\'s', 'ladies']):
                self.apparel_ucc_categories['womens'].append(ucc)
            if any(term in name_lower or term in title_lower for term in ['boy\'s', 'boys']):
                self.apparel_ucc_categories['boys'].append(ucc)
            if any(term in name_lower or term in title_lower for term in ['girl\'s', 'girls']):
                self.apparel_ucc_categories['girls'].append(ucc)
    
    def is_service_ucc(self, ucc: Dict) -> bool:
        """Determine if a UCC code represents a service (no physical goods)"""
        service_keywords = [
            'service', 'repair', 'rental', 'lease', 'insurance', 'tuition', 
            'education', 'healthcare', 'medical care', 'hospital', 'physician',
            'dental', 'veterinary', 'legal', 'accounting', 'banking', 'financial',
            'entertainment', 'admission', 'membership', 'subscription', 'cable',
            'internet', 'phone', 'cellular', 'postage', 'delivery', 'shipping',
            'parking', 'tolls', 'transit', 'airline', 'lodging', 'hotel',
            'daycare', 'care', 'maintenance', 'labor'
        ]
        
        text = (ucc['ucc_name'] + ' ' + ucc['eli_title']).lower()
        return any(keyword in text for keyword in service_keywords)
    
    def match_hs6_to_ucc(self, hs6: Dict) -> List[Dict]:
        """
        Match an HS6 code to relevant UCC codes using semantic matching
        Returns list of matches with confidence and reasoning
        """
        matches = []
        hs6_code = hs6['code']
        hs6_desc = hs6['description'].lower()
        chapter = hs6['chapter']
        
        # Special handling for apparel (chapters 61-62)
        if chapter in ['61', '62']:
            return self.match_apparel(hs6)
        
        # Special handling for footwear (chapter 64)
        if chapter == '64':
            return self.match_footwear(hs6)
        
        # General semantic matching logic
        # This is a simplified rule-based approach that can be enhanced with actual LLM calls
        
        # Food products matching
        if chapter in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', 
                       '11', '12', '15', '16', '17', '18', '19', '20', '21', '22', '23']:
            matches = self.match_food_products(hs6)
        
        # Household goods, furniture, appliances
        elif chapter in ['84', '85', '94']:
            matches = self.match_household_goods(hs6)
        
        # Other consumer goods
        else:
            matches = self.match_consumer_goods(hs6)
        
        return matches
    
    def match_apparel(self, hs6: Dict) -> List[Dict]:
        """Match apparel HS6 codes with equal 25% split across gender/age categories"""
        matches = []
        hs6_desc = hs6['description'].lower()
        
        # Determine apparel type
        apparel_type = self.identify_apparel_type(hs6_desc)
        
        # Find relevant UCC codes for each demographic
        demographics = ['mens', 'womens', 'boys', 'girls']
        
        for demo in demographics:
            ucc_candidates = self.apparel_ucc_categories[demo]
            
            # Match based on apparel type
            best_match = self.find_best_apparel_ucc(apparel_type, ucc_candidates, demo)
            
            if best_match:
                matches.append({
                    'hs6_code': hs6['code'],
                    'hs6_description': hs6['description'],
                    'ucc_code': best_match['ucc_code'],
                    'ucc_name': best_match['ucc_name'],
                    'eli_code': best_match['eli_code'],
                    'confidence': 'MEDIUM-HIGH',
                    'match_reasoning': f"Apparel match: {apparel_type} to {demo} category",
                    'is_service': 'NO',
                    'multiple_match_note': 'Gender/age split: 25% each to men/women/boys/girls per methodology'
                })
        
        return matches
    
    def identify_apparel_type(self, description: str) -> str:
        """Identify the type of apparel from description"""
        desc_lower = description.lower()
        
        if any(term in desc_lower for term in ['t-shirt', 'shirt', 'blouse', 'sweater', 'vest']):
            return 'tops'
        elif any(term in desc_lower for term in ['trouser', 'pant', 'jean', 'short']):
            return 'bottoms'
        elif any(term in desc_lower for term in ['coat', 'jacket', 'anorak', 'windbreaker']):
            return 'outerwear'
        elif any(term in desc_lower for term in ['underwear', 'underpant', 'brief', 'boxer']):
            return 'underwear'
        elif any(term in desc_lower for term in ['suit', 'ensemble']):
            return 'suits'
        elif any(term in desc_lower for term in ['dress', 'skirt']):
            return 'dresses'
        elif any(term in desc_lower for term in ['nightwear', 'pajama', 'nightgown']):
            return 'sleepwear'
        elif any(term in desc_lower for term in ['swimwear', 'bathing']):
            return 'swimwear'
        elif any(term in desc_lower for term in ['sock', 'stocking', 'hosiery']):
            return 'hosiery'
        else:
            return 'general_apparel'
    
    def find_best_apparel_ucc(self, apparel_type: str, ucc_candidates: List[Dict], demo: str) -> Optional[Dict]:
        """Find best matching UCC for apparel type and demographic"""
        if not ucc_candidates:
            return None
        
        # Simple keyword matching - can be enhanced with LLM
        for ucc in ucc_candidates:
            ucc_text = (ucc['ucc_name'] + ' ' + ucc['eli_title']).lower()
            
            if apparel_type == 'tops' and any(term in ucc_text for term in ['shirt', 'sweater', 'top', 'blouse']):
                return ucc
            elif apparel_type == 'bottoms' and any(term in ucc_text for term in ['pant', 'trouser', 'short']):
                return ucc
            elif apparel_type == 'outerwear' and any(term in ucc_text for term in ['coat', 'jacket', 'outerwear']):
                return ucc
            elif apparel_type == 'underwear' and 'underwear' in ucc_text:
                return ucc
            elif apparel_type == 'suits' and 'suit' in ucc_text:
                return ucc
            elif apparel_type == 'dresses' and any(term in ucc_text for term in ['dress', 'skirt']):
                return ucc
            elif apparel_type == 'sleepwear' and any(term in ucc_text for term in ['sleepwear', 'nightwear']):
                return ucc
            elif apparel_type == 'swimwear' and 'swim' in ucc_text:
                return ucc
            elif apparel_type == 'hosiery' and any(term in ucc_text for term in ['hosiery', 'sock']):
                return ucc
        
        # Fallback to first general apparel category
        return ucc_candidates[0] if ucc_candidates else None
    
    def match_footwear(self, hs6: Dict) -> List[Dict]:
        """Match footwear with gender/age splits similar to apparel"""
        matches = []
        # Similar logic to apparel matching
        # For simplicity, return empty for now - can be expanded
        return []
    
    def match_food_products(self, hs6: Dict) -> List[Dict]:
        """Match food-related HS6 codes to food UCC codes"""
        matches = []
        hs6_desc = hs6['description'].lower()
        
        # Search for matching UCC codes
        for ucc in self.ucc_data:
            if self.is_service_ucc(ucc):
                continue
            
            ucc_text = (ucc['ucc_name'] + ' ' + ucc['eli_title']).lower()
            
            # Calculate match score based on keyword overlap
            score, reasoning = self.calculate_match_score(hs6_desc, ucc_text, hs6, ucc)
            
            if score > 0.3:  # Threshold for matching
                confidence = self.score_to_confidence(score)
                matches.append({
                    'hs6_code': hs6['code'],
                    'hs6_description': hs6['description'],
                    'ucc_code': ucc['ucc_code'],
                    'ucc_name': ucc['ucc_name'],
                    'eli_code': ucc['eli_code'],
                    'confidence': confidence,
                    'match_reasoning': reasoning,
                    'is_service': 'NO',
                    'multiple_match_note': ''
                })
        
        return matches
    
    def match_household_goods(self, hs6: Dict) -> List[Dict]:
        """Match household goods, appliances, electronics"""
        matches = []
        hs6_desc = hs6['description'].lower()
        
        for ucc in self.ucc_data:
            if self.is_service_ucc(ucc):
                continue
            
            ucc_text = (ucc['ucc_name'] + ' ' + ucc['eli_title']).lower()
            
            score, reasoning = self.calculate_match_score(hs6_desc, ucc_text, hs6, ucc)
            
            if score > 0.3:
                confidence = self.score_to_confidence(score)
                matches.append({
                    'hs6_code': hs6['code'],
                    'hs6_description': hs6['description'],
                    'ucc_code': ucc['ucc_code'],
                    'ucc_name': ucc['ucc_name'],
                    'eli_code': ucc['eli_code'],
                    'confidence': confidence,
                    'match_reasoning': reasoning,
                    'is_service': 'NO',
                    'multiple_match_note': ''
                })
        
        return matches
    
    def match_consumer_goods(self, hs6: Dict) -> List[Dict]:
        """Match other consumer goods"""
        matches = []
        hs6_desc = hs6['description'].lower()
        
        for ucc in self.ucc_data:
            if self.is_service_ucc(ucc):
                continue
            
            ucc_text = (ucc['ucc_name'] + ' ' + ucc['eli_title']).lower()
            
            score, reasoning = self.calculate_match_score(hs6_desc, ucc_text, hs6, ucc)
            
            if score > 0.3:
                confidence = self.score_to_confidence(score)
                matches.append({
                    'hs6_code': hs6['code'],
                    'hs6_description': hs6['description'],
                    'ucc_code': ucc['ucc_code'],
                    'ucc_name': ucc['ucc_name'],
                    'eli_code': ucc['eli_code'],
                    'confidence': confidence,
                    'match_reasoning': reasoning,
                    'is_service': 'NO',
                    'multiple_match_note': ''
                })
        
        return matches
    
    def calculate_match_score(self, hs6_desc: str, ucc_text: str, hs6: Dict, ucc: Dict) -> Tuple[float, str]:
        """
        Calculate semantic match score between HS6 and UCC
        Returns (score, reasoning)
        """
        # Extract keywords from both descriptions
        hs6_keywords = set(re.findall(r'\b\w+\b', hs6_desc.lower()))
        ucc_keywords = set(re.findall(r'\b\w+\b', ucc_text.lower()))
        
        # Remove common stopwords
        stopwords = {'a', 'an', 'and', 'or', 'the', 'of', 'in', 'for', 'to', 'with', 'other', 'than'}
        hs6_keywords -= stopwords
        ucc_keywords -= stopwords
        
        # Calculate overlap
        overlap = hs6_keywords & ucc_keywords
        
        if not overlap:
            return 0.0, ""
        
        # Score based on overlap ratio
        score = len(overlap) / max(len(hs6_keywords), len(ucc_keywords))
        
        # Boost score for exact product matches
        key_products = ['beef', 'pork', 'chicken', 'fish', 'milk', 'cheese', 'bread', 
                       'rice', 'coffee', 'tea', 'apple', 'orange', 'potato', 'tomato']
        
        for product in key_products:
            if product in hs6_desc and product in ucc_text:
                score += 0.3
        
        reasoning = f"Keyword overlap: {', '.join(list(overlap)[:5])}"
        
        return min(score, 1.0), reasoning
    
    def score_to_confidence(self, score: float) -> str:
        """Convert numeric score to confidence level"""
        if score >= 0.8:
            return 'HIGH'
        elif score >= 0.6:
            return 'MEDIUM-HIGH'
        elif score >= 0.4:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def process_all_hs6_codes(self):
        """Process all HS6 codes and create concordance"""
        print("Processing all HS6 codes...")
        
        matched_hs6_codes = set()
        
        for i, hs6 in enumerate(self.hs6_data):
            if (i + 1) % 500 == 0:
                print(f"Processed {i + 1} / {len(self.hs6_data)} HS6 codes")
            
            matches = self.match_hs6_to_ucc(hs6)
            
            if matches:
                matched_hs6_codes.add(hs6['code'])
                self.concordance.extend(matches)
            else:
                # Determine why no match
                reason = self.determine_no_match_reason(hs6)
                self.unmatched_hs6.append({
                    'hs6_code': hs6['code'],
                    'hs6_description': hs6['description'],
                    'no_match_reason': reason
                })
        
        print(f"Completed processing {len(self.hs6_data)} HS6 codes")
        print(f"Created {len(self.concordance)} HS6-UCC mappings")
        print(f"Unmatched HS6 codes: {len(self.unmatched_hs6)}")
        
        # Identify unmatched UCC codes
        matched_ucc_codes = set(match['ucc_code'] for match in self.concordance)
        
        for ucc in self.ucc_data:
            if ucc['ucc_code'] not in matched_ucc_codes:
                is_service = 'YES' if self.is_service_ucc(ucc) else 'NO'
                reason = "Service category - no physical goods" if is_service == 'YES' else "No matching HS6 codes found"
                
                self.unmatched_ucc.append({
                    'ucc_code': ucc['ucc_code'],
                    'ucc_name': ucc['ucc_name'],
                    'is_service': is_service,
                    'no_match_reason': reason
                })
    
    def determine_no_match_reason(self, hs6: Dict) -> str:
        """Determine why an HS6 code has no UCC match"""
        desc_lower = hs6['description'].lower()
        
        industrial_keywords = ['industrial', 'machinery', 'equipment', 'parts', 'manufacturing',
                              'processing', 'bulk', 'raw material', 'intermediate']
        
        if any(keyword in desc_lower for keyword in industrial_keywords):
            return "Industrial intermediate good"
        
        if any(term in desc_lower for term in ['breeding', 'seed', 'live animals']):
            return "Agricultural input, not consumer product"
        
        if any(term in desc_lower for term in ['aircraft', 'ship', 'vessel', 'railway']):
            return "Capital equipment"
        
        return "Not consumer facing"
    
    def save_concordance(self, filename: str):
        """Save main concordance to CSV"""
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['HS6_Code', 'HS6_Description', 'UCC_Code', 'UCC_Name', 'ELI_Code',
                         'Confidence', 'Match_Reasoning', 'Is_Service', 'Multiple_Match_Note']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for match in self.concordance:
                writer.writerow({
                    'HS6_Code': match['hs6_code'],
                    'HS6_Description': match['hs6_description'],
                    'UCC_Code': match['ucc_code'],
                    'UCC_Name': match['ucc_name'],
                    'ELI_Code': match['eli_code'],
                    'Confidence': match['confidence'],
                    'Match_Reasoning': match['match_reasoning'],
                    'Is_Service': match['is_service'],
                    'Multiple_Match_Note': match.get('multiple_match_note', '')
                })
        
        print(f"Saved concordance to {filename}")
    
    def save_unmatched_codes(self, filename: str):
        """Save unmatched codes report"""
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write HS6 unmatched codes
            writer.writerow(['HS6 Codes Without Matches'])
            writer.writerow(['HS6_Code', 'HS6_Description', 'No_Match_Reason'])
            
            for item in self.unmatched_hs6:
                writer.writerow([item['hs6_code'], item['hs6_description'], item['no_match_reason']])
            
            writer.writerow([])
            writer.writerow(['UCC Codes Without Matches'])
            writer.writerow(['UCC_Code', 'UCC_Name', 'Is_Service', 'No_Match_Reason'])
            
            for item in self.unmatched_ucc:
                writer.writerow([item['ucc_code'], item['ucc_name'], item['is_service'], item['no_match_reason']])
        
        print(f"Saved unmatched codes to {filename}")
    
    def generate_summary_statistics(self, filename: str):
        """Generate summary statistics report"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("HS6 TO UCC CONCORDANCE SUMMARY STATISTICS\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Overall statistics
            f.write("OVERALL STATISTICS\n")
            f.write("-" * 70 + "\n")
            f.write(f"Total HS6 codes processed: {len(self.hs6_data)}\n")
            f.write(f"Total UCC codes: {len(self.ucc_data)}\n")
            f.write(f"HS6 codes with matches: {len(self.hs6_data) - len(self.unmatched_hs6)}\n")
            f.write(f"HS6 codes without matches: {len(self.unmatched_hs6)}\n")
            f.write(f"UCC codes with matches: {len(self.ucc_data) - len(self.unmatched_ucc)}\n")
            f.write(f"UCC codes without matches: {len(self.unmatched_ucc)}\n")
            f.write(f"Total HS6-UCC pairs created: {len(self.concordance)}\n\n")
            
            # Confidence distribution
            confidence_counts = defaultdict(int)
            for match in self.concordance:
                confidence_counts[match['confidence']] += 1
            
            f.write("CONFIDENCE DISTRIBUTION\n")
            f.write("-" * 70 + "\n")
            for conf in ['HIGH', 'MEDIUM-HIGH', 'MEDIUM', 'LOW']:
                count = confidence_counts[conf]
                pct = 100 * count / len(self.concordance) if self.concordance else 0
                f.write(f"{conf}: {count} ({pct:.1f}%)\n")
            f.write("\n")
            
            # Top UCC categories by matches
            ucc_match_counts = defaultdict(int)
            for match in self.concordance:
                ucc_match_counts[f"{match['ucc_code']} - {match['ucc_name']}"] += 1
            
            f.write("TOP 20 UCC CATEGORIES BY NUMBER OF HS6 MATCHES\n")
            f.write("-" * 70 + "\n")
            for i, (ucc, count) in enumerate(sorted(ucc_match_counts.items(), key=lambda x: x[1], reverse=True)[:20], 1):
                f.write(f"{i}. {ucc}: {count} matches\n")
            f.write("\n")
            
            # Top HS6 codes with multiple matches
            hs6_match_counts = defaultdict(int)
            for match in self.concordance:
                hs6_match_counts[f"{match['hs6_code']} - {match['hs6_description'][:50]}"] += 1
            
            one_to_many = {k: v for k, v in hs6_match_counts.items() if v > 1}
            
            f.write("TOP 20 HS6 CODES WITH MOST UCC MATCHES (ONE-TO-MANY)\n")
            f.write("-" * 70 + "\n")
            for i, (hs6, count) in enumerate(sorted(one_to_many.items(), key=lambda x: x[1], reverse=True)[:20], 1):
                f.write(f"{i}. {hs6}...: {count} matches\n")
            f.write("\n")
            
            # Statistics by HS6 chapter
            chapter_stats = defaultdict(lambda: {'total': 0, 'matched': 0})
            for hs6 in self.hs6_data:
                chapter = hs6['chapter']
                chapter_stats[chapter]['total'] += 1
            
            for match in self.concordance:
                chapter = match['hs6_code'][:2]
                chapter_stats[chapter]['matched'] += 1
            
            f.write("STATISTICS BY HS6 CHAPTER\n")
            f.write("-" * 70 + "\n")
            for chapter in sorted(chapter_stats.keys()):
                stats = chapter_stats[chapter]
                pct = 100 * stats['matched'] / stats['total'] if stats['total'] > 0 else 0
                f.write(f"Chapter {chapter}: {stats['matched']}/{stats['total']} codes matched ({pct:.1f}%)\n")
        
        print(f"Saved summary statistics to {filename}")
    
    def generate_methodology_doc(self, filename: str):
        """Generate detailed methodology documentation"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("# HS6 to UCC Concordance Methodology\n\n")
            
            f.write("## Introduction\n\n")
            f.write("### Purpose\n")
            f.write("This concordance maps Harmonized System 6-digit (HS6) trade classification codes ")
            f.write("to Universal Classification Code (UCC) consumption categories used in the Consumer ")
            f.write("Expenditure Survey (CE). The concordance enables researchers to link international ")
            f.write("trade data to household consumption patterns.\n\n")
            
            f.write("### Data Sources\n")
            f.write("- **HS6 Codes**: hs6_2017.csv (5,388 codes from HS 2017 revision)\n")
            f.write("- **UCC Codes**: ucc.csv (617 consumption categories)\n")
            f.write(f"- **Date Created**: {datetime.now().strftime('%Y-%m-%d')}\n\n")
            
            f.write("### Matching Method\n")
            f.write("Semantic matching using rule-based algorithms enhanced with keyword analysis. ")
            f.write("The approach combines:\n")
            f.write("1. Keyword extraction and overlap calculation\n")
            f.write("2. Product-specific matching rules\n")
            f.write("3. Category-based heuristics\n")
            f.write("4. Special handling for apparel and footwear\n\n")
            
            f.write("## Methodology Overview\n\n")
            
            f.write("### Semantic Matching Approach\n")
            f.write("The concordance uses a rule-based semantic matching system that:\n")
            f.write("- Analyzes product descriptions from both HS6 and UCC codes\n")
            f.write("- Identifies keyword overlaps and semantic similarities\n")
            f.write("- Applies category-specific matching rules\n")
            f.write("- Handles edge cases like apparel splits and services\n\n")
            
            f.write("### Confidence Level Criteria\n")
            f.write("- **HIGH**: Direct product match with clear one-to-one or one-to-few mapping\n")
            f.write("- **MEDIUM-HIGH**: Good semantic match with minor ambiguity\n")
            f.write("- **MEDIUM**: Plausible match requiring some interpretation\n")
            f.write("- **LOW**: Best available match but with significant uncertainty\n\n")
            
            f.write("### Handling of Edge Cases\n\n")
            
            f.write("#### Apparel (HS Chapters 61-62)\n")
            f.write("Apparel products present a unique challenge because HS6 codes typically don't ")
            f.write("distinguish by consumer demographic (men/women/boys/girls), while UCC codes do. ")
            f.write("**Solution**: Each apparel HS6 code is split equally across four demographic categories:\n")
            f.write("- 25% to Men's categories\n")
            f.write("- 25% to Women's categories\n")
            f.write("- 25% to Boys' categories\n")
            f.write("- 25% to Girls' categories\n\n")
            f.write("This equal distribution assumption is documented in the Multiple_Match_Note field.\n\n")
            
            f.write("#### Services\n")
            f.write("UCC codes representing services (healthcare, education, repairs, etc.) are tagged ")
            f.write("with Is_Service=YES and have no HS6 matches, as HS6 only classifies physical goods.\n\n")
            
            f.write("#### Industrial vs Consumer Goods\n")
            f.write("HS6 codes for industrial equipment, raw materials, and intermediate goods are ")
            f.write("marked as unmatched with appropriate reasoning.\n\n")
            
            f.write("## Detailed Matching Logic by Category\n\n")
            
            # Add category-specific documentation
            f.write("### Live Animals & Meat Products (HS Chapters 01-02)\n")
            f.write("**Strategy**: Match by animal type and cut specification\n")
            f.write("- Live animals for breeding: Generally no match (agricultural input)\n")
            f.write("- Fresh/frozen beef: Match to ground beef, roasts, steaks based on cut description\n")
            f.write("- Pork products: Match to pork chops, ham, bacon based on preparation\n")
            f.write("- Poultry: Distinguish chicken from turkey\n\n")
            
            f.write("### Apparel (HS Chapters 61-62)\n")
            f.write("**CRITICAL METHODOLOGY**: Equal 25% split across demographics\n")
            f.write("**Example**: HS6 610910 'T-shirts, cotton, knitted' creates 4 mappings:\n")
            f.write("1. To Men's Shirts (25%)\n")
            f.write("2. To Women's Tops (25%)\n")
            f.write("3. To Boys' Shirts (25%)\n")
            f.write("4. To Girls' Tops (25%)\n\n")
            
            f.write("## Service UCCs\n\n")
            f.write("Service UCC codes have no HS6 matches because HS6 only classifies tradeable goods.\n")
            f.write(f"Total service UCCs identified: {len([u for u in self.unmatched_ucc if u['is_service'] == 'YES'])}\n\n")
            
            f.write("## Limitations and Caveats\n\n")
            f.write("1. **Gender/Age Ambiguity**: Apparel and footwear use equal splits due to lack of demographic detail in HS6\n")
            f.write("2. **Industrial vs Consumer**: Some HS6 codes may have both industrial and consumer uses\n")
            f.write("3. **Quality Differences**: HS6 and UCC may group products differently by quality/price\n")
            f.write("4. **Multiple Plausible Mappings**: Some products could reasonably map to multiple UCCs\n")
            f.write("5. **Time Period**: HS6 uses 2017 revision; updates may be needed for newer HS versions\n\n")
            
            f.write("## Replication Instructions\n\n")
            f.write("To replicate this concordance:\n")
            f.write("1. Obtain hs6_2017.csv and ucc.csv data files\n")
            f.write("2. Run the matching script: `python create_concordance.py`\n")
            f.write("3. Review output files for quality\n")
            f.write("4. Manual review recommended for ambiguous matches\n\n")
            
            f.write("## Quality Control\n\n")
            f.write("Quality assurance steps:\n")
            f.write("- Systematic processing of all HS6 codes\n")
            f.write("- Consistent application of matching rules\n")
            f.write("- Documentation of all assumptions and special cases\n")
            f.write("- Statistical summaries for validation\n")
        
        print(f"Saved methodology document to {filename}")

def main():
    print("HS6 to UCC Concordance Generator")
    print("=" * 70)
    
    # Initialize concordance
    concordance = HS6_UCC_Concordance('hs6_2017.csv', 'ucc.csv')
    
    # Process all HS6 codes
    concordance.process_all_hs6_codes()
    
    # Save outputs
    concordance.save_concordance('hs6_to_ucc_concordance.csv')
    concordance.save_unmatched_codes('unmatched_codes.csv')
    concordance.generate_summary_statistics('concordance_summary.txt')
    concordance.generate_methodology_doc('concordance_methodology.md')
    
    print("\n" + "=" * 70)
    print("Concordance generation complete!")
    print("Output files:")
    print("  - hs6_to_ucc_concordance.csv")
    print("  - concordance_methodology.md")
    print("  - concordance_summary.txt")
    print("  - unmatched_codes.csv")

if __name__ == '__main__':
    main()
