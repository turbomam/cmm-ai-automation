#!/usr/bin/env python3
"""Cache NCBI searches from input sheets to MongoDB.

Iterates through input sheets (taxa_and_genomes, strains, growth_preferences),
extracts identifiers, and searches NCBI databases. Results are cached to MongoDB
to avoid redundant searches.

Logging is verbose to provide visibility into the process.
"""

import csv
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import click
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection

# Load environment variables
load_dotenv()

# NCBI API key (optional but recommended for higher rate limits)
NCBI_API_KEY = os.getenv("NCBI_API_KEY")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# NCBI API endpoints
NCBI_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_ELINK_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
NCBI_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
NCBI_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

# Default paths
DEFAULT_TAXA_GENOMES = Path("data/private/taxa_and_genomes.tsv")
DEFAULT_STRAINS = Path("data/private/strains.tsv")
DEFAULT_GROWTH_PREFS = Path("data/private/growth_preferences.tsv")
DEFAULT_LOG_FILE = Path("output/ncbi_cache_log.txt")


@dataclass
class SearchableIdentifier:
    """An identifier extracted from a sheet that can be searched."""

    sheet_name: str
    row_number: int
    column_name: str
    raw_value: str
    identifier_type: str  # "ncbi_taxon", "ncbi_assembly", etc.
    clean_id: str  # The actual ID to search (e.g., "270351" not "NCBITaxon:270351")


def get_mongodb_client() -> MongoClient | None:
    """Get MongoDB client connection."""
    try:
        client: MongoClient = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return None


def get_cache_collection(client: MongoClient, collection_name: str) -> Collection:
    """Get or create a cache collection."""
    db = client["ncbi_cache"]
    return db[collection_name]


def is_cached(collection: Collection, query_id: str) -> bool:
    """Check if an ID is already cached."""
    return collection.find_one({"query_id": query_id}) is not None


def save_to_cache(collection: Collection, query_id: str, response: dict, query_type: str) -> None:
    """Save a response to the cache."""
    doc = {
        "query_id": query_id,
        "query_type": query_type,
        "fetched_at": datetime.now(UTC).isoformat(),
        "response": response,
    }
    collection.insert_one(doc)


# =============================================================================
# Identifier Extraction
# =============================================================================


def extract_ncbi_taxon_id(value: str) -> str | None:
    """Extract NCBI Taxon ID from various formats.

    Handles:
    - Plain numbers: "270351"
    - CURIEs: "NCBITaxon:270351"
    - With source suffix: "NCBITaxon:270351|kg-microbe"
    """
    if not value or not value.strip():
        return None

    value = value.strip()

    # Handle CURIE format
    if value.startswith("NCBITaxon:"):
        # Extract just the ID part
        id_part = value.split(":")[1]
        # Remove any suffix like "|kg-microbe"
        id_part = id_part.split("|")[0]
        if id_part.isdigit():
            return id_part

    # Handle plain number
    if value.isdigit():
        return value

    return None


def extract_assembly_id(value: str) -> str | None:
    """Extract NCBI Assembly ID (GCA_/GCF_ accession).

    Handles:
    - "GCA_007095475.1"
    - "GCF_000001234.1"
    """
    if not value or not value.strip():
        return None

    value = value.strip()

    if value.startswith("GCA_") or value.startswith("GCF_"):
        return value

    return None


def extract_identifiers_from_taxa_genomes_row(row: dict, row_number: int) -> list[SearchableIdentifier]:
    """Extract searchable identifiers from a taxa_and_genomes row."""
    identifiers = []
    sheet_name = "taxa_and_genomes"

    # NCBITaxon id column
    ncbi_id = extract_ncbi_taxon_id(row.get("NCBITaxon id", ""))
    if ncbi_id:
        identifiers.append(
            SearchableIdentifier(
                sheet_name=sheet_name,
                row_number=row_number,
                column_name="NCBITaxon id",
                raw_value=row.get("NCBITaxon id", ""),
                identifier_type="ncbi_taxon",
                clean_id=ncbi_id,
            )
        )

    # Genome identifier column
    assembly_id = extract_assembly_id(row.get("Genome identifier (GenBank, IMG etc)", ""))
    if assembly_id:
        identifiers.append(
            SearchableIdentifier(
                sheet_name=sheet_name,
                row_number=row_number,
                column_name="Genome identifier (GenBank, IMG etc)",
                raw_value=row.get("Genome identifier (GenBank, IMG etc)", ""),
                identifier_type="ncbi_assembly",
                clean_id=assembly_id,
            )
        )

    # kg_node_ids column - may contain multiple CURIEs
    kg_nodes = row.get("kg_node_ids", "")
    if kg_nodes:
        # Split by semicolon and/or pipe
        for part in kg_nodes.replace(";", "|").split("|"):
            part = part.strip()
            ncbi_id = extract_ncbi_taxon_id(part)
            if ncbi_id:
                identifiers.append(
                    SearchableIdentifier(
                        sheet_name=sheet_name,
                        row_number=row_number,
                        column_name="kg_node_ids",
                        raw_value=part,
                        identifier_type="ncbi_taxon",
                        clean_id=ncbi_id,
                    )
                )

    return identifiers


