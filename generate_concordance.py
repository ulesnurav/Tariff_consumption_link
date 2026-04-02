#!/usr/bin/env python3
"""
GPT-Assisted HS10-to-UCC Concordance Mapping Pipeline

Creates a high-precision concordance between US HTS 10-digit codes (HS10) and
Consumer Expenditure Survey Universal Classification Codes (UCC) using a hybrid approach:

  Stage A: Candidate generation via strict lexical/synonym matching (Python)
  Stage B: GPT semantic judging/reranking (requires OPENAI_API_KEY env var)
  Stage C: Hard deterministic post-validation rules (veto power over GPT)

Key quality controls vs. naive lexical matching:
  - Whole-word-only matching (no substring traps: ASSES≠PASSES, LAYER≠PLAYERS)
  - Anchor-noun requirement: generic tokens (FRESH/FROZEN/PROCESSED) alone cannot match
  - Comprehensive goods-only UCC filter (excludes services/finance/housing/utilities)
  - HS chapter compatibility priors restrict candidate pool
  - GPT semantic judging with structured JSON output (if API key present)
  - Precision-first thresholds — prefer fewer, more accurate matches

Usage:
    export OPENAI_API_KEY=sk-...   # optional – enables GPT semantic judging
    python generate_concordance.py

    # With custom file paths or settings:
    python generate_concordance.py --input-hs10 hs10_desc.xlsx \\
        --input-ucc ucc_codes_2017_2019_merged.csv \\
        --min-score 0.5

Author: GPT-Assisted Concordance Pipeline
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# GPT CLIENT (optional)
# ──────────────────────────────────────────────────────────────────────────────

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
GPT_AVAILABLE = bool(OPENAI_API_KEY)

if GPT_AVAILABLE:
    try:
        from openai import OpenAI as _OpenAI
        _gpt_client = _OpenAI(api_key=OPENAI_API_KEY)
        GPT_MODEL = "gpt-4o-mini"
    except ImportError:
        GPT_AVAILABLE = False
        _gpt_client = None
        GPT_MODEL = None

# ──────────────────────────────────────────────────────────────────────────────
# FILE PATHS
# ──────────────────────────────────────────────────────────────────────────────

HS10_FILE = "hs10_desc.xlsx"
UCC_FILE = "ucc_codes_2017_2019_merged.csv"

CONCORDANCE_FILE = "hs10_to_ucc_concordance.csv"
UNMATCHED_HS10_FILE = "unmatched_hs10_codes.csv"
UNMATCHED_UCC_FILE = "unmatched_ucc_codes.csv"
SUMMARY_FILE = "concordance_summary.txt"
SUSPICIOUS_FILE = "suspicious_matches.csv"
DECISIONS_FILE = "match_decisions.jsonl"

# ──────────────────────────────────────────────────────────────────────────────
# GENERIC / STOPWORD TOKENS
# Tokens that are too generic or administrative to anchor a match by themselves.
# A candidate with ONLY these tokens overlapping is rejected.
# ──────────────────────────────────────────────────────────────────────────────

GENERIC_TOKENS: Set[str] = {
    # Processing/state adjectives
    "FRESH", "FROZEN", "PROCESSED", "LIVE", "DRIED", "SMOKED", "SALTED",
    "COOKED", "RAW", "WHOLE", "SLICED", "DICED", "CHOPPED", "GROUND",
    "MIXED", "PREPARED", "REFINED", "CONCENTRATED", "PURIFIED", "DEHYDRATED",
    "CANNED", "PRESERVED", "PACKAGED", "BOTTLED", "CURED", "BONELESS",
    "SHELLED", "HUSKED", "PEELED", "PITTED", "SEEDED", "UNRIPE", "RIPENED",
    # Qualifier adjectives
    "OTHER", "SPECIFIED", "UNSPECIFIED", "MISC", "NEC", "NESOI",
    "MISCELLANEOUS", "GENERAL", "SPECIAL", "VARIOUS", "SIMILAR", "SAME",
    "IMPORTED", "DOMESTIC", "COMMERCIAL", "INDUSTRIAL",
    "EDIBLE", "INEDIBLE", "CERTIFIED", "APPROVED",
    "NEW", "USED", "OLD", "SECOND",
    "WEIGHING", "WEIGHT", "VALUED", "PRICE", "CONTAINING",
    "EXCEPT", "EXCLUDING",
    # Administrative / grammatical
    "NOT", "AND", "OR", "WITH", "FOR", "FROM", "BY", "OF", "THE",
    "A", "AN", "IN", "ON", "AT", "TO", "AS", "IS", "IT",
    "MADE", "USED", "USES", "INCLUDES", "INCLUDING", "EXCEPT",
    "THEIR", "ALL", "ANY", "EACH", "EVERY", "SUCH", "TYPE", "TYPES",
    "KIND", "KINDS", "FORM", "FORMS", "GRADE", "QUALITY", "CLASS",
    "MORE", "LESS", "THAN", "BUT",
    # Very generic nouns that cause cross-category false positives
    "PRODUCTS", "PRODUCT", "ITEMS", "ITEM", "ARTICLES", "ARTICLE",
    "GOODS", "MATERIAL", "MATERIALS", "FOOD", "FOODS",
    "PARTS", "PART", "PREPARATIONS", "PREPARATION",
    "PIECES", "PIECE", "UNITS", "UNIT",
    "WATER",   # "cold-water shrimps" should NOT match "bottled water"
    # Single characters / very short words
    "N", "E", "S", "O",
}

# Tokens too short to be meaningful anchors
SHORT_TOKEN_MIN_LEN = 3

# ──────────────────────────────────────────────────────────────────────────────
# UCC SERVICE / NON-GOODS EXCLUSION PHRASES
# UCC descriptions matching ANY of these phrases are classified as non-goods
# and excluded from the candidate pool.
# ──────────────────────────────────────────────────────────────────────────────

UCC_NONGOOD_PHRASES: List[str] = [
    # Financial
    "INSURANCE", "FINANCE", "INTEREST CHARGE", "LATE CHARGE", "BANK FEE",
    "CREDIT CARD", "LOAN PAYMENT", "PREMIUM", "NONHEALTH INSURANCE",
    # Housing / real estate
    "RENT", "MORTGAGE", "PROPERTY TAX", "GROUND RENT", "HOMEOWNERS",
    "RENTERS", "PROPERTY MANAGEMENT", "LODGING", "HOTEL", "MOTEL",
    # Utilities / communications services
    "ELECTRICITY", "NATURAL GAS", "GAS SERVICE", "WATER SERVICE",
    "SEWER", "TRASH COLLECTION", "TELEPHONE SERVICE", "INTERNET SERVICE",
    "CABLE TV", "SATELLITE TELEVISION", "CABLE TELEVISION",
    # Repair / professional services
    "REPAIR AND REMODELING", "REPAIR SERVICE", "MAINTENANCE SERVICE",
    "INSTALLATION SERVICE", "LABOR COST", "CHILD CARE",
    "DAYCARE", "TUITION", "EDUCATION FEE", "SCHOOL FEE",
    "PET SERVICE", "VETERINARY", "GROOMING SERVICE", "BOARDING",
    # Medical services
    "DOCTOR", "HOSPITAL", "MEDICAL CARE", "DENTAL CARE", "HEALTH CARE",
    "PHYSICIAN", "OPTOMETRIST", "CHIROPRACTOR", "NURSING",
    # Transportation services
    "TOLLS OR ELECTRONIC TOLL", "PARKING FEE", "VEHICLE REGISTRATION",
    "DRIVER LICENSE", "TRANSIT PASS", "MASS TRANSIT",
    # Prepared/restaurant food (not raw ingredients)
    "AT FAST FOOD", "AT RESTAURANTS", "FULL SERVICE RESTAURANT",
    "AT VENDING MACHINE", "TAKE-OUT", "DELIVERY SERVICE",
    "CATERED AFFAIR", "FOOD OR BOARD AT SCHOOL",
    "FOOD ON OUT-OF-TOWN TRIP", "FOOD PREPARED BY CONSUMER UNIT",
    # Alcohol at on-premises locations
    "AT FAST FOOD, TAKE-OUT",
    "AT FULL SERVICE RESTAURANT",
    # Employer / school cafeteria food (not groceries)
    "AT EMPLOYER", "AND SCHOOL CAFETERIA", "SCHOOL CAFETERIA",
    # Miscellaneous services
    "TRIP ABROAD", "TRIP TO FOREIGN COUNTRY",
    "LEGAL FEE", "ACCOUNTING FEE", "MEMBERSHIP FEE",
]

# ──────────────────────────────────────────────────────────────────────────────
# SEMANTIC SYNONYM MAPPINGS
# Maps HS10 terms → equivalent UCC terms (and vice versa via reversal).
# Only high-confidence, domain-specific synonyms — no generic ones.
# ──────────────────────────────────────────────────────────────────────────────

# HS10 keyword → list of equivalent UCC keywords
HS_TO_UCC_SYNONYMS: Dict[str, List[str]] = {
    # ── Meat ─────────────────────────────────────────────────────────────────
    "BOVINE": ["BEEF"],
    "CATTLE": ["BEEF"],
    "SWINE": ["PORK"],
    "PORCINE": ["PORK"],
    "POULTRY": ["CHICKEN", "TURKEY"],
    "OVINE": ["LAMB", "MUTTON"],
    "CAPRINE": ["GOAT"],
    "EQUINE": ["HORSE"],
    "OFFAL": ["ORGAN", "VARIETY MEATS"],
    "SWEETBREAD": ["SWEETBREAD"],  # NOT 'BREAD' — specific term
    "SWEATBREAD": ["SWEETBREAD"],

    # ── Seafood ───────────────────────────────────────────────────────────────
    "CRUSTACEAN": ["SHRIMP", "CRAB", "LOBSTER", "SEAFOOD"],
    "MOLLUSK": ["OYSTER", "CLAM", "SCALLOP", "SEAFOOD"],
    "SHELLFISH": ["SEAFOOD", "SHRIMP", "CRAB", "OYSTER"],
    "FINFISH": ["FISH"],
    "TUNA": ["TUNA", "FISH"],
    "SALMON": ["SALMON", "FISH"],
    "COD": ["FISH"],
    "TILAPIA": ["FISH"],
    "SHRIMP": ["SHRIMP", "SEAFOOD"],
    "LOBSTER": ["LOBSTER", "SEAFOOD"],
    "CRAB": ["CRAB", "SEAFOOD"],
    "OYSTER": ["OYSTER", "SEAFOOD"],
    "CLAM": ["CLAM", "SEAFOOD"],
    "SCALLOP": ["SCALLOP", "SEAFOOD"],
    "HERRING": ["FISH"],
    "MACKEREL": ["FISH"],
    "HALIBUT": ["FISH"],
    "FLOUNDER": ["FISH"],
    "SARDINE": ["FISH"],
    "ANCHOVY": ["FISH"],
    "SQUID": ["SEAFOOD"],
    "OCTOPUS": ["SEAFOOD"],
    "MUSSEL": ["SEAFOOD"],
    "CATFISH": ["FISH"],
    "BASS": ["FISH"],
    "TROUT": ["FISH"],
    "POLLOCK": ["FISH"],
    "HADDOCK": ["FISH"],
    "SNAPPER": ["FISH"],

    # ── Dairy / Eggs ──────────────────────────────────────────────────────────
    "LACTOSE": ["DAIRY", "MILK"],
    "CASEIN": ["DAIRY", "CHEESE"],
    "WHEY": ["DAIRY"],
    "MILK": ["MILK"],
    "BUTTERMILK": ["MILK"],
    "CREAM": ["CREAM"],
    "BUTTER": ["BUTTER"],
    "CHEESE": ["CHEESE"],
    "MOZZARELLA": ["CHEESE"],
    "CHEDDAR": ["CHEESE"],
    "PARMESAN": ["CHEESE"],
    "RICOTTA": ["CHEESE"],
    "YOGURT": ["DAIRY"],
    "EGG": ["EGGS"],
    "EGGS": ["EGGS"],

    # ── Produce ───────────────────────────────────────────────────────────────
    "CITRUS": ["ORANGES", "CITRUS FRUITS"],
    "TUBEROUS": ["POTATOES"],
    "TUBER": ["POTATOES"],
    "SOLANUM": ["POTATOES"],
    "SOLANACEOUS": ["TOMATOES"],
    "LEGUME": ["BEANS", "PEAS"],
    "LEGUMINOUS": ["BEANS", "PEAS"],
    "BRASSICA": ["CABBAGE"],
    "CUCURBIT": ["CUCUMBER"],
    "ALLIUM": ["ONIONS"],
    "CAPSICUM": ["PEPPERS"],
    "CUCUMBERS": ["CUCUMBER"],
    "APPLE": ["APPLES"],
    "APPLES": ["APPLES"],
    "BANANA": ["BANANAS"],
    "BANANAS": ["BANANAS"],
    "ORANGE": ["ORANGES"],
    "ORANGES": ["ORANGES"],
    "GRAPE": ["GRAPES"],
    "GRAPES": ["GRAPES"],
    "STRAWBERRY": ["BERRIES", "STRAWBERRIES"],
    "STRAWBERRIES": ["BERRIES", "STRAWBERRIES"],
    "BERRY": ["BERRIES"],
    "BERRIES": ["BERRIES"],
    "MELON": ["MELONS", "FRUITS"],
    "POTATO": ["POTATOES"],
    "POTATOES": ["POTATOES"],
    "TOMATO": ["TOMATOES"],
    "TOMATOES": ["TOMATOES"],
    "LETTUCE": ["LETTUCE"],
    "CABBAGE": ["CABBAGE"],
    "CARROT": ["CARROTS"],
    "CARROTS": ["CARROTS"],
    "ONION": ["ONIONS"],
    "ONIONS": ["ONIONS"],
    "GARLIC": ["GARLIC"],
    "MUSHROOM": ["MUSHROOMS"],
    "MUSHROOMS": ["MUSHROOMS"],
    "CORN": ["CORN"],
    "SPINACH": ["LEAFY VEGETABLES", "VEGETABLES"],
    "BROCCOLI": ["VEGETABLES"],
    "CAULIFLOWER": ["VEGETABLES"],
    "PINEAPPLE": ["FRUITS"],
    "MANGO": ["FRUITS"],
    "AVOCADO": ["FRUITS"],
    "PEACH": ["FRUITS"],
    "CHERRY": ["FRUITS"],
    "PEAR": ["FRUITS"],
    "PLUM": ["FRUITS"],
    "LEMON": ["CITRUS FRUITS"],
    "LIME": ["CITRUS FRUITS"],
    "GRAPEFRUIT": ["CITRUS FRUITS"],
    "NUT": ["NUTS"],
    "NUTS": ["NUTS"],
    "PEANUT": ["PEANUT BUTTER", "NUTS"],
    "WALNUT": ["NUTS"],
    "ALMOND": ["NUTS"],
    "CASHEW": ["NUTS"],
    "PISTACHIO": ["NUTS"],
    "COCONUT": ["FRUITS"],
    "OLIVE": ["OLIVES"],
    "OLIVES": ["OLIVES"],
    "PEPPER": ["SPICES", "PEPPERS"],
    "SPICE": ["SPICES", "SEASONINGS"],
    "SPICES": ["SPICES", "SEASONINGS"],
    "HERB": ["SPICES", "SEASONINGS"],
    "GINGER": ["SPICES"],
    "CINNAMON": ["SPICES"],
    "VANILLA": ["SPICES"],

    # ── Grains / Milling / Bakery ─────────────────────────────────────────────
    "TRITICUM": ["FLOUR", "CEREALS"],
    "SEMOLINA": ["PASTA", "FLOUR"],
    "DURUM": ["PASTA", "FLOUR"],
    "MAIZE": ["CORN", "CEREAL"],
    "CORNMEAL": ["CORN", "CEREAL"],
    "GROAT": ["CEREAL", "OATS"],
    "WHEAT": ["FLOUR", "BREAD", "CEREALS"],
    "FLOUR": ["FLOUR"],
    "RICE": ["RICE"],
    "OATS": ["CEREAL"],
    "BARLEY": ["CEREAL"],
    "PASTA": ["PASTA"],
    "NOODLE": ["PASTA"],
    "NOODLES": ["PASTA"],
    "BREAD": ["BREAD"],
    "BISCUIT": ["CRACKERS", "BISCUITS"],
    "CRACKER": ["CRACKERS"],
    "COOKIE": ["COOKIES"],
    "CAKE": ["CAKES"],
    "CUPCAKE": ["CAKES"],
    "DONUT": ["SWEETROLLS"],
    "DOUGHNUT": ["SWEETROLLS"],
    "PIE": ["PIES"],
    "PASTRY": ["PIES", "SWEETROLLS"],
    "CEREAL": ["CEREAL"],
    "ROLL": ["ROLLS", "BREAD"],
    "TORTILLA": ["BREAD", "CRACKERS"],
    "BAGEL": ["BREAD"],

    # ── Sugar / Confectionery ─────────────────────────────────────────────────
    "SUGAR": ["SUGAR"],
    "SUCROSE": ["SUGAR"],
    "CHOCOLATE": ["CANDY"],
    "CONFECTIONERY": ["CANDY"],
    "CANDY": ["CANDY"],
    "CHEWING GUM": ["CANDY"],
    "GUM": ["CANDY"],
    "JAM": ["JAMS"],
    "JELLY": ["JAMS"],
    "PRESERVE": ["JAMS"],

    # ── Fats / Oils ───────────────────────────────────────────────────────────
    "VEGETABLE OIL": ["FATS AND OILS"],
    "OLIVE OIL": ["FATS AND OILS"],
    "MARGARINE": ["MARGARINE"],
    "COOKING OIL": ["FATS AND OILS"],
    "SOYBEAN OIL": ["FATS AND OILS"],
    "CANOLA": ["FATS AND OILS"],
    "SHORTENING": ["FATS AND OILS"],
    "MAYONNAISE": ["SALAD DRESSINGS"],
    "SALAD DRESSING": ["SALAD DRESSINGS"],
    "DRESSING": ["SALAD DRESSINGS"],

    # ── Prepared / Processed Food ─────────────────────────────────────────────
    "FRANKFURTER": ["FRANKFURTERS"],
    "HOT DOG": ["FRANKFURTERS"],
    "BOLOGNA": ["BOLOGNA"],
    "SALAMI": ["SALAMI"],
    "LUNCHMEAT": ["LUNCHMEATS"],
    "SAUSAGE": ["SAUSAGE"],
    "BACON": ["BACON"],
    "HAM": ["HAM"],
    "CANNED MEAT": ["CANNED MEAT"],
    "CONDENSED SOUP": ["SOUPS"],
    "CANNED SOUP": ["SOUPS"],
    "SOUP": ["SOUPS"],
    "SAUCE": ["SAUCES"],
    "KETCHUP": ["SAUCES"],
    "MUSTARD": ["SAUCES"],
    "VINEGAR": ["CONDIMENTS"],
    "PICKLE": ["PICKLES"],
    "RELISH": ["RELISHES"],
    "SNACK": ["SNACKS"],
    "POTATO CHIP": ["CHIPS", "SNACKS"],
    "CHIPS": ["SNACKS"],
    "POPCORN": ["SNACKS"],

    # ── Beverages ─────────────────────────────────────────────────────────────
    "MALT BEVERAGE": ["BEER", "ALE"],
    "FERMENTED BEVERAGE": ["WINE", "BEER"],
    "DISTILLED SPIRIT": ["SPIRITS"],
    "ETHYL ALCOHOL": ["SPIRITS"],
    "BEER": ["BEER"],
    "ALE": ["BEER", "ALE"],
    "WINE": ["WINE"],
    "SPIRITS": ["SPIRITS"],
    "WHISKEY": ["SPIRITS"],
    "VODKA": ["SPIRITS"],
    "GIN": ["SPIRITS"],
    "RUM": ["SPIRITS"],
    "BRANDY": ["SPIRITS"],
    "COFFEE": ["COFFEE"],
    "TEA": ["TEA"],
    "JUICE": ["JUICE"],
    "SODA": ["CARBONATED"],
    "COLA": ["COLA"],
    "WATER": ["WATER"],
    "SOFT DRINK": ["CARBONATED"],
    "CARBONATED": ["CARBONATED"],

    # ── Apparel / Textiles ───────────────────────────────────────────────────
    "GARMENT": ["CLOTHING", "APPAREL"],
    "KNITTED APPAREL": ["CLOTHING"],
    "WOVEN APPAREL": ["CLOTHING"],
    "HOSIERY": ["SOCKS", "STOCKINGS"],
    "LINGERIE": ["UNDERWEAR"],
    "NIGHTWEAR": ["SLEEPWEAR"],
    "SWIMWEAR": ["SWIMSUIT"],
    "SHIRT": ["SHIRTS"],
    "BLOUSE": ["BLOUSES", "SHIRTS"],
    "TROUSERS": ["PANTS", "SLACKS"],
    "JEANS": ["JEANS", "PANTS"],
    "SKIRT": ["SKIRTS"],
    "DRESS": ["DRESSES"],
    "SUIT": ["SUITS"],
    "COAT": ["COATS"],
    "JACKET": ["JACKETS", "COATS"],
    "SWEATER": ["SWEATERS"],
    "UNDERWEAR": ["UNDERWEAR"],
    "SOCKS": ["SOCKS"],
    "STOCKINGS": ["STOCKINGS"],
    "GLOVES": ["GLOVES"],
    "SCARF": ["SCARVES"],
    "HAT": ["HATS"],
    "CAP": ["CAPS", "HATS"],
    "BELT": ["BELTS"],
    "TIE": ["TIES"],
    "HANDBAG": ["HANDBAGS"],
    "PURSE": ["HANDBAGS"],
    "WALLET": ["WALLETS"],
    "LUGGAGE": ["LUGGAGE"],
    "SUITCASE": ["LUGGAGE"],
    "BACKPACK": ["BACKPACKS"],

    # ── Furniture / Home ─────────────────────────────────────────────────────
    "SETTEE": ["SOFA", "COUCH"],
    "DIVAN": ["SOFA"],
    "LOUNGE": ["SOFA"],
    "OTTOMAN": ["SOFA"],
    "UPHOLSTERED": ["SOFA", "CHAIR"],
    "BEDSTEAD": ["BED"],
    "MATTRESS": ["MATTRESS", "BED"],
    "BEDDING": ["MATTRESS", "PILLOW", "BLANKET"],
    "WARDROBE": ["CLOSET", "DRESSER"],
    "COOKWARE": ["POTS", "PANS"],
    "TABLEWARE": ["DISHES", "FLATWARE"],
    "CUTLERY": ["FLATWARE", "KNIVES"],
    "SILVERWARE": ["FLATWARE"],
    "SOFA": ["SOFA"],
    "COUCH": ["SOFA"],
    "CHAIR": ["CHAIRS"],
    "TABLE": ["TABLES"],
    "DESK": ["DESKS"],
    "DRESSER": ["DRESSERS"],
    "LAMP": ["LAMPS"],
    "RUG": ["RUGS", "FLOOR COVERING"],
    "CARPET": ["CARPETS", "FLOOR COVERING"],
    "CURTAIN": ["CURTAINS"],
    "PILLOW": ["PILLOWS"],
    "BLANKET": ["BLANKETS"],
    "TOWEL": ["TOWELS"],
    "SHEET": ["SHEETS"],
    "SHELVING": ["SHELVES"],

    # ── Appliances ────────────────────────────────────────────────────────────
    "WASHING MACHINE": ["CLOTHES WASHER"],
    "CLOTHES WASHER": ["CLOTHES WASHER"],
    "DISHWASHER": ["DISHWASHER"],
    "REFRIGERATOR": ["REFRIGERATOR"],
    "FREEZER": ["FREEZER"],
    "COOKING RANGE": ["STOVE"],
    "MICROWAVE OVEN": ["MICROWAVE"],
    "AIR CONDITIONER": ["AIR CONDITIONER"],
    "VACUUM CLEANER": ["VACUUM"],

    # ── Electronics ───────────────────────────────────────────────────────────
    "PHOTOVOLTAIC": ["SOLAR"],
    "TELEVISION": ["TELEVISION", "TV"],
    "TELEVISIONS": ["TELEVISION", "TV"],
    "RADIO": ["RADIO"],
    "TELEPHONE": ["TELEPHONE"],
    "COMPUTER": ["COMPUTER"],
    "PRINTER": ["PRINTER"],
    "CAMERA": ["CAMERA"],
    "HEADPHONE": ["HEADPHONES"],
    "SPEAKER": ["SPEAKERS"],

    # ── Tools / Hardware ─────────────────────────────────────────────────────
    "WRENCH": ["TOOLS"],
    "SCREWDRIVER": ["TOOLS"],
    "HAMMER": ["TOOLS"],
    "SAW": ["TOOLS"],
    "DRILL": ["TOOLS"],
    "PAINT": ["PAINTS"],
    "PAINTBRUSH": ["PAINTING SUPPLIES"],
    "NAIL": ["HARDWARE"],
    "SCREW": ["HARDWARE"],
    "BOLT": ["HARDWARE"],

    # ── Health / Personal Care ────────────────────────────────────────────────
    "MEDICAMENT": ["MEDICINE"],
    "PHARMACEUTICAL": ["MEDICINE"],
    "VITAMIN": ["VITAMINS"],
    "ANALGESIC": ["MEDICINE"],
    "ANTISEPTIC": ["MEDICINE"],
    "TOOTHPASTE": ["DENTAL"],
    "TOOTHBRUSH": ["DENTAL"],
    "SHAMPOO": ["HAIR CARE"],
    "COSMETIC": ["COSMETICS"],
    "PERFUME": ["PERFUME"],
    "COLOGNE": ["COLOGNE"],
    "RAZOR": ["SHAVING"],
    "SOAP": ["SOAP"],
    "DEODORANT": ["DEODORANT"],
    "LOTION": ["LOTION"],
    "SUNSCREEN": ["SUNSCREEN"],
    "DIAPER": ["DIAPERS"],

    # ── Paper / Books / Media ─────────────────────────────────────────────────
    "PERIODICAL": ["MAGAZINES"],
    "NEWSPAPER": ["NEWSPAPERS"],
    "PAPERBACK": ["BOOKS"],
    "MAGAZINE": ["MAGAZINES"],
    "BOOK": ["BOOKS"],

    # ── Toys / Sports ─────────────────────────────────────────────────────────
    "BICYCLE": ["BICYCLES"],
    "FIREARM": ["FIREARMS"],
    "GUN": ["FIREARMS"],
    "TOY": ["TOYS"],
    "DOLL": ["TOYS"],
    "PUZZLE": ["TOYS"],
    "GAME": ["GAMES"],
    "BALL": ["BALLS", "SPORTS EQUIPMENT"],
    "TENNIS": ["SPORTS EQUIPMENT"],
    "GOLF": ["GOLF EQUIPMENT", "SPORTS EQUIPMENT"],
    "FISHING": ["FISHING EQUIPMENT"],
    "CAMPING": ["CAMPING EQUIPMENT"],
    "SKI": ["SPORTS EQUIPMENT"],

    # ── Automotive ────────────────────────────────────────────────────────────
    "AUTOMOBILE": ["VEHICLE"],
    "CAR": ["VEHICLE"],
    "TRUCK": ["TRUCK", "VEHICLE"],
    "MOTORCYCLE": ["MOTORCYCLE"],
    "TIRE": ["TIRES"],
    "TIRES": ["TIRES"],
    "MOTOR OIL": ["MOTOR OIL"],

    # ── Fuel / Energy goods (physical) ───────────────────────────────────────
    "PETROLEUM": ["GASOLINE", "MOTOR OIL"],
    "MOTOR SPIRIT": ["GASOLINE"],
    "GASOLINE": ["GASOLINE"],
    "DIESEL": ["DIESEL FUEL"],
    "LUBRICATING OIL": ["MOTOR OIL"],
}

# Build reverse mapping: UCC keyword → list of HS10 keywords
UCC_TO_HS_SYNONYMS: Dict[str, List[str]] = defaultdict(list)
for hs_kw, ucc_kws in HS_TO_UCC_SYNONYMS.items():
    for ucc_kw in ucc_kws:
        UCC_TO_HS_SYNONYMS[ucc_kw].append(hs_kw)

# ──────────────────────────────────────────────────────────────────────────────
# HS CHAPTER → ALLOWED UCC CODE PREFIXES (first 2 digits of UCC code)
#
# UCC code structure (verified from actual data):
#   01-02: Flour, bread/bakery                 17-18: Non-alc beverages, misc food
#   03-07: Meat (beef/pork/processed/poultry/  19-20: Cafeteria + store alcohol
#          seafood)                            24: Home improvement (paint, etc.)
#   08:    Eggs                                25: Fuel oil
#   09-10: Dairy                               27: Phone/communication
#   11-14: Fruits, vegetables                  28-32: Linens, furniture, appliances,
#   15:    Candy/sugar                                 electronics, furnishings
#   16:    Fats/oils                            33: Cleaning products
#   34+: Services, apparel (36-41), footwear   45-48: Vehicles & automotive
#        (40), accessories (43), vehicles,     54-55: Drugs/medicines
#        fuel, health, media, etc.             59: Newspapers/magazines
#                                              63: Tobacco
#
# HARD REJECT: if a UCC prefix is NOT in the chapter's allowed set (and the set
# is non-empty), the pair receives a final score of 0.0 regardless of token
# overlap.  Empty set means "no restriction".
# ──────────────────────────────────────────────────────────────────────────────

# Verified UCC prefix groups (actual 2-digit prefixes from data):
_FOOD_UCC = {  # All food/beverage UCC prefixes (01-20)
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
}
_APPAREL_UCC = {  # Apparel + footwear + accessories (36-44)
    "36", "37", "38", "39", "40", "41", "42", "43", "44",
}
_HOME_UCC = {  # Home furnishings, appliances, electronics
    "24", "25", "28", "29", "30", "31", "32", "33", "99",
}
_VEHICLE_UCC = {  # Vehicles, fuel, tires, auto services
    "45", "46", "47", "48", "49",
}
_HEALTH_UCC = {  # Drugs, medical, eyeglasses
    "54", "55",
}
_MEDIA_TOBACCO_UCC = {  # Newspapers, magazines, tobacco
    "59", "63",
}
_TOY_RECREATION_UCC = {  # Toys, boats, recreation goods
    "60", "61",
}
_PERSONAL_CARE_UCC = {  # Hair, personal care products
    "64",
}
_ACCESSORY_UCC = {  # Watches, jewelry
    "43",
}

HS_CHAPTER_UCC_ALLOWED: Dict[str, Set[str]] = {}

# ── Food / agricultural chapters (01–24) → FOOD UCC only ─────────────────────
for _ch in range(1, 25):
    HS_CHAPTER_UCC_ALLOWED[str(_ch).zfill(2)] = _FOOD_UCC

# Overrides for specific food chapters with narrower UCC ranges:
HS_CHAPTER_UCC_ALLOWED["02"] = {"03", "04", "05", "06", "07"}        # Meat cuts
HS_CHAPTER_UCC_ALLOWED["03"] = {"05", "06", "07"}                     # Fish/seafood
HS_CHAPTER_UCC_ALLOWED["04"] = {"08", "09", "10"}                     # Dairy/eggs
HS_CHAPTER_UCC_ALLOWED["07"] = {"11", "12", "13", "14", "18"}         # Vegetables
HS_CHAPTER_UCC_ALLOWED["08"] = {"11", "12", "13", "14", "15", "18"}   # Fruits/nuts
HS_CHAPTER_UCC_ALLOWED["09"] = {"17", "18"}                           # Coffee/tea/spices
HS_CHAPTER_UCC_ALLOWED["10"] = {"01", "02", "18"}                     # Cereals
HS_CHAPTER_UCC_ALLOWED["11"] = {"01", "02", "18"}                     # Milling
HS_CHAPTER_UCC_ALLOWED["12"] = {"16", "18"}                           # Oil seeds → fats/oils
HS_CHAPTER_UCC_ALLOWED["15"] = {"16", "18"}                           # Fats/oils
HS_CHAPTER_UCC_ALLOWED["16"] = {"03", "04", "05", "06", "07", "18"}   # Prepared meat/fish
HS_CHAPTER_UCC_ALLOWED["17"] = {"15", "18"}                           # Sugar/confectionery
HS_CHAPTER_UCC_ALLOWED["18"] = {"15", "18"}                           # Cocoa/chocolate
HS_CHAPTER_UCC_ALLOWED["19"] = {"01", "02", "18"}                     # Bakery/pasta
HS_CHAPTER_UCC_ALLOWED["20"] = {"11", "12", "13", "14", "18"}         # Canned veg/fruit
HS_CHAPTER_UCC_ALLOWED["21"] = {"17", "18"}                           # Misc food prep
HS_CHAPTER_UCC_ALLOWED["22"] = {"17", "20"}                           # Beverages
HS_CHAPTER_UCC_ALLOWED["24"] = {"63"}                                 # Tobacco

# ── Chemicals / materials / fuels (25–40) → mostly no restriction ─────────────
# (too varied; rely on synonym matching for precision)
HS_CHAPTER_UCC_ALLOWED["27"] = _VEHICLE_UCC | {"25"}                  # Mineral fuels → gasoline/fuel
HS_CHAPTER_UCC_ALLOWED["30"] = _HEALTH_UCC                            # Pharmaceuticals
HS_CHAPTER_UCC_ALLOWED["33"] = _PERSONAL_CARE_UCC                     # Cosmetics/essential oils
HS_CHAPTER_UCC_ALLOWED["34"] = {"33"}                                 # Soap/detergents

# ── Hides / leather / fur (41–43) → apparel + accessories ────────────────────
for _ch in [41, 42, 43]:
    HS_CHAPTER_UCC_ALLOWED[str(_ch)] = _APPAREL_UCC | _ACCESSORY_UCC

# ── Wood / paper / printed matter (44–49) ─────────────────────────────────────
HS_CHAPTER_UCC_ALLOWED["44"] = {"29", "32", "24"}                     # Wood → furniture/floors
HS_CHAPTER_UCC_ALLOWED["48"] = _MEDIA_TOBACCO_UCC | {"24"}            # Paper → books/media
HS_CHAPTER_UCC_ALLOWED["49"] = _MEDIA_TOBACCO_UCC                     # Printed matter → media

# ── Textiles / apparel / footwear (50–67) → APPAREL UCC only ─────────────────
for _ch in range(50, 68):
    HS_CHAPTER_UCC_ALLOWED[str(_ch).zfill(2)] = _APPAREL_UCC

# Overrides for textile chapters that are broader:
HS_CHAPTER_UCC_ALLOWED["57"] = {"32"}                                 # Carpets → floor coverings
HS_CHAPTER_UCC_ALLOWED["63"] = _APPAREL_UCC | {"32"}                  # Made-up textiles (bedding, curtains)

# ── Stone / glass / ceramics (68–70) → home goods ────────────────────────────
for _ch in [68, 69, 70]:
    HS_CHAPTER_UCC_ALLOWED[str(_ch)] = _HOME_UCC | {"24"}

# ── Jewelry / precious metals (71) ───────────────────────────────────────────
HS_CHAPTER_UCC_ALLOWED["71"] = _ACCESSORY_UCC

# ── Metals (72–83) → home goods / tools (no food/apparel) ────────────────────
# No explicit restriction — too diverse (tools, cookware, hardware)

# ── Machinery / appliances (84–85) → home appliances, electronics ────────────
HS_CHAPTER_UCC_ALLOWED["84"] = _HOME_UCC | _VEHICLE_UCC | {"61"}
HS_CHAPTER_UCC_ALLOWED["85"] = _HOME_UCC | _VEHICLE_UCC | {"27", "61"}

# ── Vehicles (87) → vehicles ─────────────────────────────────────────────────
HS_CHAPTER_UCC_ALLOWED["86"] = {"__none__"}   # Railways: no consumer goods application
HS_CHAPTER_UCC_ALLOWED["87"] = _VEHICLE_UCC

# ── Aircraft, Ships (88-89) → vehicles ───────────────────────────────────────
HS_CHAPTER_UCC_ALLOWED["88"] = {"45", "46"}    # Aircraft → aircraft/vehicle UCC only
HS_CHAPTER_UCC_ALLOWED["89"] = {"60"}          # Ships/boats → boats UCC only
HS_CHAPTER_UCC_ALLOWED["90"] = _HEALTH_UCC | {"31", "61"}             # Optics, instruments
HS_CHAPTER_UCC_ALLOWED["91"] = _ACCESSORY_UCC                         # Clocks/watches
HS_CHAPTER_UCC_ALLOWED["92"] = {"67"}                                 # Musical instruments
HS_CHAPTER_UCC_ALLOWED["93"] = {"60", "61"}                           # Arms → sporting/recreation

# ── Furniture (94) → furniture/home goods ────────────────────────────────────
HS_CHAPTER_UCC_ALLOWED["94"] = {"29", "30", "32", "24", "99"}

# ── Toys / sports equipment (95) ─────────────────────────────────────────────
HS_CHAPTER_UCC_ALLOWED["95"] = _TOY_RECREATION_UCC | {"48"}

# ── Misc manufactured articles (96) ──────────────────────────────────────────
HS_CHAPTER_UCC_ALLOWED["96"] = _PERSONAL_CARE_UCC | {"43", "64", "65"}


# ──────────────────────────────────────────────────────────────────────────────
# SUBSTRING TRAP DETECTION
# Reject matches where one token is a true substring of the other token.
# This prevents: ASSES↔PASSES, ASSES↔EYEGLASSES, IMMEDIATE↔MEDIA, LAYER↔PLAYERS
# ──────────────────────────────────────────────────────────────────────────────

def is_substring_trap(tok_a: str, tok_b: str) -> bool:
    """Return True if tok_a is a substring of tok_b or vice versa (not equal)."""
    if tok_a == tok_b:
        return False
    return tok_a in tok_b or tok_b in tok_a


# ──────────────────────────────────────────────────────────────────────────────
# TEXT PROCESSING UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Upper-case, strip, collapse whitespace."""
    if not text or (isinstance(text, float)):
        return ""
    return re.sub(r"\s+", " ", str(text).upper().strip())


