#!/usr/bin/env python3
"""Index TogoMedium data into ChromaDB for fuzzy/semantic search.

Downloads media data from TogoMedium API and indexes into ChromaDB.
TogoMedium is a comprehensive database of microbial culture media from DBCLS.

Usage:
    uv run python -m cmm_ai_automation.scripts.index_togomedium_chromadb
    uv run python -m cmm_ai_automation.scripts.index_togomedium_chromadb --test
"""

import json
import logging
import time
from pathlib import Path

import chromadb
import click
import requests
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CHROMA_PATH = "data/chroma_togomedium"
DATA_CACHE_PATH = "data/togomedium_cache"
TOGOMEDIUM_API = "https://togomedium.org/sparqlist/api"

# Test cases for media grounding
TEST_CASES = [
    ("LB medium", ["luria", "bertani", "lb"], "LB medium search"),
    ("Luria-Bertani", ["lb", "luria"], "Luria-Bertani search"),
    ("R2A", ["r2a", "reasoner"], "R2A medium search"),
    ("minimal medium", ["minimal", "defined"], "Minimal medium search"),
    ("PYG", ["pyg", "peptone", "yeast", "glucose"], "PYG medium search"),
    ("nutrient broth", ["nutrient", "broth"], "Nutrient broth search"),
    ("marine agar", ["marine"], "Marine agar search"),
    ("tryptic soy", ["tryptic", "soy", "tsa", "tsb"], "TSA/TSB search"),
]


def fetch_all_media(cache_dir: Path, force_refresh: bool = False) -> list[dict]:
    """Fetch all media from TogoMedium API.

    Uses pagination and caches results locally.
    """
    cache_file = cache_dir / "media_list.json"

    if cache_file.exists() and not force_refresh:
        logger.info(f"Loading cached media from {cache_file}")
        with cache_file.open() as f:
            return json.load(f)

    logger.info("Fetching media list from TogoMedium API...")
    all_media = []
    offset = 0
    limit = 100
    total = None

    while True:
        url = f"{TOGOMEDIUM_API}/list_media?limit={limit}&offset={offset}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"API error at offset {offset}: {e}")
            break

        if total is None:
            total = data.get("total", 0)
            logger.info(f"Total media in TogoMedium: {total}")

        contents = data.get("contents", [])
        if not contents:
            break

        all_media.extend(contents)
        logger.info(f"Fetched {len(all_media)}/{total} media...")

        offset += limit
        if offset >= total:
            break

        # Rate limiting
        time.sleep(0.1)

    # Cache results
    cache_dir.mkdir(parents=True, exist_ok=True)
    with cache_file.open("w") as f:
        json.dump(all_media, f, indent=2)
    logger.info(f"Cached {len(all_media)} media to {cache_file}")

    return all_media


def flatten_medium_doc(doc: dict) -> tuple[str, dict]:
    """Flatten medium document for ChromaDB indexing.

    Returns (searchable_text, metadata).
    """
    parts = []
    metadata = {}

    # Medium ID
    media_id_info = doc.get("media_id", {})
    media_id = media_id_info.get("label", "") if isinstance(media_id_info, dict) else str(media_id_info)

    if media_id:
        metadata["togomedium_id"] = media_id
        parts.append(f"Medium ID: {media_id}")

    # Medium name
    name = doc.get("label", "")
    if name:
        parts.append(f"Medium: {name}")
        metadata["name"] = name

    # Original media ID (e.g., JCM_M443)
    original_id = doc.get("original_media_id", "")
    if original_id:
        parts.append(f"Original ID: {original_id}")
        metadata["original_id"] = original_id

        # Extract source (JCM, NBRC, etc.)
        if "_" in original_id:
            source = original_id.split("_")[0]
            metadata["source"] = source
            parts.append(f"Source: {source}")

    searchable_text = "\n".join(parts)
    return searchable_text, metadata


def index_media(media_list: list[dict], chroma_client, clear: bool = False) -> int:
    """Index media into ChromaDB."""
    logger.info("\n" + "=" * 50)
    logger.info("Indexing TogoMedium Media")
    logger.info("=" * 50)

    collection_name = "togomedium_media"

    if clear:
        try:
            chroma_client.delete_collection(collection_name)
            logger.info(f"Cleared existing collection '{collection_name}'")
        except Exception:
            pass

    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "TogoMedium culture media for semantic search"},
    )

    # Batch index media - deduplicate by ID
    batch_ids = []
    batch_docs = []
    batch_metas = []
    batch_size = 500
    indexed = 0
    seen_ids: set[str] = set()

    for doc in tqdm(media_list, desc="Media"):
        searchable_text, metadata = flatten_medium_doc(doc)
        if not searchable_text.strip():
            continue

        media_id = metadata.get("togomedium_id", f"unknown_{indexed}")
        # Include original_id to make unique if same togomedium_id
        original_id = metadata.get("original_id", "")
        doc_id = f"TogoMedium_{media_id}_{original_id}" if original_id else f"TogoMedium_{media_id}"

        # Skip duplicates within batch
        if doc_id in seen_ids:
            continue
        seen_ids.add(doc_id)

        batch_ids.append(doc_id)
        batch_docs.append(searchable_text)
        batch_metas.append(metadata)
        indexed += 1

        if len(batch_ids) >= batch_size:
            collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
            batch_ids, batch_docs, batch_metas = [], [], []

    # Final batch
    if batch_ids:
        collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)

    logger.info(f"Indexed {indexed} media")
    logger.info(f"Collection count: {collection.count()}")
    return indexed


