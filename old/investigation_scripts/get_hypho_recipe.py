import csv
from pathlib import Path

TSV_PATH = "/home/mark/Downloads/BER-CMM-data-for-AI-normalized - media_ingredients.tsv"


def get_hypho_recipe() -> None:
    print("--- Hypho Medium Ingredients (from TSV) ---")
    with Path(TSV_PATH).open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # Check name if ID is missing
            name = row.get("media_name", "").lower()
            if "hypho" in name:
                print(f"- {row['ingredient_name']}: {row['concentration']} {row['unit']}")


if __name__ == "__main__":
    get_hypho_recipe()