def tokenize(text: str) -> List[str]:
    """
    Split text into whole-word tokens (alpha sequences only, length >= SHORT_TOKEN_MIN_LEN).
    Returns upper-cased tokens.
    """
    words = re.findall(r"[A-Za-z]+", text)
    return [w.upper() for w in words if len(w) >= SHORT_TOKEN_MIN_LEN]


def anchor_tokens(tokens: List[str]) -> List[str]:
    """Return tokens that are NOT in GENERIC_TOKENS — these are the 'anchor nouns'."""
    return [t for t in tokens if t not in GENERIC_TOKENS]


def expand_synonyms(tokens: List[str], direction: str = "hs_to_ucc") -> Set[str]:
    """
    Expand a list of tokens with their synonyms.
    direction: 'hs_to_ucc' or 'ucc_to_hs'
    Returns the original tokens PLUS synonym expansions as a set.
    """
    result = set(tokens)
    mapping = HS_TO_UCC_SYNONYMS if direction == "hs_to_ucc" else UCC_TO_HS_SYNONYMS
    for tok in tokens:
        if tok in mapping:
            for syn in mapping[tok]:
                result.update(tokenize(syn))
    # Also check multi-word phrases
    text = " ".join(tokens)
    for phrase, syns in mapping.items():
        phrase_tokens = tokenize(phrase)
        if len(phrase_tokens) > 1 and all(pt in tokens for pt in phrase_tokens):
            for syn in syns:
                result.update(tokenize(syn))
    return result


