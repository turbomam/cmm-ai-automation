import csv
from pathlib import Path

from pymongo import MongoClient

# Config
TSV_PATH = "/home/mark/Downloads/BER-CMM-data-for-AI-normalized - media_ingredients.tsv"
MONGO_URI = "mongodb://localhost:27017/"


def check_dsmz88() -> None:
    print("--- Parsing TSV for DSMZ:88 ---")

    tsv_ingredients = []
    with Path(TSV_PATH).open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row.get("media_id") == "DSMZ:88":
                tsv_ingredients.append(
                    {"name": row["ingredient_name"], "amount": row["concentration"], "unit": row["unit"]}
                )

    if not tsv_ingredients:
        print("No ingredients found for DSMZ:88 in TSV.")
    else:
        for ing in tsv_ingredients:
            print(f"  - {ing['name']}: {ing['amount']} {ing['unit']}")

    print("\n--- Fetching MediaDive DSMZ 88 (ID 88) ---")
    client = MongoClient(MONGO_URI)
    db = client["mediadive"]

    # DSMZ 88 should have ID 88
    dsmz88 = db.media_details.find_one({"_id": 88})

    if dsmz88:
        print(f"Name: {dsmz88.get('medium', {}).get('name')}")
        solutions = dsmz88.get("solutions", [])
        for sol in solutions:
            for comp in sol.get("recipe", []):
                if "compound" in comp:
                    print(f"  - {comp['compound']}: {comp.get('amount')} {comp.get('unit')}")
    else:
        print("DSMZ 88 not found in MediaDive DB.")


if __name__ == "__main__":
    check_dsmz88()