def extract_identifiers_from_strains_row(row: dict, row_number: int) -> list[SearchableIdentifier]:
    """Extract searchable identifiers from a strains row."""
    identifiers = []
    sheet_name = "strains"

    # species_taxon_id column
    ncbi_id = extract_ncbi_taxon_id(row.get("species_taxon_id", ""))
    if ncbi_id:
        identifiers.append(
            SearchableIdentifier(
                sheet_name=sheet_name,
                row_number=row_number,
                column_name="species_taxon_id",
                raw_value=row.get("species_taxon_id", ""),
                identifier_type="ncbi_taxon",
                clean_id=ncbi_id,
            )
        )

    # Genome column
    assembly_id = extract_assembly_id(row.get("Genome", ""))
    if assembly_id:
        identifiers.append(
            SearchableIdentifier(
                sheet_name=sheet_name,
                row_number=row_number,
                column_name="Genome",
                raw_value=row.get("Genome", ""),
                identifier_type="ncbi_assembly",
                clean_id=assembly_id,
            )
        )

    # kg_microbe_nodes column - may contain multiple CURIEs
    kg_nodes = row.get("kg_microbe_nodes", "")
    if kg_nodes:
        for part in kg_nodes.replace(";", "|").split("|"):
            part = part.strip()
            ncbi_id = extract_ncbi_taxon_id(part)
            if ncbi_id:
                identifiers.append(
                    SearchableIdentifier(
                        sheet_name=sheet_name,
                        row_number=row_number,
                        column_name="kg_microbe_nodes",
                        raw_value=part,
                        identifier_type="ncbi_taxon",
                        clean_id=ncbi_id,
                    )
                )

    return identifiers


def extract_identifiers_from_growth_prefs_row(_row: dict, _row_number: int) -> list[SearchableIdentifier]:
    """Extract searchable identifiers from a growth_preferences row.

    Note: This sheet has no external database identifiers.
    """
    return []


# =============================================================================
# NCBI API Functions
# =============================================================================