# ──────────────────────────────────────────────────────────────────────────────
# UCC GOODS CLASSIFICATION
# ──────────────────────────────────────────────────────────────────────────────

def classify_ucc(desc: str) -> str:
    """
    Classify a UCC description as GOODS or one of the non-goods categories.
    Returns 'GOODS' or one of: SERVICE, HOUSING, FINANCIAL, PREPARED_FOOD,
    UTILITY, TRANSPORT_SERVICE.
    """
    d = normalize(desc)

    # Check exclusion phrases in order of specificity
    # Financial
    if any(p in d for p in [
        "INSURANCE", "FINANCE, LATE", "INTEREST CHARGE", "LATE CHARGE",
        "BANK FEE", "LOAN PAYMENT", "NONHEALTH INSURANCE", "HEALTH INSURANCE",
        "LIFE INSURANCE", "VEHICLE INSURANCE", "HOMEOWNER INSURANCE",
    ]):
        return "FINANCIAL"

    # Housing
    if any(p in d for p in [
        "RENT, ", "MORTGAGE", "PROPERTY TAX", "GROUND RENT", "LODGING",
        "HOTEL LODGING", "PROPERTY MANAGEMENT", "HOMEOWNERS ASSOCIATION",
        "RENTERS INSURANCE",
    ]):
        return "HOUSING"
    if d.startswith("RENT ") or d == "RENT":
        return "HOUSING"

    # Utilities / communication services
    if any(p in d for p in [
        "ELECTRICITY", "NATURAL GAS", "GAS SERVICE", "WATER AND SEWER",
        "WATER SERVICE", "TRASH COLLECTION", "GARBAGE COLLECTION",
        "TELEPHONE SERVICE", "CELLULAR SERVICE", "INTERNET SERVICE",
        "CABLE TV", "CABLE TELEVISION", "SATELLITE TV", "SATELLITE TELEVISION",
        "CABLE AND SATELLITE",
    ]):
        return "UTILITY"

    # Prepared / restaurant food (away-from-home eating)
    if any(p in d for p in [
        "AT FAST FOOD", "AT RESTAURANTS", "FULL SERVICE RESTAURANT",
        "AT VENDING MACHINE", "CATERED AFFAIR", "FOOD OR BOARD AT SCHOOL",
        "FOOD ON OUT-OF-TOWN TRIP", "FOOD PREPARED BY CONSUMER UNIT ON OUT-OF-TOWN",
        "AT VENDING MACHINES AND MOBILE",
    ]):
        return "PREPARED_FOOD"

    # Transportation services
    if any(p in d for p in [
        "TOLLS OR ELECTRONIC TOLL", "PARKING FEE", "VEHICLE REGISTRATION FEE",
        "DRIVER LICENSE FEE", "MASS TRANSIT", "PUBLIC TRANSPORTATION",
    ]):
        return "TRANSPORT_SERVICE"

    # Repair / professional services (but not "REPAIR PARTS" or "REPAIR KITS" which are goods)
    repair_svc_phrases = [
        "REPAIR AND REMODELING SERVICE", "REPAIR SERVICE", "MAINTENANCE SERVICE",
        "INSTALLATION SERVICE", "CHILD CARE", "DAYCARE",
        "TUITION", "EDUCATION FEE", "SCHOOL FEE",
        "PET SERVICE", "VETERINARY SERVICE", "GROOMING SERVICE",
        "DOCTOR VISIT", "HOSPITAL VISIT", "MEDICAL CARE SERVICE",
        "DENTAL CARE SERVICE", "PHYSICIAN FEE", "OPTOMETRIST FEE",
    ]
    if any(p in d for p in repair_svc_phrases):
        return "SERVICE"

    # Explicit SERVICE flag in description
    if "SERVICE" in d and not any(x in d for x in [
        "SERVICE WARE", "SERVICE SET", "SERVICEABLE", "SELF-SERVICE",
        "FOOD SERVICE EQUIPMENT", "FOOD SERVICE GOODS",
    ]):
        # Only flag if "SERVICE" is a standalone concept
        service_pattern = r"\bSERVICE[S]?\b"
        if re.search(service_pattern, d):
            # But allow: FULL SERVICE (restaurant was caught above), REPAIR PARTS, etc.
            # Check if it's a repair/professional service type
            if any(x in d for x in ["REPAIR", "PROFESSIONAL", "CONTRACT", "SUBSCRIPTION"]):
                return "SERVICE"

    return "GOODS"


