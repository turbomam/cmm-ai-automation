import csv
import re
from pathlib import Path

from pymongo import MongoClient

# Config
INPUT_TSV = "output/kgx/cmm_grounded_media_hybrid.tsv"
OUTPUT_TSV = "output/kgx/media_matches_audit.tsv"
MONGO_URI = "mongodb://localhost:27017/"


def audit_matches() -> None:
    print(f"Auditing matches from {INPUT_TSV}...")

    # Connect to Mongo
    client = MongoClient(MONGO_URI)
    db_media = client["mediadive"]
    col_media = db_media["media_details"]

    rows_out = []

    with Path(INPUT_TSV).open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            input_name = row.get("media_name", "").strip()

            # 1. Check kg_microbe_nodes (matches provided in input)
            kg_nodes = row.get("kg_microbe_nodes", "").strip()
            if kg_nodes:
                parts = re.split(r"[;,]", kg_nodes)
                for part in parts:
                    clean_id = part.strip().replace("medium:", "")
                    if not clean_id:
                        continue

                    # Look up name in DB
                    match_name = "UNKNOWN"
                    doc = col_media.find_one({"_id": clean_id})
                    if not doc and clean_id.isdigit():
                        doc = col_media.find_one({"_id": int(clean_id)})
                    if not doc:
                        doc = col_media.find_one({"medium.id": clean_id})

                    if doc:
                        match_name = doc.get("medium", {}).get("name", "Unknown")

                    rows_out.append(
                        {
                            "input_media_name": input_name,
                            "match_id": part.strip(),
                            "match_name_in_db": match_name,
                            "source": "kg_microbe_nodes",
                        }
                    )

            # 2. Check grounded_id (match found by our pipeline)
            grounded_id = row.get("grounded_id", "").strip()
            grounded_source = row.get("grounded_source", "").strip()

            # Skip local/registry matches for this audit (we want to check DB links)
            if grounded_source in ["mediadive", "togomedium"]:
                rows_out.append(
                    {
                        "input_media_name": input_name,
                        "match_id": grounded_id,
                        "match_name_in_db": row.get("grounded_name", ""),
                        "source": f"pipeline_{grounded_source}",
                    }
                )

    # Write output
    if rows_out:
        with Path(OUTPUT_TSV).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows_out[0].keys(), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows_out)

    print(f"Wrote {len(rows_out)} rows to {OUTPUT_TSV}")


if __name__ == "__main__":
    audit_matches()
