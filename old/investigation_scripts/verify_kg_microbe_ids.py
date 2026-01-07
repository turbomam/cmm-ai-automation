import csv
import re
from pathlib import Path

from pymongo import MongoClient

# Config
TSV_PATH = "output/kgx/cmm_grounded_media_hybrid.tsv"
MONGO_URI = "mongodb://localhost:27017/"


def check_ids() -> None:
    print(f"Checking IDs from {TSV_PATH}...")

    # Connect to Mongo
    client = MongoClient(MONGO_URI)
    db_media = client["mediadive"]
    col_media = db_media["media_details"]

    # Collect IDs to check
    ids_to_check = set()
    with Path(TSV_PATH).open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            val = row.get("kg_microbe_nodes", "").strip()
            if val:
                # Split by semicolon
                parts = re.split(r"[;,]", val)
                for part in parts:
                    clean = part.strip()
                    if clean:
                        ids_to_check.add(clean)

    print(f"Found {len(ids_to_check)} unique IDs to verify.")

    # Verify each ID
    found = 0
    missing = 0

    print("\n--- Verification Results ---")
    for full_id in sorted(ids_to_check):
        # Extract ID part (e.g., medium:J562 -> J562)
        clean_id = full_id.replace("medium:", "").strip()

        # 1. Try exact _id match (string)
        doc = col_media.find_one({"_id": clean_id})

        # 2. Try exact _id match (int)
        if not doc and clean_id.isdigit():
            doc = col_media.find_one({"_id": int(clean_id)})

        # 3. Try medium.id match (legacy/alt ID)
        if not doc:
            doc = col_media.find_one({"medium.id": clean_id})

        if doc:
            found += 1
            name = doc.get("medium", {}).get("name", "Unknown")
            print(f"✅ {full_id} -> Found in MediaDive: '{name}' (ID: {doc['_id']})")
        else:
            missing += 1
            print(f"❌ {full_id} -> NOT FOUND in MediaDive")

    print(f"\nSummary: {found} found, {missing} missing.")


if __name__ == "__main__":
    check_ids()