# ──────────────────────────────────────────────────────────────────────────────
# CANDIDATE SCORING (DETERMINISTIC)
# ──────────────────────────────────────────────────────────────────────────────

def score_candidate(
    hs10_tokens: List[str],
    ucc_tokens: List[str],
    hs10_anchors: List[str],
    ucc_anchors: List[str],
    hs10_expanded: Set[str],
    ucc_expanded: Set[str],
    hs_chapter: str,
    ucc_prefix: str,
) -> Tuple[float, str]:
    """
    Score a (HS10, UCC) candidate pair using coverage-based scoring.

    Coverage-based approach (asymmetric):
      UCC coverage  = fraction of UCC anchor tokens explained by HS10 expanded tokens
      HS10 coverage = fraction of HS10 anchor tokens captured by UCC expanded tokens

    This avoids Jaccard's penalty for HS10 codes with many specific tokens while
    still requiring the UCC description to be semantically relevant.

    Returns (score, reason_str) where score is in [0, 1].
    Returns (0.0, reason) if the pair should be hard-rejected.
    """
    # ── Hard rejection: no anchor tokens at all ────────────────────────────
    if not ucc_anchors:
        return 0.0, "REJECT: UCC has no anchor (specific) tokens"
    if not hs10_anchors:
        return 0.0, "REJECT: HS10 has no anchor (specific) tokens"

    # ── UCC coverage (primary): how many UCC anchors are covered by HS10 ──
    ucc_anchor_set = set(ucc_anchors)
    ucc_covered = ucc_anchor_set & hs10_expanded
    ucc_coverage = len(ucc_covered) / len(ucc_anchor_set)

    # Require at least partial UCC coverage (any UCC anchor matched)
    if ucc_coverage == 0:
        return 0.0, "REJECT: no UCC anchor tokens covered by HS10 description"

    # ── HS10 coverage (secondary): how many HS10 anchors are captured ─────
    hs10_anchor_set = set(hs10_anchors)
    hs10_covered = hs10_anchor_set & ucc_expanded
    hs10_coverage = len(hs10_covered) / len(hs10_anchor_set)

    # ── Chapter compatibility: HARD REJECT for clear domain mismatches ────────
    chapter_allowed = HS_CHAPTER_UCC_ALLOWED.get(hs_chapter, set())
    if chapter_allowed and ucc_prefix not in chapter_allowed:
        return 0.0, (
            f"REJECT: HS chapter {hs_chapter} incompatible with UCC prefix {ucc_prefix} "
            f"(allowed: {sorted(chapter_allowed)[:5]}...)"
        )

    # ── Compute combined score ─────────────────────────────────────────────────
    # 65% weight on UCC coverage (most important: does the UCC fit the HS10?)
    # 35% weight on HS10 coverage (secondary: does the HS10 relate to the UCC?)
    raw_score = 0.65 * ucc_coverage + 0.35 * hs10_coverage

    # Bonus for exact non-generic bigram match in original tokens
    hs_bigrams = _bigrams(hs10_tokens)
    ucc_bigrams = _bigrams(ucc_tokens)
    non_generic_bigrams = {
        bg for bg in (hs_bigrams & ucc_bigrams)
        if not any(t in GENERIC_TOKENS for t in bg)
    }
    if non_generic_bigrams:
        raw_score = min(raw_score + 0.10 * len(non_generic_bigrams), 1.0)

    score = max(min(raw_score, 1.0), 0.0)

    # Build human-readable reason
    reason_parts = []
    if ucc_covered:
        reason_parts.append(f"anchor tokens: {', '.join(sorted(ucc_covered))}")
    if hs10_covered and hs10_covered != ucc_covered:
        reason_parts.append(f"HS10 tokens matched: {', '.join(sorted(hs10_covered))}")
    if non_generic_bigrams:
        reason_parts.append(f"bigram matches: {', '.join(' '.join(bg) for bg in non_generic_bigrams)}")

    return score, "; ".join(reason_parts) if reason_parts else "token overlap"