def fetch_with_retry(url: str, params: dict, max_retries: int = 3) -> requests.Response | None:
    """Fetch URL with retry logic for rate limiting.

    Automatically adds NCBI API key if available (increases rate limit from 3 to 10 req/sec).
    """
    # Add API key if available
    if NCBI_API_KEY:
        params = {**params, "api_key": NCBI_API_KEY}

    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 429:
                # Rate limited - wait and retry
                wait_time = 2**attempt  # 1, 2, 4 seconds
                logger.warning(f"Rate limited (429), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response

        except requests.exceptions.HTTPError as e:
            if "429" in str(e):
                wait_time = 2**attempt
                logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                time.sleep(wait_time)
                continue
            raise

    return None


def fetch_ncbi_taxonomy(taxon_id: str) -> dict | None:
    """Fetch NCBI Taxonomy record and convert XML to dict."""
    try:
        response = fetch_with_retry(
            NCBI_EFETCH_URL,
            params={"db": "taxonomy", "id": taxon_id, "retmode": "xml"},
        )

        if response is None:
            return None

        # Parse XML to dict
        root = ET.fromstring(response.content)
        taxon = root.find("Taxon")

        if taxon is None:
            return None

        # Convert XML to dict (preserve structure)
        result = xml_element_to_dict(taxon)
        result["_raw_xml"] = response.text  # Keep raw XML too
        return result

    except Exception as e:
        logger.error(f"Error fetching taxonomy {taxon_id}: {e}")
        return None


def fetch_ncbi_taxonomy_linkouts(taxon_id: str) -> dict | None:
    """Fetch external linkouts for a taxonomy record."""
    try:
        response = fetch_with_retry(
            NCBI_ELINK_URL,
            params={
                "dbfrom": "taxonomy",
                "id": taxon_id,
                "cmd": "llinkslib",  # Get external links
                "retmode": "xml",
            },
        )

        if response is None:
            return None

        # Parse and convert to dict
        root = ET.fromstring(response.content)
        result = xml_element_to_dict(root)
        result["_raw_xml"] = response.text
        return result

    except Exception as e:
        logger.error(f"Error fetching linkouts for {taxon_id}: {e}")
        return None


def fetch_ncbi_taxonomy_entrez_links(taxon_id: str) -> dict | None:
    """Fetch internal Entrez links for a taxonomy record (Assembly, BioProject, etc.).

    Uses default elink behavior (no cmd parameter) to get cross-database links.
    """
    try:
        response = fetch_with_retry(
            NCBI_ELINK_URL,
            params={
                "dbfrom": "taxonomy",
                "id": taxon_id,
                "retmode": "xml",
            },
        )

        if response is None:
            return None

        root = ET.fromstring(response.content)
        result = xml_element_to_dict(root)
        result["_raw_xml"] = response.text
        return result

    except Exception as e:
        logger.error(f"Error fetching entrez links for {taxon_id}: {e}")
        return None


def fetch_ncbi_assembly(assembly_accession: str) -> dict | None:
    """Fetch NCBI Assembly summary.

    First uses esearch to convert accession (GCA_/GCF_) to UID,
    then uses esummary to get the full record.
    """
    try:
        # Step 1: Search for assembly by accession to get UID
        search_response = fetch_with_retry(
            NCBI_ESEARCH_URL,
            params={"db": "assembly", "term": assembly_accession, "retmode": "json"},
        )

        if search_response is None:
            return None

        search_data = search_response.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])

        if not id_list:
            logger.warning(f"No assembly UID found for accession {assembly_accession}")
            return {"error": "no_uid_found", "accession": assembly_accession, "search_result": search_data}

        uid = id_list[0]
        time.sleep(0.1)  # Brief pause between API calls

        # Step 2: Get assembly summary using UID
        summary_response = fetch_with_retry(
            NCBI_ESUMMARY_URL,
            params={"db": "assembly", "id": uid, "retmode": "json"},
        )

        if summary_response is None:
            return None

        result = summary_response.json()
        result["_query_accession"] = assembly_accession
        result["_resolved_uid"] = uid
        return result

    except Exception as e:
        logger.error(f"Error fetching assembly {assembly_accession}: {e}")
        return None


def fetch_ncbi_assembly_linkouts(assembly_uid: str) -> dict | None:
    """Fetch external linkouts for an assembly record."""
    try:
        response = fetch_with_retry(
            NCBI_ELINK_URL,
            params={
                "dbfrom": "assembly",
                "id": assembly_uid,
                "cmd": "llinkslib",
                "retmode": "xml",
            },
        )

        if response is None:
            return None

        root = ET.fromstring(response.content)
        result = xml_element_to_dict(root)
        result["_raw_xml"] = response.text
        return result

    except Exception as e:
        logger.error(f"Error fetching assembly linkouts for {assembly_uid}: {e}")
        return None


def fetch_ncbi_assembly_entrez_links(assembly_uid: str) -> dict | None:
    """Fetch internal Entrez links for an assembly record (BioProject, BioSample, etc.)."""
    try:
        response = fetch_with_retry(
            NCBI_ELINK_URL,
            params={
                "dbfrom": "assembly",
                "id": assembly_uid,
                "retmode": "xml",
            },
        )

        if response is None:
            return None

        root = ET.fromstring(response.content)
        result = xml_element_to_dict(root)
        result["_raw_xml"] = response.text
        return result

    except Exception as e:
        logger.error(f"Error fetching assembly entrez links for {assembly_uid}: {e}")
        return None


def xml_element_to_dict(element: ET.Element) -> dict:
    """Recursively convert an XML element to a dictionary."""
    result: dict = {}

    # Add element attributes
    if element.attrib:
        result["@attributes"] = dict(element.attrib)

    # Add text content
    if element.text and element.text.strip():
        result["@text"] = element.text.strip()

    # Add children
    for child in element:
        child_dict = xml_element_to_dict(child)

        if child.tag in result:
            # Convert to list if multiple children with same tag
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(child_dict)
        else:
            result[child.tag] = child_dict

    return result