def run_tests(chroma_client) -> tuple[int, int]:
    """Run test cases against indexed collection."""
    logger.info("\n" + "=" * 60)
    logger.info("RUNNING TEST CASES")
    logger.info("=" * 60)

    passed = 0
    total = 0

    try:
        collection = chroma_client.get_collection("togomedium_media")
        logger.info(f"Collection has {collection.count()} documents")
    except Exception as e:
        logger.warning(f"Collection not found: {e}")
        return 0, 0

    for query, expected_substrings, description in TEST_CASES:
        total += 1
        try:
            results = collection.query(query_texts=[query], n_results=5)

            found = False
            matched_text = ""
            for doc in results.get("documents", [[]])[0]:
                doc_lower = doc.lower()
                if any(sub.lower() in doc_lower for sub in expected_substrings):
                    found = True
                    matched_text = doc[:80] + "..." if len(doc) > 80 else doc
                    break

            if found:
                passed += 1
                logger.info(f"  PASS: '{query}' ({description})")
                logger.info(f"        -> {matched_text}")
            else:
                logger.warning(f"  FAIL: '{query}' ({description})")
                logger.warning(f"        Expected: {expected_substrings}")
                if results.get("documents", [[]])[0]:
                    logger.warning(f"        Got: {results['documents'][0][0][:80]}...")

        except Exception as e:
            logger.warning(f"  ERROR: '{query}' - {e}")

    logger.info(f"\n{'=' * 60}")
    logger.info(f"TEST RESULTS: {passed}/{total} passed ({100 * passed / total:.1f}%)" if total > 0 else "No tests run")
    logger.info("=" * 60)

    return passed, total


def demo_searches(chroma_client) -> None:
    """Demonstrate search capabilities."""
    logger.info("\n" + "=" * 60)
    logger.info("DEMO: TogoMedium ChromaDB Search")
    logger.info("=" * 60)

    demo_queries = [
        ("LB agar", "Common lab medium"),
        ("minimal salts medium", "Defined medium search"),
        ("methanotroph medium", "Phenotype-based search"),
        ("DSMZ medium", "Source-based search"),
        ("peptone yeast glucose", "Ingredient-based search"),
    ]

    try:
        collection = chroma_client.get_collection("togomedium_media")

        for query, description in demo_queries:
            logger.info(f"\n--- Query: '{query}' ({description}) ---")
            results = collection.query(query_texts=[query], n_results=3)

            for i, (_doc_id, dist, meta) in enumerate(
                zip(results["ids"][0], results["distances"][0], results["metadatas"][0], strict=False)
            ):
                name = meta.get("name", "Unknown")
                tgm_id = meta.get("togomedium_id", "")
                logger.info(f"  {i + 1}. {name} ({tgm_id}) - dist: {dist:.3f}")

    except Exception as e:
        logger.warning(f"Demo failed: {e}")


@click.command()
@click.option("--clear/--no-clear", default=True, help="Clear existing collection")
@click.option("--test/--no-test", default=False, help="Run test cases after indexing")
@click.option("--demo/--no-demo", default=False, help="Run demo searches")
@click.option("--test-only", is_flag=True, help="Only run tests (skip indexing)")
@click.option("--refresh", is_flag=True, help="Force refresh from API (ignore cache)")
def main(clear: bool, test: bool, demo: bool, test_only: bool, refresh: bool) -> None:
    """Index TogoMedium data into ChromaDB."""
    logger.info("=" * 60)
    logger.info("TogoMedium ChromaDB Indexer")
    logger.info("=" * 60)

    cache_dir = Path(DATA_CACHE_PATH)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

    if not test_only:
        # Fetch media from API
        media_list = fetch_all_media(cache_dir, force_refresh=refresh)
        logger.info(f"Total media fetched: {len(media_list)}")

        # Index into ChromaDB
        index_media(media_list, chroma_client, clear=clear)

    if test or test_only:
        passed, total = run_tests(chroma_client)
        if total > 0 and passed < total:
            logger.warning(f"Some tests failed: {total - passed}/{total}")

    if demo:
        demo_searches(chroma_client)

    logger.info("\nDone!")


if __name__ == "__main__":
    main()