def _bigrams(tokens: List[str]) -> Set[Tuple[str, str]]:
    """Return set of consecutive bigrams from a token list."""
    return {(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)}


def confidence_label(score: float) -> str:
    """Convert numeric score to a confidence label.

    With coverage-based scoring:
    - HIGH (≥0.70): both UCC and HS10 well-covered, or perfect UCC coverage
    - MEDIUM-HIGH (≥0.55): good UCC coverage, some HS10 coverage
    - MEDIUM (≥0.40): partial UCC coverage, minimum threshold
    - LOW: below acceptance threshold (should not appear in accepted output)
    """
    if score >= 0.70:
        return "HIGH"
    if score >= 0.55:
        return "MEDIUM-HIGH"
    if score >= 0.40:
        return "MEDIUM"
    return "LOW"


# ──────────────────────────────────────────────────────────────────────────────
# GPT JUDGING
# ──────────────────────────────────────────────────────────────────────────────

GPT_SYSTEM_PROMPT = """You are an expert in US trade classification (HTS) and
consumer expenditure surveys (CEX). Your task is to judge whether an HS10 product
description corresponds to a specific UCC (Universal Classification Code) consumer
expenditure category.

Rules you MUST follow:
1. UCC categories must represent physical consumer goods that households purchase.
   REJECT matches where the UCC is a service, financial product, utility, housing,
   or restaurant/prepared food category.
2. Matches must be based on SPECIFIC product semantics — not just generic modifiers.
   Words like FRESH, FROZEN, PROCESSED, DRIED, LIVE, OTHER, SPECIFIED alone are
   NOT sufficient to accept a match.
3. Whole-word matching only — substring coincidences are invalid
   (e.g., ASSES≠PASSES, LAYER≠PLAYERS, IMMEDIATE≠MEDIA, SPECIFIED≠UNSPECIFIED).
4. If the HS10 product is an industrial input, raw material, or non-consumer good,
   reject all candidates.
5. Prefer precision: when in doubt, REJECT rather than accept.

Return a JSON object with this exact schema:
{
  "matches": [
    {
      "ucc_code": "<6-digit UCC code>",
      "accept": <true or false>,
      "confidence": "<high|medium|low>",
      "reason": "<brief explanation, max 100 chars>"
    }
  ]
}"""

