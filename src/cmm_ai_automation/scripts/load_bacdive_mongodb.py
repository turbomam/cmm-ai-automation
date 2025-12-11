#!/usr/bin/env python3
"""Download BacDive strain data and load into MongoDB.

Uses a hybrid approach:
1. SPARQL endpoint to efficiently discover all valid BacDive IDs
2. Official bacdive Python package to fetch the complete native JSON documents

This avoids scanning 200k sequential IDs when only ~97k strains exist,
while maintaining compatibility with KG-Microbe's expected document format.

Usage:
    uv run python -m cmm_ai_automation.scripts.load_bacdive_mongodb

Options:
    --batch-size N       IDs per API batch (default: 100)
    --env-file PATH      Path to .env file with credentials
    --dry-run            Test without downloading
    --limit N            Limit number of strains to fetch (for testing)
"""

import argparse
import logging
import os
import time
from typing import Any

import bacdive  # type: ignore[import-untyped]
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from tqdm import tqdm  # type: ignore[import-untyped]

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SPARQL_ENDPOINT = "https://sparql.dsmz.de/api/bacdive"
MONGODB_URI = "mongodb://localhost:27017"
DATABASE_NAME = "bacdive"
COLLECTION_NAME = "strains"

# Rate limiting - be polite
REQUEST_DELAY = 0.1  # seconds between requests

# SPARQL prefixes
SPARQL_PREFIXES = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX d3o: <https://purl.dsmz.de/schema/>
PREFIX bd: <https://purl.dsmz.de/bacdive/>
"""


def sparql_query(query: str, max_retries: int = 3) -> list[dict[str, Any]]:
    """Execute a SPARQL query and return results.

    Args:
        query: SPARQL query string
        max_retries: Number of retries on failure

    Returns:
        List of result bindings as dicts
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=300,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            results: dict[str, Any] = data.get("results", {})
            bindings: list[dict[str, Any]] = results.get("bindings", [])
            return bindings
        except (requests.RequestException, ValueError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"SPARQL query failed (attempt {attempt + 1}): {e}")
                time.sleep(2**attempt)
            else:
                logger.error(f"SPARQL query failed after {max_retries} attempts: {e}")
                return []
    return []


def get_all_bacdive_ids() -> list[int]:
    """Get all valid BacDive IDs via SPARQL.

    Returns:
        Sorted list of all BacDive strain IDs
    """
    logger.info("Fetching all BacDive IDs via SPARQL...")

    query = f"""{SPARQL_PREFIXES}
SELECT ?bacdiveId
WHERE {{
  ?strain a d3o:Strain ;
          d3o:hasBacDiveID ?bacdiveId .
}}
ORDER BY ?bacdiveId
"""
    results = sparql_query(query)

    ids = []
    for row in results:
        try:
            ids.append(int(row["bacdiveId"]["value"]))
        except (KeyError, ValueError):
            continue

    logger.info(f"Found {len(ids):,} valid BacDive IDs")
    return sorted(ids)


