"""BacDive MongoDB lookup functions for strain enrichment.

This module provides functions to look up strain data in BacDive's
local MongoDB database and enrich strain records with that data.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pymongo.collection import Collection

    from cmm_ai_automation.strains.models import StrainRecord

logger = logging.getLogger(__name__)

# MongoDB connection settings for BacDive
MONGODB_URI = "mongodb://localhost:27017"
BACDIVE_DB = "bacdive"
BACDIVE_COLLECTION = "strains"


def get_bacdive_collection() -> Collection[dict[str, Any]] | None:
    """Get MongoDB collection for BacDive strains.

    Returns:
        MongoDB collection or None if connection fails
    """
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure

        client: MongoClient[dict[str, Any]] = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2000)
        # Test connection
        client.admin.command("ping")
        return client[BACDIVE_DB][BACDIVE_COLLECTION]
    except (ImportError, ConnectionFailure) as e:
        logger.warning(f"Could not connect to BacDive MongoDB: {e}")
        return None


def lookup_bacdive_by_dsm(collection: Collection[dict[str, Any]], dsm_number: int) -> dict[str, Any] | None:
    """Look up a BacDive record by DSM number.

    Args:
        collection: MongoDB collection
        dsm_number: DSM number (e.g., 16371)

    Returns:
        BacDive document or None
    """
    result: dict[str, Any] | None = collection.find_one({"General.DSM-Number": dsm_number})
    return result


def lookup_bacdive_by_ncbi_taxon(collection: Collection[dict[str, Any]], taxon_id: int) -> dict[str, Any] | None:
    """Look up a BacDive record by NCBITaxon ID.

    Note: Multiple BacDive records may share the same NCBITaxon ID (different strains
    of the same species). This returns the first match.

    Args:
        collection: MongoDB collection
        taxon_id: NCBITaxon ID (e.g., 270351)

    Returns:
        BacDive document or None
    """
    result: dict[str, Any] | None = collection.find_one({"General.NCBI tax id.NCBI tax id": taxon_id})
    return result


def lookup_bacdive_by_species(collection: Collection[dict[str, Any]], species_name: str) -> dict[str, Any] | None:
    """Look up a BacDive record by species name.

    Args:
        collection: MongoDB collection
        species_name: Binomial species name (e.g., "Methylobacterium aquaticum")

    Returns:
        BacDive document or None
    """
    result: dict[str, Any] | None = collection.find_one({"Name and taxonomic classification.species": species_name})
    return result


def lookup_bacdive_by_culture_collection(
    collection: Collection[dict[str, Any]], search_id: str
) -> dict[str, Any] | None:
    """Look up a BacDive record by culture collection ID.

    Searches the 'External links.culture collection no.' field which contains
    comma-separated list of all culture collection IDs for a strain.

    Uses a MongoDB regex query for server-side filtering instead of client-side
    iteration, reducing network overhead. The pattern matches complete tokens
    in comma-separated lists, preventing false positives (e.g., "DSM 1"
    matching "DSM 11").

    Args:
        collection: MongoDB collection
        search_id: Culture collection ID in format "PREFIX NUMBER" (e.g., "ATCC 43883")

    Returns:
        BacDive document or None
    """
    # Escape search_id to prevent regex injection
    escaped_id = re.escape(search_id)
    # Match complete token: start/comma before, comma/end after
    pattern = rf"(^|,\s*){escaped_id}(\s*,|$)"
    result: dict[str, Any] | None = collection.find_one({"External links.culture collection no.": {"$regex": pattern}})
    return result


def lookup_bacdive_by_strain_designation(
    collection: Collection[dict[str, Any]], designation: str
) -> dict[str, Any] | None:
    """Look up a BacDive record by strain designation.

    Args:
        collection: MongoDB collection
        designation: Strain designation (e.g., "PA1", "AM-1")

    Returns:
        BacDive document or None
    """
    result: dict[str, Any] | None = collection.find_one(
        {"Name and taxonomic classification.strain designation": designation}
    )
    return result


def extract_bacdive_data(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract relevant data from a BacDive document.

    Args:
        doc: BacDive MongoDB document

    Returns:
        Dict with extracted fields
    """
    result: dict[str, Any] = {
        "bacdive_id": None,
        "ncbi_taxon_id": None,
        "species": None,
        "strain_designation": None,
        "type_strain": None,
        "culture_collection_ids": [],
        "synonyms": [],
    }

    # BacDive ID
    general = doc.get("General", {})
    result["bacdive_id"] = general.get("BacDive-ID") or doc.get("_id")

    # NCBITaxon ID
    ncbi_tax = general.get("NCBI tax id", {})
    if isinstance(ncbi_tax, dict):
        result["ncbi_taxon_id"] = ncbi_tax.get("NCBI tax id")

    # Taxonomy info
    taxonomy = doc.get("Name and taxonomic classification", {})
    result["species"] = taxonomy.get("species")
    result["strain_designation"] = taxonomy.get("strain designation")
    # Type strain: "yes" or "no" in BacDive
    type_strain_str = taxonomy.get("type strain", "")
    if type_strain_str:
        result["type_strain"] = type_strain_str.lower() == "yes"

    # LPSN synonyms (homotypic/heterotypic)
    # Can be either a single object or array of objects per BacDive schema
    lpsn = taxonomy.get("LPSN", {})
    if isinstance(lpsn, dict):
        lpsn_synonyms = lpsn.get("synonyms")
        if isinstance(lpsn_synonyms, list):
            # Array of synonym objects
            for syn_entry in lpsn_synonyms:
                if isinstance(syn_entry, dict) and "synonym" in syn_entry:
                    result["synonyms"].append(syn_entry["synonym"])
        elif isinstance(lpsn_synonyms, dict) and "synonym" in lpsn_synonyms:
            # Single synonym object
            result["synonyms"].append(lpsn_synonyms["synonym"])

    # Culture collection IDs from External links
    external = doc.get("External links", {})
    cc_string = external.get("culture collection no.", "")
    if cc_string:
        # Parse comma-separated list: "DSM 1337, ATCC 43645, NCIMB 9399"
        for cc_id in cc_string.split(","):
            cc_id = cc_id.strip()
            if cc_id:
                result["culture_collection_ids"].append(cc_id)

    return result