GPT_BATCH_SIZE = 8   # HS10 codes per GPT request
GPT_MAX_CANDIDATES = 5  # Top candidates per HS10 to send to GPT
GPT_RATE_LIMIT_SLEEP = 1.0  # seconds between batches


def gpt_judge_batch(
    hs10_descs: List[Tuple[str, str]],  # list of (hs10_code, hs10_desc)
    candidates_per_hs10: List[List[Dict]],  # list of candidate lists
) -> List[Optional[List[Dict]]]:
    """
    Send a batch of HS10→UCC candidate judgments to GPT.
    Returns a list of judgment lists (one per HS10), or None on error.
    """
    if not GPT_AVAILABLE:
        return [None] * len(hs10_descs)

    user_content_parts = []
    for i, ((code, desc), candidates) in enumerate(zip(hs10_descs, candidates_per_hs10)):
        cands_text = "\n".join(
            f"  - UCC {c['ucc_code']}: {c['ucc_description']}" for c in candidates
        )
        user_content_parts.append(
            f"[{i+1}] HS10 {code}: {desc}\nCandidates:\n{cands_text}"
        )

    user_content = (
        "Judge each HS10 code against its candidate UCC codes.\n\n"
        + "\n\n".join(user_content_parts)
        + "\n\nReturn a single JSON object with a 'matches' array containing one entry "
        "per candidate (in the order listed above, flattened across all HS10 codes)."
    )

    try:
        response = _gpt_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": GPT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        all_matches = data.get("matches", [])

        # Re-associate matches with HS10 codes
        idx = 0
        results = []
        for candidates in candidates_per_hs10:
            chunk = all_matches[idx: idx + len(candidates)]
            results.append(chunk)
            idx += len(candidates)
        return results
    except Exception as exc:
        print(f"  [GPT] Batch error: {exc}", file=sys.stderr)
        return [None] * len(hs10_descs)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN CONCORDANCE GENERATION
# ──────────────────────────────────────────────────────────────────────────────