# =============================================================================
# Main Processing
# =============================================================================


def process_identifier(
    identifier: SearchableIdentifier,
    taxonomy_cache: Collection,
    taxonomy_linkouts_cache: Collection,
    taxonomy_entrez_cache: Collection,
    assembly_cache: Collection,
    assembly_linkouts_cache: Collection,
    assembly_entrez_cache: Collection,
    dry_run: bool = False,
) -> dict:
    """Process a single identifier - check cache, search if needed, save results.

    Returns a summary dict of what was done.
    """
    summary = {
        "identifier": identifier.clean_id,
        "type": identifier.identifier_type,
        "actions": [],
    }

    if identifier.identifier_type == "ncbi_taxon":
        # Check taxonomy cache
        if is_cached(taxonomy_cache, identifier.clean_id):
            logger.info(f"    CACHE HIT: ncbi_taxonomy_cache already has {identifier.clean_id}")
            summary["actions"].append(("ncbi_taxonomy", "cache_hit"))
        else:
            logger.info(f"    CACHE MISS: Will search NCBI Taxonomy for {identifier.clean_id}")
            if not dry_run:
                result = fetch_ncbi_taxonomy(identifier.clean_id)
                if result:
                    save_to_cache(taxonomy_cache, identifier.clean_id, result, "taxonomy")
                    logger.info(f"    SAVED: Taxonomy record for {identifier.clean_id}")
                    summary["actions"].append(("ncbi_taxonomy", "fetched_and_saved"))
                else:
                    logger.warning(f"    FAILED: Could not fetch taxonomy for {identifier.clean_id}")
                    summary["actions"].append(("ncbi_taxonomy", "fetch_failed"))
                time.sleep(0.1)  # Rate limit
            else:
                summary["actions"].append(("ncbi_taxonomy", "would_fetch"))

        # Check linkouts cache
        if is_cached(taxonomy_linkouts_cache, identifier.clean_id):
            logger.info(f"    CACHE HIT: ncbi_taxonomy_linkouts_cache already has {identifier.clean_id}")
            summary["actions"].append(("ncbi_linkouts", "cache_hit"))
        else:
            logger.info(f"    CACHE MISS: Will search NCBI linkouts for {identifier.clean_id}")
            if not dry_run:
                result = fetch_ncbi_taxonomy_linkouts(identifier.clean_id)
                if result:
                    save_to_cache(taxonomy_linkouts_cache, identifier.clean_id, result, "linkouts")
                    logger.info(f"    SAVED: Linkouts for {identifier.clean_id}")
                    summary["actions"].append(("ncbi_linkouts", "fetched_and_saved"))
                else:
                    logger.warning(f"    FAILED: Could not fetch linkouts for {identifier.clean_id}")
                    summary["actions"].append(("ncbi_linkouts", "fetch_failed"))
                time.sleep(0.1)
            else:
                summary["actions"].append(("ncbi_linkouts", "would_fetch"))

        # Check entrez links cache
        if is_cached(taxonomy_entrez_cache, identifier.clean_id):
            logger.info(f"    CACHE HIT: ncbi_taxonomy_entrez_cache already has {identifier.clean_id}")
            summary["actions"].append(("ncbi_entrez", "cache_hit"))
        else:
            logger.info(f"    CACHE MISS: Will search NCBI entrez links for {identifier.clean_id}")
            if not dry_run:
                result = fetch_ncbi_taxonomy_entrez_links(identifier.clean_id)
                if result:
                    save_to_cache(taxonomy_entrez_cache, identifier.clean_id, result, "entrez_links")
                    logger.info(f"    SAVED: Entrez links for {identifier.clean_id}")
                    summary["actions"].append(("ncbi_entrez", "fetched_and_saved"))
                else:
                    logger.warning(f"    FAILED: Could not fetch entrez links for {identifier.clean_id}")
                    summary["actions"].append(("ncbi_entrez", "fetch_failed"))
                time.sleep(0.1)
            else:
                summary["actions"].append(("ncbi_entrez", "would_fetch"))

    elif identifier.identifier_type == "ncbi_assembly":
        assembly_uid = None

        # Check assembly cache
        if is_cached(assembly_cache, identifier.clean_id):
            logger.info(f"    CACHE HIT: ncbi_assembly_cache already has {identifier.clean_id}")
            summary["actions"].append(("ncbi_assembly", "cache_hit"))
            # Get the UID from the cached document for linkout/entrez lookups
            cached_doc = assembly_cache.find_one({"query_id": identifier.clean_id})
            if cached_doc:
                assembly_uid = cached_doc.get("response", {}).get("_resolved_uid")
        else:
            logger.info(f"    CACHE MISS: Will search NCBI Assembly for {identifier.clean_id}")
            if not dry_run:
                result = fetch_ncbi_assembly(identifier.clean_id)
                if result:
                    save_to_cache(assembly_cache, identifier.clean_id, result, "assembly")
                    logger.info(f"    SAVED: Assembly record for {identifier.clean_id}")
                    summary["actions"].append(("ncbi_assembly", "fetched_and_saved"))
                    assembly_uid = result.get("_resolved_uid")
                else:
                    logger.warning(f"    FAILED: Could not fetch assembly for {identifier.clean_id}")
                    summary["actions"].append(("ncbi_assembly", "fetch_failed"))
                time.sleep(0.1)
            else:
                summary["actions"].append(("ncbi_assembly", "would_fetch"))

        # Fetch linkouts and entrez links using the resolved UID
        if assembly_uid:
            # Check assembly linkouts cache
            if is_cached(assembly_linkouts_cache, assembly_uid):
                logger.info(f"    CACHE HIT: ncbi_assembly_linkouts_cache already has UID {assembly_uid}")
                summary["actions"].append(("ncbi_assembly_linkouts", "cache_hit"))
            else:
                logger.info(f"    CACHE MISS: Will search NCBI assembly linkouts for UID {assembly_uid}")
                if not dry_run:
                    result = fetch_ncbi_assembly_linkouts(assembly_uid)
                    if result:
                        save_to_cache(assembly_linkouts_cache, assembly_uid, result, "assembly_linkouts")
                        logger.info(f"    SAVED: Assembly linkouts for UID {assembly_uid}")
                        summary["actions"].append(("ncbi_assembly_linkouts", "fetched_and_saved"))
                    else:
                        logger.warning(f"    FAILED: Could not fetch assembly linkouts for UID {assembly_uid}")
                        summary["actions"].append(("ncbi_assembly_linkouts", "fetch_failed"))
                    time.sleep(0.1)
                else:
                    summary["actions"].append(("ncbi_assembly_linkouts", "would_fetch"))

            # Check assembly entrez links cache
            if is_cached(assembly_entrez_cache, assembly_uid):
                logger.info(f"    CACHE HIT: ncbi_assembly_entrez_cache already has UID {assembly_uid}")
                summary["actions"].append(("ncbi_assembly_entrez", "cache_hit"))
            else:
                logger.info(f"    CACHE MISS: Will search NCBI assembly entrez links for UID {assembly_uid}")
                if not dry_run:
                    result = fetch_ncbi_assembly_entrez_links(assembly_uid)
                    if result:
                        save_to_cache(assembly_entrez_cache, assembly_uid, result, "assembly_entrez_links")
                        logger.info(f"    SAVED: Assembly entrez links for UID {assembly_uid}")
                        summary["actions"].append(("ncbi_assembly_entrez", "fetched_and_saved"))
                    else:
                        logger.warning(f"    FAILED: Could not fetch assembly entrez links for UID {assembly_uid}")
                        summary["actions"].append(("ncbi_assembly_entrez", "fetch_failed"))
                    time.sleep(0.1)
                else:
                    summary["actions"].append(("ncbi_assembly_entrez", "would_fetch"))

    return summary