def load_bacdive_to_mongodb(
    client: bacdive.BacdiveClient,
    collection: Collection[dict[str, Any]],
    bacdive_ids: list[int],
    batch_size: int,
) -> tuple[int, int]:
    """Load BacDive entries into MongoDB using official bacdive package.

    Args:
        client: Authenticated BacDive client
        collection: MongoDB collection
        bacdive_ids: List of BacDive IDs to fetch
        batch_size: Number of IDs per batch

    Returns:
        Tuple of (total_fetched, total_stored)
    """
    total_fetched = 0
    total_stored = 0

    logger.info(f"Fetching {len(bacdive_ids):,} strains in batches of {batch_size}")

    with tqdm(total=len(bacdive_ids), desc="Fetching strains") as pbar:
        for i in range(0, len(bacdive_ids), batch_size):
            batch_ids = bacdive_ids[i : i + batch_size]

            try:
                # Build semicolon-separated ID string for API
                id_str = ";".join(str(bid) for bid in batch_ids)

                # Use do_api_call to fetch batch
                result = client.do_api_call(f"fetch/{id_str}")

                if not result or "results" not in result:
                    logger.warning(f"Empty result for batch {batch_ids[0]}-{batch_ids[-1]}")
                    pbar.update(len(batch_ids))
                    continue

                # Results is a dict keyed by ID
                results_dict = result["results"]

                for key, strain_data in results_dict.items():
                    if not isinstance(strain_data, dict):
                        continue

                    # Get BacDive ID from General section or use key
                    bacdive_id = None
                    if "General" in strain_data:
                        bacdive_id = strain_data["General"].get("BacDive-ID")
                    if bacdive_id is None:
                        # Fall back to key (which is the ID)
                        try:
                            bacdive_id = int(key)
                        except (ValueError, TypeError):
                            continue

                    total_fetched += 1

                    # Add bacdive_id at top level for compatibility
                    strain_data["bacdive_id"] = bacdive_id
                    # Use bacdive_id as MongoDB _id
                    strain_data["_id"] = bacdive_id

                    try:
                        collection.replace_one(
                            {"_id": bacdive_id},
                            strain_data,
                            upsert=True,
                        )
                        total_stored += 1
                    except Exception as e:
                        logger.warning(f"Failed to store BacDive {bacdive_id}: {e}")

            except Exception as e:
                logger.warning(f"Batch fetch failed for IDs {batch_ids[0]}-{batch_ids[-1]}: {e}")

            pbar.update(len(batch_ids))
            time.sleep(REQUEST_DELAY)

    return total_fetched, total_stored


def main() -> None:
    """Download BacDive strain data and load into MongoDB."""
    parser = argparse.ArgumentParser(description="Download BacDive strain data into MongoDB")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="IDs per batch (default: 100)",
    )
    parser.add_argument(
        "--env-file",
        help="Path to .env file with credentials",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test without downloading",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of strains to fetch (for testing)",
    )
    args = parser.parse_args()

    # Load environment
    if args.env_file:
        load_dotenv(args.env_file)
    else:
        load_dotenv()

    # Get credentials
    email = os.environ.get("BACDIVE_EMAIL")
    password = os.environ.get("BACDIVE_PASSWORD")

    if not email or not password:
        logger.error("BACDIVE_EMAIL and BACDIVE_PASSWORD must be set in environment or .env file")
        return

    # Step 1: Get all valid IDs via SPARQL
    all_ids = get_all_bacdive_ids()
    if not all_ids:
        logger.error("Failed to get BacDive IDs from SPARQL")
        return

    # Apply limit if specified
    if args.limit:
        all_ids = all_ids[: args.limit]
        logger.info(f"Limited to {len(all_ids)} strains")

    if args.dry_run:
        logger.info(f"[DRY RUN] Would fetch {len(all_ids):,} strains")
        logger.info(f"  ID range: {min(all_ids)} to {max(all_ids)}")
        return

    # Step 2: Authenticate with BacDive using official package
    logger.info("Authenticating with BacDive...")
    try:
        bacdive_client = bacdive.BacdiveClient(email, password)
        logger.info("BacDive authentication successful")
    except Exception as e:
        logger.error(f"BacDive authentication failed: {e}")
        return

    # Step 3: Connect to MongoDB
    logger.info("Connecting to MongoDB...")
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(MONGODB_URI)
    db = mongo_client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]

    # Create indexes
    collection.create_index("bacdive_id")
    collection.create_index("General.species")
    collection.create_index("Name and taxonomic classification.species")

    # Get current count
    existing_count = collection.count_documents({})
    logger.info(f"Existing strains in MongoDB: {existing_count}")

    # Step 4: Fetch and store via official bacdive package
    total_fetched, total_stored = load_bacdive_to_mongodb(
        client=bacdive_client,
        collection=collection,
        bacdive_ids=all_ids,
        batch_size=args.batch_size,
    )

    # Summary
    final_count = collection.count_documents({})
    logger.info("\n=== Summary ===")
    logger.info(f"  IDs from SPARQL: {len(all_ids):,}")
    logger.info(f"  Total fetched: {total_fetched:,}")
    logger.info(f"  Total stored: {total_stored:,}")
    logger.info(f"  Final count in MongoDB: {final_count:,}")

    mongo_client.close()
    logger.info("Done!")


if __name__ == "__main__":
    main()