def build_concordance(
    hs10_df: pd.DataFrame,
    ucc_df: pd.DataFrame,
    min_score: float = 0.40,
    max_candidates: int = 10,
) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    """
    Build the concordance.

    Returns:
        matches        – list of accepted match dicts (→ concordance CSV)
        unmatched_hs10 – list of unmatched HS10 dicts
        unmatched_ucc  – list of unmatched UCC dicts
        decisions      – list of all decision dicts (→ JSONL audit log)
    """

    # ── 1. Prepare UCC data ───────────────────────────────────────────────────
    ucc_df = ucc_df.copy()
    ucc_df["_desc_norm"] = ucc_df["description"].apply(normalize)
    ucc_df["_category"] = ucc_df["_desc_norm"].apply(classify_ucc)
    ucc_df["_tokens"] = ucc_df["_desc_norm"].apply(tokenize)
    ucc_df["_anchors"] = ucc_df["_tokens"].apply(anchor_tokens)
    ucc_df["_expanded"] = ucc_df["_tokens"].apply(
        lambda t: expand_synonyms(t, direction="ucc_to_hs")
    )
    ucc_df["_prefix"] = ucc_df["ucc_code"].apply(lambda c: str(c).zfill(6)[:2])

    goods_ucc = ucc_df[ucc_df["_category"] == "GOODS"].copy()
    print(f"  UCC goods pool: {len(goods_ucc)} / {len(ucc_df)} codes after service filter")

    # Index goods UCC by anchor token for fast lookup
    ucc_anchor_index: Dict[str, List[int]] = defaultdict(list)
    for row_idx, row in goods_ucc.iterrows():
        for tok in row["_anchors"]:
            ucc_anchor_index[tok].append(row_idx)
        for tok in row["_expanded"] - GENERIC_TOKENS:
            if tok not in row["_anchors"]:
                ucc_anchor_index[tok].append(row_idx)

    # ── 2. Prepare HS10 data ──────────────────────────────────────────────────
    hs10_df = hs10_df.copy()
    hs_code_col = "HS10 Code" if "HS10 Code" in hs10_df.columns else hs10_df.columns[0]
    hs_desc_col = "HS10 Description" if "HS10 Description" in hs10_df.columns else hs10_df.columns[1]

    hs10_df["_code"] = hs10_df[hs_code_col].apply(lambda c: str(c).zfill(10))
    hs10_df["_desc_norm"] = hs10_df[hs_desc_col].apply(normalize)
    hs10_df["_tokens"] = hs10_df["_desc_norm"].apply(tokenize)
    hs10_df["_anchors"] = hs10_df["_tokens"].apply(anchor_tokens)
    hs10_df["_expanded"] = hs10_df["_tokens"].apply(
        lambda t: expand_synonyms(t, direction="hs_to_ucc")
    )
    hs10_df["_chapter"] = hs10_df["_code"].apply(lambda c: c[:2])

    # ── 3. Main matching loop ─────────────────────────────────────────────────
    matches: List[Dict] = []
    unmatched_hs10: List[Dict] = []
    decisions: List[Dict] = []

    matched_ucc_codes: Set[str] = set()

    total = len(hs10_df)
    print(f"  Processing {total} HS10 codes...")

    # GPT batching state
    gpt_batch_hs_codes: List[Tuple[str, str]] = []
    gpt_batch_candidates: List[List[Dict]] = []
    gpt_batch_hs_rows: List[pd.Series] = []

    def flush_gpt_batch():
        """Process one GPT batch and record results."""
        if not gpt_batch_hs_codes:
            return

        judgments = gpt_judge_batch(gpt_batch_hs_codes, gpt_batch_candidates)
        for (hs_code, _hs_desc), candidates, judgment_list, hs_row in zip(
            gpt_batch_hs_codes, gpt_batch_candidates, judgments, gpt_batch_hs_rows
        ):
            _process_hs10_with_gpt_results(
                hs_row, candidates, judgment_list,
                matches, unmatched_hs10, decisions, matched_ucc_codes,
            )
        gpt_batch_hs_codes.clear()
        gpt_batch_candidates.clear()
        gpt_batch_hs_rows.clear()

    for i, (_, hs_row) in enumerate(hs10_df.iterrows()):
        if i % 2000 == 0:
            print(f"    {i}/{total} ({i*100//total}%)", flush=True)

        hs_code = hs_row["_code"]
        hs_desc = hs_row["_desc_norm"]
        hs_anchors = hs_row["_anchors"]
        hs_expanded = hs_row["_expanded"]
        hs_chapter = hs_row["_chapter"]

        if not hs_anchors:
            unmatched_hs10.append({
                "hs10_code": hs_code,
                "hs10_description": hs_desc,
                "reason": "No anchor (specific) tokens in description",
            })
            decisions.append({
                "hs10_code": hs_code, "hs10_description": hs_desc,
                "candidates": [], "accepted": False,
                "rejection_reason": "no anchor tokens",
            })
            continue

        # Candidate retrieval: find UCC rows with at least one matching anchor token
        candidate_indices: Set[int] = set()
        for tok in hs_anchors:
            candidate_indices.update(ucc_anchor_index.get(tok, []))
        for tok in hs_expanded - GENERIC_TOKENS:
            candidate_indices.update(ucc_anchor_index.get(tok, []))

        if not candidate_indices:
            unmatched_hs10.append({
                "hs10_code": hs_code,
                "hs10_description": hs_desc,
                "reason": "No UCC goods code shares anchor tokens",
            })
            decisions.append({
                "hs10_code": hs_code, "hs10_description": hs_desc,
                "candidates": [], "accepted": False,
                "rejection_reason": "no matching UCC anchor tokens",
            })
            continue

        # Score all candidates
        scored: List[Tuple[float, pd.Series, str]] = []
        for idx in candidate_indices:
            ucc_row = goods_ucc.loc[idx]
            score, reason = score_candidate(
                hs_row["_tokens"], ucc_row["_tokens"],
                hs_anchors, ucc_row["_anchors"],
                hs_expanded, ucc_row["_expanded"],
                hs_chapter, ucc_row["_prefix"],
            )
            if score > 0:
                scored.append((score, ucc_row, reason))

        # Sort by score descending, take top-N
        scored.sort(key=lambda x: -x[0])
        top_candidates = scored[:max_candidates]

        if not top_candidates:
            unmatched_hs10.append({
                "hs10_code": hs_code,
                "hs10_description": hs_desc,
                "reason": "No candidates passed scoring threshold",
            })
            decisions.append({
                "hs10_code": hs_code, "hs10_description": hs_desc,
                "candidates": [], "accepted": False,
                "rejection_reason": "all candidates failed scoring",
            })
            continue

        # Build candidate dicts for GPT / output
        candidate_dicts = [
            {
                "ucc_code": ucc_row["ucc_code"],
                "ucc_description": ucc_row["description"],
                "det_score": score,
                "det_reason": reason,
            }
            for score, ucc_row, reason in top_candidates
        ]

        if GPT_AVAILABLE:
            # Queue for GPT batch
            gpt_batch_hs_codes.append((hs_code, hs_desc))
            gpt_batch_candidates.append(candidate_dicts[:GPT_MAX_CANDIDATES])
            gpt_batch_hs_rows.append(hs_row)

            if len(gpt_batch_hs_codes) >= GPT_BATCH_SIZE:
                flush_gpt_batch()
                time.sleep(GPT_RATE_LIMIT_SLEEP)
        else:
            # Fallback: use deterministic scores with stricter threshold
            _process_hs10_deterministic(
                hs_row, candidate_dicts, min_score,
                matches, unmatched_hs10, decisions, matched_ucc_codes,
            )

    # Flush remaining GPT batch
    if GPT_AVAILABLE:
        flush_gpt_batch()

    # ── 4. Build unmatched UCC list ───────────────────────────────────────────
    unmatched_ucc: List[Dict] = []
    for _, ucc_row in ucc_df.iterrows():
        code = ucc_row["ucc_code"]
        category = ucc_row["_category"]
        if code not in matched_ucc_codes:
            if category == "GOODS":
                reason = "OTHER - No matching HS10 goods category"
            else:
                reason = category
            unmatched_ucc.append({
                "ucc_code": code,
                "ucc_description": ucc_row["description"],
                "category": category,
                "reason": reason,
            })

    return matches, unmatched_hs10, unmatched_ucc, decisions


def _process_hs10_deterministic(
    hs_row: pd.Series,
    candidate_dicts: List[Dict],
    min_score: float,
    matches: List[Dict],
    unmatched_hs10: List[Dict],
    decisions: List[Dict],
    matched_ucc_codes: Set[str],
) -> None:
    """Apply deterministic threshold to candidate list and record results."""
    hs_code = hs_row["_code"]
    hs_desc = hs_row["_desc_norm"]
    hs_desc_orig = hs_row.get("HS10 Description", hs_desc)

    accepted_any = False
    decision_candidates = []

    for cand in candidate_dicts:
        score = cand["det_score"]
        accept = score >= min_score
        conf = confidence_label(score)

        decision_candidates.append({
            "ucc_code": cand["ucc_code"],
            "ucc_description": cand["ucc_description"],
            "det_score": round(score, 4),
            "accept": accept,
            "confidence": conf,
            "reason": cand["det_reason"],
            "method": "deterministic",
        })

        if accept:
            matches.append({
                "hs10_code": hs_code,
                "hs10_description": hs_desc_orig if hs_desc_orig != hs_desc else hs_desc,
                "ucc_code": cand["ucc_code"],
                "ucc_description": cand["ucc_description"],
                "confidence_level": conf,
                "match_score": round(score, 4),
                "match_reasoning": cand["det_reason"],
                "match_method": "deterministic",
                "demographic_split": 1.0,
            })
            matched_ucc_codes.add(cand["ucc_code"])
            accepted_any = True

    if not accepted_any:
        best = candidate_dicts[0] if candidate_dicts else {}
        unmatched_hs10.append({
            "hs10_code": hs_code,
            "hs10_description": hs_desc,
            "reason": (
                f"Best candidate score {best.get('det_score', 0):.2f} below threshold {min_score}"
                if best else "No candidates passed scoring"
            ),
        })

    decisions.append({
        "hs10_code": hs_code,
        "hs10_description": hs_desc,
        "candidates": decision_candidates,
        "accepted": accepted_any,
        "rejection_reason": None if accepted_any else "score below threshold",
    })


def _process_hs10_with_gpt_results(
    hs_row: pd.Series,
    candidate_dicts: List[Dict],
    judgment_list: Optional[List[Dict]],
    matches: List[Dict],
    unmatched_hs10: List[Dict],
    decisions: List[Dict],
    matched_ucc_codes: Set[str],
) -> None:
    """Integrate GPT judgments with deterministic candidates."""
    hs_code = hs_row["_code"]
    hs_desc = hs_row["_desc_norm"]
    hs_desc_orig = hs_row.get("HS10 Description", hs_desc)

    if judgment_list is None:
        # GPT failed — fall back to deterministic
        _process_hs10_deterministic(
            hs_row, candidate_dicts, 0.40,
            matches, unmatched_hs10, decisions, matched_ucc_codes,
        )
        return

    # Build lookup from GPT results
    gpt_by_code: Dict[str, Dict] = {j["ucc_code"]: j for j in judgment_list if "ucc_code" in j}

    accepted_any = False
    decision_candidates = []

    for cand in candidate_dicts:
        gpt = gpt_by_code.get(cand["ucc_code"], {})
        gpt_accept = gpt.get("accept", False)
        gpt_conf = gpt.get("confidence", "low")
        gpt_reason = gpt.get("reason", "")

        # Hard veto: even if GPT accepts, deterministic score must be > 0
        # (prevents GPT hallucination on clearly wrong pairs)
        det_score = cand["det_score"]
        if gpt_accept and det_score <= 0:
            gpt_accept = False
            gpt_reason = "VETOED: deterministic score is 0 (hard block)"

        conf = gpt_conf.upper() if gpt_accept else "REJECTED"
        reason = gpt_reason if gpt_reason else cand["det_reason"]

        decision_candidates.append({
            "ucc_code": cand["ucc_code"],
            "ucc_description": cand["ucc_description"],
            "det_score": round(det_score, 4),
            "accept": gpt_accept,
            "confidence": conf if gpt_accept else "REJECTED",
            "reason": reason,
            "method": "gpt",
        })

        if gpt_accept:
            conf_label = {
                "high": "HIGH", "medium": "MEDIUM-HIGH", "low": "MEDIUM"
            }.get(gpt_conf.lower(), "MEDIUM")

            matches.append({
                "hs10_code": hs_code,
                "hs10_description": hs_desc_orig if hs_desc_orig != hs_desc else hs_desc,
                "ucc_code": cand["ucc_code"],
                "ucc_description": cand["ucc_description"],
                "confidence_level": conf_label,
                "match_score": round(det_score, 4),
                "match_reasoning": reason,
                "match_method": "gpt",
                "demographic_split": 1.0,
            })
            matched_ucc_codes.add(cand["ucc_code"])
            accepted_any = True

    if not accepted_any:
        unmatched_hs10.append({
            "hs10_code": hs_code,
            "hs10_description": hs_desc,
            "reason": "GPT rejected all candidates",
        })

    decisions.append({
        "hs10_code": hs_code,
        "hs10_description": hs_desc,
        "candidates": decision_candidates,
        "accepted": accepted_any,
        "rejection_reason": None if accepted_any else "GPT rejected all candidates",
    })


