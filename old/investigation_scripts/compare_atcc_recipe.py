import csv
import re
from pymongo import MongoClient

# Config
TSV_PATH = "/home/mark/Downloads/BER-CMM-data-for-AI-normalized - media_ingredients.tsv"
MONGO_URI = "mongodb://localhost:27017/"

def normalize_name(name):
    return name.lower().strip().replace(" ", "")

def check_atcc_ingredients():
    print("--- Parsing TSV for ATCC:1306 ---")
    
    tsv_ingredients = []
    
    with open(TSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row.get('media_id') == 'ATCC:1306':
                tsv_ingredients.append({
                    "name": row['ingredient_name'],
                    "amount": row['concentration'],
                    "unit": row['unit'],
                    "chebi": row['ontology_id']
                })
    
    print(f"Found {len(tsv_ingredients)} ingredients in TSV:")
    for ing in tsv_ingredients:
        print(f"  - {ing['name']}: {ing['amount']} {ing['unit']} ({ing['chebi']})")

    print("\n--- Fetching MediaDive NMS (ID 632) ---")
    client = MongoClient(MONGO_URI)
    db = client["mediadive"]
    
    # Fetch NMS (ID 632)
    nms = db.media_details.find_one({"_id": 632})
    if not nms:
        print("Error: NMS (632) not found in DB.")
        return

    db_ingredients = []
    solutions = nms.get('solutions', [])
    for sol in solutions:
        for comp in sol.get('recipe', []):
            if 'compound' in comp:
                db_ingredients.append({
                    "name": comp['compound'],
                    "amount": comp.get('amount', '?'),
                    "unit": comp.get('unit', '?')
                })

    print(f"Found {len(db_ingredients)} ingredients in MediaDive:")
    for ing in db_ingredients:
        print(f"  - {ing['name']}: {ing['amount']} {ing['unit']}")

    # Simple Intersection Check
    print("\n--- Comparison ---")
    tsv_names = {normalize_name(i['name']) for i in tsv_ingredients}
    db_names = {normalize_name(i['name']) for i in db_ingredients}
    
    common = tsv_names.intersection(db_names)
    print(f"Common Ingredients: {len(common)}")
    print(f"Unique to TSV: {tsv_names - db_names}")
    print(f"Unique to MediaDive: {db_names - tsv_names}")

if __name__ == "__main__":
    check_atcc_ingredients()