def enrich_strain_from_bacdive(record: StrainRecord, collection: Collection[dict[str, Any]]) -> bool:
    """Enrich a strain record with data from BacDive.

    Attempts to find the strain in BacDive using multiple strategies:
    1. DSM number lookup (fastest, indexed)
    2. NCBITaxon ID lookup (indexed)
    3. Other culture collection ID lookup (requires scan)
    4. Species name lookup
    5. Strain designation lookup

    Args:
        record: StrainRecord to enrich
        collection: BacDive MongoDB collection

    Returns:
        True if enrichment was successful
    """
    doc = None

    # Strategy 1: Look up by DSM number (indexed, fast)
    for cc_id in record.culture_collection_ids:
        match = re.match(r"(?:DSM|DSMZ)[:\s-]*(\d+)", cc_id, re.IGNORECASE)
        if match:
            dsm_num = int(match.group(1))
            doc = lookup_bacdive_by_dsm(collection, dsm_num)
            if doc:
                logger.debug(f"Found BacDive by DSM {dsm_num}")
                break

    # Strategy 2: Look up by NCBITaxon ID (indexed, fast)
    if not doc and record.ncbi_taxon_id:
        try:
            taxon_id = int(record.ncbi_taxon_id.replace("NCBITaxon:", ""))
            doc = lookup_bacdive_by_ncbi_taxon(collection, taxon_id)
            if doc:
                logger.debug(f"Found BacDive by NCBITaxon {taxon_id}")
        except (ValueError, AttributeError):
            # Invalid or unexpectedly formatted NCBI taxon identifier; skip this strategy
            # and continue with other enrichment strategies.
            pass

    # Strategy 3: Look up by other culture collection ID (slow, full scan)
    if not doc:
        for cc_id in record.culture_collection_ids:
            # Skip DSM (already tried)
            if cc_id.upper().startswith(("DSM", "DSMZ")):
                continue
            # Format for search: "ATCC 43883"
            match = re.match(r"([A-Z]+)[:\s-]*(.+)", cc_id, re.IGNORECASE)
            if match:
                search_id = f"{match.group(1).upper()} {match.group(2)}"
                doc = lookup_bacdive_by_culture_collection(collection, search_id)
                if doc:
                    logger.debug(f"Found BacDive by culture collection {search_id}")
                    break

    # Strategy 4: Look up by species name
    if not doc and record.scientific_name:
        doc = lookup_bacdive_by_species(collection, record.scientific_name)
        if doc:
            logger.debug(f"Found BacDive by species {record.scientific_name}")

    # Strategy 5: Look up by strain designation
    if not doc and record.strain_designation:
        doc = lookup_bacdive_by_strain_designation(collection, record.strain_designation)
        if doc:
            logger.debug(f"Found BacDive by strain designation {record.strain_designation}")

    if not doc:
        return False

    # Extract and apply BacDive data
    bacdive_data = extract_bacdive_data(doc)

    # Apply BacDive ID
    if not record.bacdive_id and bacdive_data["bacdive_id"]:
        record.bacdive_id = str(bacdive_data["bacdive_id"])

    # Apply NCBITaxon ID if missing
    if not record.ncbi_taxon_id and bacdive_data["ncbi_taxon_id"]:
        record.ncbi_taxon_id = str(bacdive_data["ncbi_taxon_id"])

    # Apply strain designation if missing
    if not record.strain_designation and bacdive_data["strain_designation"]:
        record.strain_designation = bacdive_data["strain_designation"]

    # Add all culture collection cross-references
    for cc_id in bacdive_data["culture_collection_ids"]:
        if cc_id not in record.culture_collection_ids:
            record.culture_collection_ids.append(cc_id)

    # Add LPSN synonyms (homotypic/heterotypic species name synonyms)
    for synonym in bacdive_data["synonyms"]:
        if synonym not in record.synonyms:
            record.synonyms.append(synonym)

    # Don't infer rank from BacDive - NCBI is authoritative for rank.
    # If NCBI data is unavailable, infer_taxonomic_rank() will handle it later.

    return True


def enrich_strains_with_bacdive(records: list[StrainRecord], collection: Collection[dict[str, Any]]) -> tuple[int, int]:
    """Enrich all strain records with BacDive data.

    Args:
        records: List of strain records to enrich
        collection: BacDive MongoDB collection

    Returns:
        Tuple of (enriched_count, total_count)
    """
    enriched = 0
    for record in records:
        if enrich_strain_from_bacdive(record, collection):
            enriched += 1

    return enriched, len(records)