def process_sheet(
    sheet_path: Path,
    sheet_name: str,
    extract_fn,
    taxonomy_cache: Collection,
    taxonomy_linkouts_cache: Collection,
    taxonomy_entrez_cache: Collection,
    assembly_cache: Collection,
    assembly_linkouts_cache: Collection,
    assembly_entrez_cache: Collection,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    """Process all rows in a sheet."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PROCESSING SHEET: {sheet_name}")
    logger.info(f"Path: {sheet_path}")
    logger.info(f"{'=' * 60}")

    stats = {
        "rows_processed": 0,
        "identifiers_found": 0,
        "cache_hits": 0,
        "fetches": 0,
        "failures": 0,
    }

    seen_ids: set[tuple[str, str]] = set()  # (type, id) to avoid duplicate searches within sheet

    with sheet_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
            if limit and row_num > limit + 1:
                logger.info(f"  Reached limit of {limit} rows, stopping.")
                break

            # Get a display name for the row
            row_name = row.get("Strain name") or row.get("scientific_name") or row.get("strain id") or f"Row {row_num}"

            logger.info(f"\n  Row {row_num}: {row_name}")

            identifiers = extract_fn(row, row_num)

            if not identifiers:
                logger.info("    No searchable identifiers found")
                stats["rows_processed"] += 1
                continue

            for ident in identifiers:
                # Skip if we've already processed this ID in this run
                id_key = (ident.identifier_type, ident.clean_id)
                if id_key in seen_ids:
                    logger.info(f"    SKIP: Already processed {ident.identifier_type}:{ident.clean_id} in this run")
                    continue
                seen_ids.add(id_key)

                logger.info(f"    Found {ident.identifier_type}: {ident.clean_id} (from column '{ident.column_name}')")
                stats["identifiers_found"] += 1

                summary = process_identifier(
                    ident,
                    taxonomy_cache,
                    taxonomy_linkouts_cache,
                    taxonomy_entrez_cache,
                    assembly_cache,
                    assembly_linkouts_cache,
                    assembly_entrez_cache,
                    dry_run,
                )

                for _action_type, action_result in summary["actions"]:
                    if action_result == "cache_hit":
                        stats["cache_hits"] += 1
                    elif action_result in ("fetched_and_saved", "would_fetch"):
                        stats["fetches"] += 1
                    elif action_result == "fetch_failed":
                        stats["failures"] += 1

            stats["rows_processed"] += 1

    logger.info("\n  Sheet Summary:")
    logger.info(f"    Rows processed: {stats['rows_processed']}")
    logger.info(f"    Identifiers found: {stats['identifiers_found']}")
    logger.info(f"    Cache hits: {stats['cache_hits']}")
    logger.info(f"    Fetches: {stats['fetches']}")
    logger.info(f"    Failures: {stats['failures']}")

    return stats


@click.command()
@click.option(
    "--taxa-genomes-tsv",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_TAXA_GENOMES,
    help="Path to taxa_and_genomes.tsv",
)
@click.option(
    "--strains-tsv",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_STRAINS,
    help="Path to strains.tsv",
)
@click.option(
    "--growth-prefs-tsv",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_GROWTH_PREFS,
    help="Path to growth_preferences.tsv",
)
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    default=DEFAULT_LOG_FILE,
    help="Path to log file",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Don't actually search or save - just show what would be done",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit number of rows per sheet (for testing)",
)
@click.option(
    "--sheet",
    type=click.Choice(["all", "taxa_and_genomes", "strains", "growth_preferences"]),
    default="all",
    help="Which sheet(s) to process",
)
@click.option(
    "--clear-cache/--no-clear-cache",
    default=True,
    help="Clear all cache collections before starting (default: True)",
)
def main(
    taxa_genomes_tsv: Path,
    strains_tsv: Path,
    growth_prefs_tsv: Path,
    log_file: Path,
    dry_run: bool,
    limit: int | None,
    sheet: str,
    clear_cache: bool,
) -> None:
    """Cache NCBI searches from input sheets to MongoDB.

    Iterates through sheets, extracts identifiers, checks MongoDB cache,
    and fetches from NCBI if not cached. All actions are logged.
    """
    load_dotenv()

    # Add file handler for logging
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)

    logger.info("\n" + "=" * 60)
    logger.info("NCBI CACHE SEARCH - STARTING")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Limit per sheet: {limit or 'None'}")
    logger.info(f"Clear cache: {clear_cache}")
    if NCBI_API_KEY:
        logger.info("NCBI API key: configured (10 req/sec limit)")
    else:
        logger.info("NCBI API key: not set (3 req/sec limit)")
    logger.info("=" * 60)

    # Connect to MongoDB
    client = get_mongodb_client()
    if client is None:
        logger.error("Cannot proceed without MongoDB connection")
        return

    # Get cache collections
    taxonomy_cache = get_cache_collection(client, "ncbi_taxonomy_cache")
    taxonomy_linkouts_cache = get_cache_collection(client, "ncbi_taxonomy_linkouts_cache")
    taxonomy_entrez_cache = get_cache_collection(client, "ncbi_taxonomy_entrez_cache")
    assembly_cache = get_cache_collection(client, "ncbi_assembly_cache")
    assembly_linkouts_cache = get_cache_collection(client, "ncbi_assembly_linkouts_cache")
    assembly_entrez_cache = get_cache_collection(client, "ncbi_assembly_entrez_cache")

    # Clear all collections if requested
    if clear_cache and not dry_run:
        logger.info("\nClearing all cache collections...")
        taxonomy_cache.delete_many({})
        taxonomy_linkouts_cache.delete_many({})
        taxonomy_entrez_cache.delete_many({})
        assembly_cache.delete_many({})
        assembly_linkouts_cache.delete_many({})
        assembly_entrez_cache.delete_many({})
        logger.info("All cache collections cleared.")

    # Create indexes for fast lookups
    taxonomy_cache.create_index("query_id", unique=True)
    taxonomy_linkouts_cache.create_index("query_id", unique=True)
    taxonomy_entrez_cache.create_index("query_id", unique=True)
    assembly_cache.create_index("query_id", unique=True)
    assembly_linkouts_cache.create_index("query_id", unique=True)
    assembly_entrez_cache.create_index("query_id", unique=True)

    logger.info("\nMongoDB collections:")
    logger.info(f"  ncbi_taxonomy_cache: {taxonomy_cache.count_documents({})} documents")
    logger.info(f"  ncbi_taxonomy_linkouts_cache: {taxonomy_linkouts_cache.count_documents({})} documents")
    logger.info(f"  ncbi_taxonomy_entrez_cache: {taxonomy_entrez_cache.count_documents({})} documents")
    logger.info(f"  ncbi_assembly_cache: {assembly_cache.count_documents({})} documents")
    logger.info(f"  ncbi_assembly_linkouts_cache: {assembly_linkouts_cache.count_documents({})} documents")
    logger.info(f"  ncbi_assembly_entrez_cache: {assembly_entrez_cache.count_documents({})} documents")

    all_stats = {}

    # Process sheets
    sheets_to_process = []
    if sheet in ("all", "taxa_and_genomes"):
        sheets_to_process.append(("taxa_and_genomes", taxa_genomes_tsv, extract_identifiers_from_taxa_genomes_row))
    if sheet in ("all", "strains"):
        sheets_to_process.append(("strains", strains_tsv, extract_identifiers_from_strains_row))
    if sheet in ("all", "growth_preferences"):
        sheets_to_process.append(("growth_preferences", growth_prefs_tsv, extract_identifiers_from_growth_prefs_row))

    for sheet_name, sheet_path, extract_fn in sheets_to_process:
        stats = process_sheet(
            sheet_path,
            sheet_name,
            extract_fn,
            taxonomy_cache,
            taxonomy_linkouts_cache,
            taxonomy_entrez_cache,
            assembly_cache,
            assembly_linkouts_cache,
            assembly_entrez_cache,
            dry_run,
            limit,
        )
        all_stats[sheet_name] = stats

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 60)

    total_rows = sum(s["rows_processed"] for s in all_stats.values())
    total_ids = sum(s["identifiers_found"] for s in all_stats.values())
    total_hits = sum(s["cache_hits"] for s in all_stats.values())
    total_fetches = sum(s["fetches"] for s in all_stats.values())
    total_failures = sum(s["failures"] for s in all_stats.values())

    logger.info(f"Total rows processed: {total_rows}")
    logger.info(f"Total identifiers found: {total_ids}")
    logger.info(f"Total cache hits: {total_hits}")
    logger.info(f"Total fetches: {total_fetches}")
    logger.info(f"Total failures: {total_failures}")

    logger.info("\nMongoDB collections after run:")
    logger.info(f"  ncbi_taxonomy_cache: {taxonomy_cache.count_documents({})} documents")
    logger.info(f"  ncbi_taxonomy_linkouts_cache: {taxonomy_linkouts_cache.count_documents({})} documents")
    logger.info(f"  ncbi_taxonomy_entrez_cache: {taxonomy_entrez_cache.count_documents({})} documents")
    logger.info(f"  ncbi_assembly_cache: {assembly_cache.count_documents({})} documents")
    logger.info(f"  ncbi_assembly_linkouts_cache: {assembly_linkouts_cache.count_documents({})} documents")
    logger.info(f"  ncbi_assembly_entrez_cache: {assembly_entrez_cache.count_documents({})} documents")

    logger.info(f"\nLog saved to: {log_file}")
    logger.info("DONE")


if __name__ == "__main__":
    main()