# ──────────────────────────────────────────────────────────────────────────────
# SUSPICIOUS MATCH DETECTION
# ──────────────────────────────────────────────────────────────────────────────

SUSPICIOUS_PATTERNS = [
    # Substring traps in reasoning (use word boundaries to avoid false flags)
    (r"\bASSES\b.*\bPASS\b|\bPASS\b.*\bASSES\b", "substring trap: ASSES≈PASSES"),
    (r"\bASSES\b.*\bGLASS\b|\bGLASS\b.*\bASSES\b", "substring trap: ASSES≈EYEGLASSES"),
    (r"\bIMMEDIATE\b.*\bMEDIA\b|\bMEDIA\b.*\bIMMEDIATE\b", "substring trap: IMMEDIATE≈MEDIA"),
    # LAYER≈PLAYERS: only flag when HS10 has standalone "LAYER" and UCC has "PLAYER"
    # (not when both sides say "PLAYER/PLAYERS" — that's a valid media device match)
    (r"\bLAYER\b(?!S).*\bPLAYER\b|\bPLAYER\b.*\bLAYER\b(?!S)", "substring trap: LAYER≈PLAYERS"),
    (r"\bSPECIFIED\b.*\bUNSPECIFIED\b|\bUNSPECIFIED\b.*\bSPECIFIED\b",
     "substring trap: SPECIFIED≈UNSPECIFIED"),
    (r"\bBREAD\b.*\bSWEAT\b|\bSWEAT\b.*\bBREAD\b", "likely false match: SWEETBREADS vs BREAD"),
]


def flag_suspicious(matches: List[Dict]) -> List[Dict]:
    """Flag matches that look suspicious for manual review."""
    suspicious = []
    for m in matches:
        hs = m.get("hs10_description", "")
        ucc = m.get("ucc_description", "")
        combined = f"{hs} {ucc}"
        for pattern, label in SUSPICIOUS_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                suspicious.append({**m, "suspicious_reason": label})
                break
        else:
            # Also flag if confidence is LOW
            if m.get("confidence_level") == "LOW":
                suspicious.append({**m, "suspicious_reason": "LOW confidence — review recommended"})
    return suspicious


# ──────────────────────────────────────────────────────────────────────────────
# SUMMARY GENERATION
# ──────────────────────────────────────────────────────────────────────────────

def generate_summary(
    hs10_df: pd.DataFrame,
    ucc_df: pd.DataFrame,
    matches: List[Dict],
    unmatched_hs10: List[Dict],
    unmatched_ucc: List[Dict],
    gpt_used: bool,
) -> str:
    total_hs10 = len(hs10_df)
    total_ucc = len(ucc_df)
    n_pairs = len(matches)
    n_matched_hs10 = len({m["hs10_code"] for m in matches})
    n_unmatched_hs10 = len(unmatched_hs10)
    n_matched_ucc = len({m["ucc_code"] for m in matches})
    n_unmatched_ucc = len(unmatched_ucc)

    conf_counts: Dict[str, int] = defaultdict(int)
    for m in matches:
        conf_counts[m.get("confidence_level", "UNKNOWN")] += 1

    ucc_reason_counts: Dict[str, int] = defaultdict(int)
    for u in unmatched_ucc:
        ucc_reason_counts[u["reason"]] += 1

    lines = [
        "HS10-to-UCC CONCORDANCE MAPPING SUMMARY",
        "=" * 40,
        "",
        "PIPELINE",
        "-" * 20,
        f"Matching method:             {'GPT-assisted (Stage A+B+C)' if gpt_used else 'Deterministic fallback (Stage A+C; GPT unavailable)'}",
        f"Generated:                   {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "INPUT DATA",
        "-" * 20,
        f"Total HS10 codes:            {total_hs10:,}",
        f"Total UCC codes:             {total_ucc:,}",
        "",
        "MATCHING RESULTS",
        "-" * 20,
        f"HS10 codes matched:          {n_matched_hs10:,} ({n_matched_hs10*100//total_hs10}%)",
        f"HS10 codes unmatched:        {n_unmatched_hs10:,} ({n_unmatched_hs10*100//total_hs10}%)",
        "",
        f"UCC codes matched:           {n_matched_ucc:,} ({n_matched_ucc*100//total_ucc}%)",
        f"UCC codes unmatched:         {n_unmatched_ucc:,} ({n_unmatched_ucc*100//total_ucc}%)",
        "",
        f"Total HS10-UCC pairs:        {n_pairs:,}",
        "",
        "CONFIDENCE LEVEL DISTRIBUTION",
        "-" * 20,
    ]
    for level in ["HIGH", "MEDIUM-HIGH", "MEDIUM", "LOW"]:
        lines.append(f"{level:<20}         {conf_counts[level]:,} pairs")

    lines += [
        "",
        "UNMATCHED UCC CODES BY CATEGORY",
        "-" * 20,
    ]
    for reason, count in sorted(ucc_reason_counts.items()):
        lines.append(f"{reason:<40} {count} codes")

    if not gpt_used:
        lines += [
            "",
            "NOTE: GPT semantic judging was SKIPPED (OPENAI_API_KEY not set).",
            "To enable GPT-assisted matching, set the OPENAI_API_KEY environment",
            "variable and re-run: python generate_concordance.py",
            "GPT mode improves precision for edge cases and borderline matches.",
        ]

    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input-hs10", default=HS10_FILE, help="HS10 input Excel file")
    p.add_argument("--input-ucc", default=UCC_FILE, help="UCC input CSV file")
    p.add_argument(
        "--min-score", type=float, default=0.40,
        help="Minimum deterministic score for acceptance (default: 0.40)",
    )
    p.add_argument(
        "--max-candidates", type=int, default=10,
        help="Max UCC candidates per HS10 to score (default: 10)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print("\n" + "=" * 70)
    print("GPT-ASSISTED HS10-to-UCC CONCORDANCE PIPELINE")
    print("=" * 70)
    print(f"GPT judging:   {'ENABLED (model: ' + GPT_MODEL + ')' if GPT_AVAILABLE else 'DISABLED (set OPENAI_API_KEY to enable)'}")
    print(f"Min score:     {args.min_score}")
    print(f"Max candidates:{args.max_candidates}")
    print()

    # ── Load data ─────────────────────────────────────────────────────────────
    print("Step 1: Loading input data...")
    hs10_df = pd.read_excel(args.input_hs10, dtype=str)
    ucc_df = pd.read_csv(args.input_ucc, dtype=str)
    print(f"  Loaded {len(hs10_df):,} HS10 codes from {args.input_hs10}")
    print(f"  Loaded {len(ucc_df):,} UCC codes from {args.input_ucc}")
    print()

    # ── Build concordance ─────────────────────────────────────────────────────
    print("Step 2: Building concordance...")
    matches, unmatched_hs10, unmatched_ucc, decisions = build_concordance(
        hs10_df, ucc_df,
        min_score=args.min_score,
        max_candidates=args.max_candidates,
    )
    print()
    print(f"  Accepted matches: {len(matches):,}")
    print(f"  Unmatched HS10:   {len(unmatched_hs10):,}")
    print(f"  Unmatched UCC:    {len(unmatched_ucc):,}")
    print()

    # ── Flag suspicious matches ───────────────────────────────────────────────
    print("Step 3: Flagging suspicious matches...")
    suspicious = flag_suspicious(matches)
    print(f"  Suspicious matches flagged: {len(suspicious):,}")
    print()

    # ── Save outputs ──────────────────────────────────────────────────────────
    print("Step 4: Saving output files...")

    concordance_df = pd.DataFrame(matches)
    concordance_df.to_csv(CONCORDANCE_FILE, index=False)
    print(f"  Saved {CONCORDANCE_FILE} ({len(matches):,} rows)")

    unmatched_hs10_df = pd.DataFrame(unmatched_hs10)
    unmatched_hs10_df.to_csv(UNMATCHED_HS10_FILE, index=False)
    print(f"  Saved {UNMATCHED_HS10_FILE} ({len(unmatched_hs10):,} rows)")

    unmatched_ucc_df = pd.DataFrame(unmatched_ucc)
    unmatched_ucc_df.to_csv(UNMATCHED_UCC_FILE, index=False)
    print(f"  Saved {UNMATCHED_UCC_FILE} ({len(unmatched_ucc):,} rows)")

    summary = generate_summary(hs10_df, ucc_df, matches, unmatched_hs10, unmatched_ucc, GPT_AVAILABLE)
    with open(SUMMARY_FILE, "w") as f:
        f.write(summary)
    print(f"  Saved {SUMMARY_FILE}")

    suspicious_df = pd.DataFrame(suspicious) if suspicious else pd.DataFrame(
        columns=list(matches[0].keys()) + ["suspicious_reason"] if matches else ["suspicious_reason"]
    )
    suspicious_df.to_csv(SUSPICIOUS_FILE, index=False)
    print(f"  Saved {SUSPICIOUS_FILE} ({len(suspicious):,} rows)")

    with open(DECISIONS_FILE, "w") as f:
        for dec in decisions:
            f.write(json.dumps(dec) + "\n")
    print(f"  Saved {DECISIONS_FILE} ({len(decisions):,} entries)")

    print()
    print("=" * 70)
    print("CONCORDANCE GENERATION COMPLETE")
    print("=" * 70)
    print()
    print(summary)


if __name__ == "__main__":
    main()
