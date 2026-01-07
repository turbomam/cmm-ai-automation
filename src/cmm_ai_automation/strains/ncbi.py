"""NCBI Entrez API functions for strain enrichment.

This module provides functions to fetch data from NCBI Taxonomy using
the Entrez E-utilities API.
"""

from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import TypedDict

import requests

logger = logging.getLogger(__name__)

# NCBI Entrez settings
NCBI_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_ELINK_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
NCBI_REQUEST_TIMEOUT = 10  # seconds


class NcbiTaxonData(TypedDict):
    """Type for NCBI Taxonomy data returned from efetch."""

    synonyms: list[str]
    equivalent_names: list[str]
    includes: list[str]
    misspellings: list[str]
    authority: list[str]
    rank: str
    species_taxon_id: str  # Species-level ancestor from lineage
    parent_taxon_id: str  # Immediate parent taxon from lineage


class NcbiLinkout(TypedDict):
    """External linkout from NCBI."""

    provider: str  # e.g., "BacDive", "BioCyc"
    url: str
    name: str


def fetch_ncbi_synonyms(taxon_id: int | str) -> NcbiTaxonData:
    """Fetch synonyms, related names, rank, and lineage from NCBI Taxonomy.

    Args:
        taxon_id: NCBI Taxonomy ID (integer or string)

    Returns:
        NcbiTaxonData with synonyms, equivalent_names, includes, misspellings, authority (lists),
        rank (string, e.g., 'species', 'strain', 'subspecies'),
        species_taxon_id (species-level ancestor from lineage),
        and parent_taxon_id (immediate parent in taxonomy).
    """
    result: NcbiTaxonData = {
        "synonyms": [],
        "equivalent_names": [],
        "includes": [],
        "misspellings": [],
        "authority": [],
        "rank": "",
        "species_taxon_id": "",
        "parent_taxon_id": "",
    }

    try:
        response = requests.get(
            NCBI_EFETCH_URL,
            params={"db": "taxonomy", "id": str(taxon_id), "retmode": "xml"},
            timeout=NCBI_REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        taxon = root.find(".//Taxon")
        if taxon is None:
            return result

        # Extract taxonomic rank
        rank_elem = taxon.find("Rank")
        if rank_elem is not None and rank_elem.text:
            result["rank"] = rank_elem.text

        # Extract parent taxon ID
        parent_id_elem = taxon.find("ParentTaxId")
        if parent_id_elem is not None and parent_id_elem.text:
            result["parent_taxon_id"] = parent_id_elem.text

        # Extract species-level ancestor from LineageEx
        # LineageEx contains all ancestors with their ranks
        lineage_ex = taxon.find("LineageEx")
        if lineage_ex is not None:
            for ancestor in lineage_ex.findall("Taxon"):
                ancestor_rank = ancestor.find("Rank")
                ancestor_id = ancestor.find("TaxId")
                if (
                    ancestor_rank is not None
                    and ancestor_rank.text == "species"
                    and ancestor_id is not None
                    and ancestor_id.text
                ):
                    result["species_taxon_id"] = ancestor_id.text
                    break  # Take the first (most specific) species ancestor

        # If taxon itself is at species level or below, use its own ID as species_taxon_id
        # (unless we already found a species ancestor, which means this is subspecies/strain)
        if not result["species_taxon_id"] and result["rank"] == "species":
            result["species_taxon_id"] = str(taxon_id)

        other_names = taxon.find("OtherNames")
        if other_names is None:
            return result

        # Extract different name types
        for synonym in other_names.findall("Synonym"):
            if synonym.text:
                result["synonyms"].append(synonym.text)

        for equiv in other_names.findall("EquivalentName"):
            if equiv.text:
                result["equivalent_names"].append(equiv.text)

        for includes in other_names.findall("Includes"):
            if includes.text:
                result["includes"].append(includes.text)

        # Extract from Name elements with ClassCDE
        for name_elem in other_names.findall("Name"):
            class_cde = name_elem.find("ClassCDE")
            disp_name = name_elem.find("DispName")
            if class_cde is not None and disp_name is not None and disp_name.text:
                if class_cde.text == "misspelling":
                    result["misspellings"].append(disp_name.text)
                elif class_cde.text == "authority":
                    result["authority"].append(disp_name.text)

    except (requests.RequestException, ET.ParseError) as e:
        logger.debug(f"Failed to fetch NCBI synonyms for {taxon_id}: {e}")

    return result


def fetch_ncbi_batch(taxon_ids: list[str], batch_size: int = 50) -> dict[str, NcbiTaxonData]:
    """Fetch NCBI Taxonomy data for multiple taxa in batch.

    Args:
        taxon_ids: List of NCBI Taxonomy IDs
        batch_size: Number of IDs per request (default 50)

    Returns:
        Dictionary mapping taxon_id -> NcbiTaxonData
    """
    results: dict[str, NcbiTaxonData] = {}

    # Process in batches
    for i in range(0, len(taxon_ids), batch_size):
        batch = taxon_ids[i : i + batch_size]
        ids_param = ",".join(batch)

        try:
            response = requests.get(
                NCBI_EFETCH_URL,
                params={"db": "taxonomy", "id": ids_param, "retmode": "xml"},
                timeout=30,  # Longer timeout for batch
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)

            # Parse each Taxon element (direct children of TaxaSet)
            for taxon in root.findall("Taxon"):
                taxid_elem = taxon.find("TaxId")
                if taxid_elem is None or not taxid_elem.text:
                    continue

                taxid = taxid_elem.text
                data: NcbiTaxonData = {
                    "synonyms": [],
                    "equivalent_names": [],
                    "includes": [],
                    "misspellings": [],
                    "authority": [],
                    "rank": "",
                    "species_taxon_id": "",
                    "parent_taxon_id": "",
                }

                # Extract rank
                rank_elem = taxon.find("Rank")
                if rank_elem is not None and rank_elem.text:
                    data["rank"] = rank_elem.text

                # Extract parent taxon ID
                parent_elem = taxon.find("ParentTaxId")
                if parent_elem is not None and parent_elem.text:
                    data["parent_taxon_id"] = parent_elem.text

                # Extract species from lineage
                lineage_ex = taxon.find("LineageEx")
                if lineage_ex is not None:
                    for ancestor in lineage_ex.findall("Taxon"):
                        ancestor_rank = ancestor.find("Rank")
                        ancestor_id = ancestor.find("TaxId")
                        if (
                            ancestor_rank is not None
                            and ancestor_rank.text == "species"
                            and ancestor_id is not None
                            and ancestor_id.text
                        ):
                            data["species_taxon_id"] = ancestor_id.text
                            break

                # If taxon is species level, use its own ID
                if not data["species_taxon_id"] and data["rank"] == "species":
                    data["species_taxon_id"] = taxid

                # Extract synonyms from OtherNames
                other_names = taxon.find("OtherNames")
                if other_names is not None:
                    for syn in other_names.findall("Synonym"):
                        if syn.text:
                            data["synonyms"].append(syn.text)
                    for equiv in other_names.findall("EquivalentName"):
                        if equiv.text:
                            data["equivalent_names"].append(equiv.text)
                    for incl in other_names.findall("Includes"):
                        if incl.text:
                            data["includes"].append(incl.text)
                    for name_elem in other_names.findall("Name"):
                        class_cde = name_elem.find("ClassCDE")
                        disp_name = name_elem.find("DispName")
                        if class_cde is not None and disp_name is not None and disp_name.text:
                            if class_cde.text == "misspelling":
                                data["misspellings"].append(disp_name.text)
                            elif class_cde.text == "authority":
                                data["authority"].append(disp_name.text)

                results[taxid] = data

            # Small delay between batches to be nice to NCBI
            if i + batch_size < len(taxon_ids):
                time.sleep(0.5)

        except (requests.RequestException, ET.ParseError) as e:
            logger.warning(f"Failed to fetch NCBI batch starting at {i}: {e}")

    return results


def fetch_ncbi_linkouts(taxon_ids: list[str], batch_size: int = 20) -> dict[str, list[NcbiLinkout]]:
    """Fetch external linkouts from NCBI for multiple taxa.

    Uses the elink API with cmd=llinkslib to get external database links
    like BacDive, BioCyc, LPSN, etc.

    Args:
        taxon_ids: List of NCBI Taxonomy IDs
        batch_size: Number of IDs per request (default 20, smaller for elink)

    Returns:
        Dictionary mapping taxon_id -> list of NcbiLinkout
    """
    results: dict[str, list[NcbiLinkout]] = {}

    for i in range(0, len(taxon_ids), batch_size):
        batch = taxon_ids[i : i + batch_size]
        ids_param = ",".join(batch)

        try:
            response = requests.get(
                NCBI_ELINK_URL,
                params={"dbfrom": "taxonomy", "id": ids_param, "cmd": "llinkslib"},
                timeout=30,
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)

            # Parse each IdUrlSet
            for id_url_set in root.findall(".//IdUrlSet"):
                id_elem = id_url_set.find("Id")
                if id_elem is None or not id_elem.text:
                    continue

                taxid = id_elem.text
                linkouts: list[NcbiLinkout] = []

                for obj_url in id_url_set.findall("ObjUrl"):
                    url_elem = obj_url.find("Url")
                    name_elem = obj_url.find("LinkName")
                    provider_elem = obj_url.find("Provider/Name")

                    if url_elem is not None and url_elem.text:
                        url = url_elem.text
                        # Skip placeholder URLs
                        if "&base.url;" in url:
                            continue

                        linkout: NcbiLinkout = {
                            "provider": provider_elem.text or "" if provider_elem is not None else "",
                            "url": url,
                            "name": name_elem.text or "" if name_elem is not None else "",
                        }
                        linkouts.append(linkout)

                results[taxid] = linkouts

            # Rate limit between batches
            if i + batch_size < len(taxon_ids):
                time.sleep(0.5)

        except (requests.RequestException, ET.ParseError) as e:
            logger.warning(f"Failed to fetch NCBI linkouts batch starting at {i}: {e}")

    return results


def fetch_ncbi_entrez_links(taxon_ids: list[str], batch_size: int = 50) -> dict[str, dict[str, list[str]]]:
    """Fetch Entrez links to other NCBI databases for multiple taxa.

    Uses the elink API with cmd=acheck to find links to Assembly, BioProject, etc.

    Args:
        taxon_ids: List of NCBI Taxonomy IDs
        batch_size: Number of IDs per request

    Returns:
        Dictionary mapping taxon_id -> {db_name: [linked_ids]}
    """
    results: dict[str, dict[str, list[str]]] = {}

    # Databases we're interested in
    target_dbs = {"assembly", "bioproject", "biosample", "nuccore", "genome"}

    for i in range(0, len(taxon_ids), batch_size):
        batch = taxon_ids[i : i + batch_size]

        for taxid in batch:
            if taxid in results:
                continue

            try:
                response = requests.get(
                    NCBI_ELINK_URL,
                    params={"dbfrom": "taxonomy", "id": taxid, "cmd": "acheck"},
                    timeout=15,
                )
                response.raise_for_status()

                root = ET.fromstring(response.content)
                links: dict[str, list[str]] = {}

                for link_info in root.findall(".//LinkInfo"):
                    db_to = link_info.find("DbTo")
                    if db_to is not None and db_to.text in target_dbs and db_to.text not in links:
                        links[db_to.text] = []

                results[taxid] = links

            except (requests.RequestException, ET.ParseError) as e:
                logger.debug(f"Failed to fetch Entrez links for {taxid}: {e}")

        # Rate limit between batches
        if i + batch_size < len(taxon_ids):
            time.sleep(0.3)

    return results


def extract_xrefs_from_linkouts(linkouts: list[NcbiLinkout]) -> list[str]:
    """Extract structured xrefs from NCBI linkouts.

    Parses URLs to extract database identifiers in CURIE format.

    Args:
        linkouts: List of NcbiLinkout from fetch_ncbi_linkouts

    Returns:
        List of xref CURIEs (e.g., "bacdive:13546", "biocyc:GCF_000346065")
    """
    xrefs: list[str] = []

    for linkout in linkouts:
        provider = linkout["provider"].lower()
        url = linkout["url"]

        # BacDive: https://bacdive.dsmz.de/strain/13546
        if "bacdive" in provider or "bacdive.dsmz.de" in url:
            match = re.search(r"/strain/(\d+)", url)
            if match:
                xrefs.append(f"bacdive:{match.group(1)}")

        # BioCyc: http://biocyc.org/organism-summary?object=GCF_000346065
        elif "biocyc" in provider:
            match = re.search(r"object=(GCF_\d+)", url)
            if match:
                xrefs.append(f"biocyc:{match.group(1)}")
            match = re.search(r"object=(\d+)", url)
            if match:
                xrefs.append(f"biocyc:taxon:{match.group(1)}")

        # LPSN: List of Prokaryotic names with Standing in Nomenclature
        elif "lpsn" in provider.lower() or "lpsn.dsmz.de" in url:
            # Extract species name from URL
            match = re.search(r"/species/([^/]+)", url)
            if match:
                xrefs.append(f"lpsn:{match.group(1)}")

    return list(set(xrefs))  # Deduplicate
