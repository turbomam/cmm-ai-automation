import csv
from pathlib import Path

TSV_PATH = "/home/mark/Downloads/BER-CMM-data-for-AI-normalized - media_ingredients.tsv"


def check_succinate() -> None:
    print("Checking for Succinate in Hypho/MP...")

    with Path(TSV_PATH).open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            media_id = row.get("media_id", "")
            name = row.get("ingredient_name", "").lower()

            if ("hypho" in media_id.lower() or "mp" in media_id.lower()) and "succinate" in name:
                print(f"FOUND SUCCINATE: {media_id} contains {name} ({row['concentration']} {row['unit']})")


if __name__ == "__main__":
    check_succinate()
