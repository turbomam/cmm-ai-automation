#!/usr/bin/env python3
"""Export strain data from all sheets to KGX nodes format.

Consolidates strain data from multiple sheets and exports normalized KGX nodes:
- strains.tsv (27 rows) - culture collection IDs, species taxon IDs
- taxa_and_genomes.tsv (215 rows) - strain names, NCBITaxon IDs, GCA accessions
- growth_preferences.tsv (24 rows) - strain references for linking

Primary identifier strategy:
1. NCBITaxon:{strain_level_taxon_id} - when strain has its own taxon ID
2. bacdive:{bacdive_id} - when no strain-level taxon, but in BacDive
3. dsmz:DSM-{number} - fallback to culture collection

BacDive Enrichment:
- Looks up strains in local MongoDB (bacdive.strains collection)
- Extracts BacDive ID, NCBITaxon ID, and culture collection cross-references
- Fills in missing identifiers from BacDive's comprehensive database

NCBI Entrez Enrichment:
- Fetches synonyms from NCBI Taxonomy for strains with NCBITaxon IDs
- Extracts formal synonyms, equivalent names, and common misspellings

Usage:
    uv run python -m cmm_ai_automation.scripts.export_strains_kgx
    uv run python -m cmm_ai_automation.scripts.export_strains_kgx --no-bacdive --no-ncbi
    uv run python -m cmm_ai_automation.scripts.export_strains_kgx --output output/kgx/strains_nodes.tsv
"""

from __future__ import annotations

import csv
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

import bioregistry
import click
import requests
from dotenv import load_dotenv

if TYPE_CHECKING:
    from pymongo.collection import Collection

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Default paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_STRAINS = PROJECT_ROOT / "data" / "private" / "strains.tsv"
DEFAULT_TAXA_GENOMES = PROJECT_ROOT / "data" / "private" / "taxa_and_genomes.tsv"
DEFAULT_GROWTH_PREFS = PROJECT_ROOT / "data" / "private" / "growth_preferences.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "kgx" / "strains_nodes.tsv"
DEFAULT_EDGES_OUTPUT = PROJECT_ROOT / "output" / "kgx" / "strains_edges.tsv"
DEFAULT_TAXRANK_OUTPUT = PROJECT_ROOT / "output" / "kgx" / "taxrank_nodes.tsv"

# Biolink category for strains
BIOLINK_CATEGORY = "biolink:OrganismTaxon"

# Biolink predicate and category for taxonomic hierarchy edges
SUBCLASS_OF_PREDICATE = "biolink:subclass_of"
TAXON_ASSOCIATION_CATEGORY = "biolink:TaxonToTaxonAssociation"

# NCBI rank string -> TAXRANK CURIE mapping
# See: http://purl.obolibrary.org/obo/taxrank.owl
RANK_TO_TAXRANK: dict[str, str] = {
    "domain": "TAXRANK:0000037",
    "superkingdom": "TAXRANK:0000037",  # NCBI uses superkingdom, maps to domain
    "phylum": "TAXRANK:0000003",
    "class": "TAXRANK:0000002",
    "order": "TAXRANK:0000017",
    "family": "TAXRANK:0000004",
    "genus": "TAXRANK:0000005",
    "species": "TAXRANK:0000006",
    "subspecies": "TAXRANK:0000023",
    "strain": "TAXRANK:0000060",
    # "no rank" has no direct TAXRANK equivalent - leave as empty string
}

# TAXRANK CURIE -> label mapping (for creating TaxonomicRank nodes)
TAXRANK_LABELS: dict[str, str] = {
    "TAXRANK:0000037": "domain",
    "TAXRANK:0000003": "phylum",
    "TAXRANK:0000002": "class",
    "TAXRANK:0000017": "order",
    "TAXRANK:0000004": "family",
    "TAXRANK:0000005": "genus",
    "TAXRANK:0000006": "species",
    "TAXRANK:0000023": "subspecies",
    "TAXRANK:0000060": "strain",
}

# Biolink category for TaxonomicRank nodes
TAXONOMIC_RANK_CATEGORY = "biolink:OntologyClass"

# Culture collection prefix mappings (input format -> bioregistry canonical)
COLLECTION_PREFIX_MAP = {
    "DSM": "dsmz",
    "DSMZ": "dsmz",
    "ATCC": "atcc",
    "JCM": "jcm",
    "NBRC": "nbrc",
    "NCIMB": "ncimb",  # Not in bioregistry but we'll use it
    "LMG": "lmg",  # Not in bioregistry
    "CIP": "cip",  # Not in bioregistry
    "CCM": "ccm",
    "CECT": "cect",
    "IAM": "iam",
    "IFO": "nbrc",  # IFO was merged into NBRC
    "CCUG": "ccug",
    "VKM": "vkm",
    "BCRC": "bcrc",
    "IMET": "imet",
}

# MongoDB connection settings for BacDive
MONGODB_URI = "mongodb://localhost:27017"
BACDIVE_DB = "bacdive"
BACDIVE_COLLECTION = "strains"

# NCBI Entrez settings
NCBI_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
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
    elink_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"

    for i in range(0, len(taxon_ids), batch_size):
        batch = taxon_ids[i : i + batch_size]
        ids_param = ",".join(batch)

        try:
            response = requests.get(
                elink_url,
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
    elink_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"

    # Databases we're interested in
    target_dbs = {"assembly", "bioproject", "biosample", "nuccore", "genome"}

    for i in range(0, len(taxon_ids), batch_size):
        batch = taxon_ids[i : i + batch_size]

        for taxid in batch:
            if taxid in results:
                continue

            try:
                response = requests.get(
                    elink_url,
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
                        and_rank = ancestor.find("Rank")
                        and_id = ancestor.find("TaxId")
                        if and_rank is not None and and_rank.text == "species" and and_id is not None and and_id.text:
                            data["species_taxon_id"] = and_id.text
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


@dataclass
class StrainRecord:
    """Consolidated strain record from multiple sources."""

    # Source tracking
    source_sheet: str
    source_row: int

    # Identity
    id: str | None = None  # Canonical ID (NCBITaxon, bacdive, or collection)
    name: str | None = None  # Full name with strain designation
    scientific_name: str | None = None  # Binomial (genus species)
    strain_designation: str | None = None  # e.g., AM1, KT2440, DSM 16371

    # Taxonomic IDs
    ncbi_taxon_id: str | None = None  # NCBITaxon ID (species or strain level)
    species_taxon_id: str | None = None  # Species-level NCBITaxon
    parent_taxon_id: str | None = None  # Immediate parent in taxonomy

    # Culture collection IDs
    culture_collection_ids: list[str] = field(default_factory=list)
    primary_collection_id: str | None = None  # e.g., DSM:16371

    # BacDive
    bacdive_id: str | None = None

    # Genome
    genome_accession: str | None = None  # GCA_* accession

    # Taxonomic rank (Biolink-aligned)
    has_taxonomic_rank: str | None = None  # e.g., species, strain, subspecies, no rank

    # Additional
    synonyms: list[str] = field(default_factory=list)
    xrefs: list[str] = field(default_factory=list)

    def to_kgx_node(self) -> dict[str, str]:
        """Convert to KGX node row."""
        # Determine canonical ID
        canonical_id = self._determine_canonical_id()

        # Build name
        display_name = self.name or self._build_display_name()

        # Build xrefs list
        all_xrefs = self._collect_xrefs()

        return {
            "id": canonical_id,
            "category": BIOLINK_CATEGORY,
            "name": display_name,
            "ncbi_taxon_id": self.ncbi_taxon_id or "",
            "species_taxon_id": self.species_taxon_id or "",
            "parent_taxon_id": self.parent_taxon_id or "",
            "has_taxonomic_rank": RANK_TO_TAXRANK.get(self.has_taxonomic_rank or "", ""),
            "strain_designation": self.strain_designation or "",
            "bacdive_id": f"bacdive:{self.bacdive_id}" if self.bacdive_id else "",
            "genome_accession": self.genome_accession or "",
            "xrefs": "|".join(all_xrefs) if all_xrefs else "",
            "synonyms": "|".join(self.synonyms) if self.synonyms else "",
            "source_sheet": self.source_sheet,
        }

    def _determine_canonical_id(self) -> str:
        """Determine canonical ID following priority rules."""
        # Priority 1: NCBITaxon (strain-level preferred)
        if self.ncbi_taxon_id:
            taxon_id = self.ncbi_taxon_id
            if not taxon_id.startswith("NCBITaxon:"):
                taxon_id = f"NCBITaxon:{taxon_id}"
            return taxon_id

        # Priority 2: BacDive
        if self.bacdive_id:
            return f"bacdive:{self.bacdive_id}"

        # Priority 3: Culture collection (prefer DSM)
        if self.primary_collection_id:
            return self._normalize_collection_curie(self.primary_collection_id)

        # Fallback: generate from available info
        if self.strain_designation:
            return f"cmm:strain-{self.strain_designation.replace(' ', '-')}"

        return f"cmm:strain-unknown-{self.source_sheet}-{self.source_row}"

    def _build_display_name(self) -> str:
        """Build display name from components."""
        parts = []
        if self.scientific_name:
            parts.append(self.scientific_name)
        if self.strain_designation:
            parts.append(self.strain_designation)
        return " ".join(parts) if parts else "Unknown strain"

    def _collect_xrefs(self) -> list[str]:
        """Collect all cross-references."""
        xrefs = list(self.xrefs)

        # Add culture collection IDs as xrefs
        for cc_id in self.culture_collection_ids:
            curie = self._normalize_collection_curie(cc_id)
            if curie and curie not in xrefs:
                xrefs.append(curie)

        # Add species taxon if different from main taxon
        if self.species_taxon_id and self.species_taxon_id != self.ncbi_taxon_id:
            species_curie = f"NCBITaxon:{self.species_taxon_id}"
            if species_curie not in xrefs:
                xrefs.append(species_curie)

        return sorted(xrefs)

    def _normalize_collection_curie(self, cc_id: str) -> str:
        """Normalize culture collection ID to CURIE format."""
        if ":" in cc_id:
            prefix, local_id = cc_id.split(":", 1)
            prefix = prefix.strip().upper()
            local_id = local_id.strip()
        else:
            # Try to parse "DSM 16371" or "DSM-16371" format
            match = re.match(r"([A-Z]+)[\s-]*(.*)", cc_id.strip())
            if match:
                prefix = match.group(1)
                local_id = match.group(2)
            else:
                return cc_id

        # Map to bioregistry canonical prefix
        canonical_prefix = COLLECTION_PREFIX_MAP.get(prefix, prefix.lower())

        # Validate with bioregistry if available
        if bioregistry.get_resource(canonical_prefix):
            # Use bioregistry-validated format
            return f"{canonical_prefix}:{local_id}"
        else:
            # Use as-is for unregistered prefixes
            return f"{canonical_prefix}:{local_id}"


def generate_query_variants(
    scientific_name: str | None,
    strain_designation: str | None,
    culture_collection_ids: list[str],
) -> list[str]:
    """Generate multiple query variants for fuzzy matching.

    Args:
        scientific_name: Binomial name (e.g., "Methylobacterium aquaticum")
        strain_designation: Strain name (e.g., "DSM 16371", "AM1")
        culture_collection_ids: List of culture collection IDs

    Returns:
        List of query strings to try for matching
    """
    queries = []

    # Full name + strain designation
    if scientific_name and strain_designation:
        queries.append(f"{scientific_name} {strain_designation}")

    # Scientific name only
    if scientific_name:
        queries.append(scientific_name)

    # Strain designation only
    if strain_designation:
        queries.append(strain_designation)

    # Culture collection ID variants
    for cc_id in culture_collection_ids:
        if ":" in cc_id:
            prefix, local_id = cc_id.split(":", 1)
            # Various formats
            queries.extend(
                [
                    f"{prefix} {local_id}",  # DSM 16371
                    f"{prefix}-{local_id}",  # DSM-16371
                    f"{prefix}{local_id}",  # DSM16371
                ]
            )
            # With scientific name
            if scientific_name:
                queries.append(f"{scientific_name} {prefix} {local_id}")

    # Deduplicate while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            unique_queries.append(q)

    return unique_queries


def parse_strains_tsv(path: Path) -> list[StrainRecord]:
    """Parse strains.tsv and return StrainRecord list."""
    records: list[StrainRecord] = []
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return records

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row_num, row in enumerate(reader, start=2):
            # Parse culture collection IDs from both columns
            cc_ids = []
            primary_id = row.get("strain_id", "").strip()
            if primary_id:
                cc_ids.append(primary_id)

            # Additional IDs from culture_collection_ids column
            additional = row.get("culture_collection_ids", "")
            if additional:
                for part in additional.split(";"):
                    part = part.strip()
                    if part and part not in cc_ids:
                        cc_ids.append(part)

            record = StrainRecord(
                source_sheet="strains.tsv",
                source_row=row_num,
                scientific_name=row.get("scientific_name", "").strip() or None,
                strain_designation=row.get("strain_designation", "").strip() or None,
                species_taxon_id=row.get("species_taxon_id", "").strip() or None,
                culture_collection_ids=cc_ids,
                primary_collection_id=primary_id or None,
                synonyms=[s.strip() for s in row.get("Name synonyms", "").split(";") if s.strip()],
            )

            # Build name from scientific_name + strain_designation
            if record.scientific_name:
                if record.strain_designation:
                    record.name = f"{record.scientific_name} {record.strain_designation}"
                else:
                    record.name = record.scientific_name

            records.append(record)

    logger.info(f"Parsed {len(records)} records from strains.tsv")
    return records


def parse_taxa_and_genomes_tsv(path: Path) -> list[StrainRecord]:
    """Parse taxa_and_genomes.tsv and return StrainRecord list."""
    records: list[StrainRecord] = []
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return records

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row_num, row in enumerate(reader, start=2):
            strain_name = row.get("Strain name", "").strip()
            ncbi_taxon = row.get("NCBITaxon id", "").strip()
            genome_id = row.get("Genome identifier (GenBank, IMG etc)", "").strip()

            if not strain_name and not ncbi_taxon:
                continue

            # Parse strain name to extract scientific name and designation
            scientific_name = None
            strain_designation = None
            if strain_name:
                # Try to split "Genus species strain_designation"
                parts = strain_name.split()
                if len(parts) >= 2:
                    scientific_name = " ".join(parts[:2])  # Genus species
                    if len(parts) > 2:
                        strain_designation = " ".join(parts[2:])

            record = StrainRecord(
                source_sheet="taxa_and_genomes.tsv",
                source_row=row_num,
                name=strain_name or None,
                scientific_name=scientific_name,
                strain_designation=strain_designation,
                ncbi_taxon_id=ncbi_taxon or None,
                genome_accession=genome_id or None,
            )

            records.append(record)

    logger.info(f"Parsed {len(records)} records from taxa_and_genomes.tsv")
    return records


def parse_growth_preferences_tsv(path: Path) -> list[StrainRecord]:
    """Parse growth_preferences.tsv for additional strain references."""
    records: list[StrainRecord] = []
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return records

    seen_strains: set[str] = set()

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row_num, row in enumerate(reader, start=2):
            strain_id = row.get("strain id", "").strip()
            full_name = row.get("scientific name with strain id", "").strip()

            # Skip empty or duplicate
            key = strain_id or full_name
            if not key or key in seen_strains:
                continue
            seen_strains.add(key)

            # Parse the full name
            scientific_name = None
            strain_designation = None
            cc_ids = []

            if strain_id:
                # Could be "DSM:1337" or "KT2440"
                if ":" in strain_id:
                    cc_ids.append(strain_id)
                else:
                    strain_designation = strain_id

            if full_name:
                parts = full_name.split()
                if len(parts) >= 2:
                    scientific_name = " ".join(parts[:2])
                    if len(parts) > 2:
                        strain_designation = " ".join(parts[2:])

            record = StrainRecord(
                source_sheet="growth_preferences.tsv",
                source_row=row_num,
                name=full_name or None,
                scientific_name=scientific_name,
                strain_designation=strain_designation,
                culture_collection_ids=cc_ids,
                primary_collection_id=cc_ids[0] if cc_ids else None,
            )

            records.append(record)

    logger.info(f"Parsed {len(records)} unique strains from growth_preferences.tsv")
    return records


def consolidate_strains(all_records: list[StrainRecord]) -> list[StrainRecord]:
    """Consolidate duplicate strain records.

    Merges records that appear to refer to the same strain based on:
    - Matching NCBITaxon IDs
    - Matching culture collection IDs
    - Matching names (case-insensitive)

    Uses both primary key lookup AND secondary name-based lookup to catch
    cases where one sheet has an ID and another has the same entity by name only.

    Args:
        all_records: List of strain records from all sources

    Returns:
        Deduplicated list of consolidated records
    """
    consolidated: dict[str, StrainRecord] = {}
    # Secondary index: name -> primary key (to find records by name even when they have IDs)
    name_to_key: dict[str, str] = {}

    for record in all_records:
        # Generate primary key for deduplication
        primary_key = None
        if record.ncbi_taxon_id:
            primary_key = f"ncbi:{record.ncbi_taxon_id}"
        elif record.primary_collection_id:
            primary_key = f"cc:{record.primary_collection_id}"
        elif record.name:
            primary_key = f"name:{record.name.lower()}"
        else:
            primary_key = f"row:{record.source_sheet}:{record.source_row}"

        # Also check if we can find this record by name (secondary lookup)
        name_key = record.name.lower() if record.name else None
        existing_key = None

        # First try primary key match
        if primary_key in consolidated:
            existing_key = primary_key
        # Then try secondary name lookup (catches mismatched ID vs name-only records)
        elif name_key and name_key in name_to_key:
            existing_key = name_to_key[name_key]
            logger.debug(f"Found by name lookup: '{record.name}' matches existing record with key {existing_key}")

        if existing_key:
            # Merge into existing record
            existing = consolidated[existing_key]
            _merge_records(existing, record)

            # Check if incoming record's name points to a DIFFERENT record
            # (e.g., strains.tsv created record by name, taxa_and_genomes.tsv has same name + ncbi_id
            # pointing to different record - need to merge both)
            if name_key and name_key in name_to_key and name_to_key[name_key] != existing_key:
                other_key = name_to_key[name_key]
                if other_key in consolidated:
                    other_record = consolidated[other_key]
                    logger.debug(f"Cross-merge: '{record.name}' links {other_key} to {existing_key}")
                    _merge_records(existing, other_record)
                    del consolidated[other_key]
                    # Update name index to point to surviving record
                    name_to_key[name_key] = existing_key

            # Register incoming record's name in name index
            if name_key and name_key not in name_to_key:
                name_to_key[name_key] = existing_key
        else:
            consolidated[primary_key] = record
            # Register in name index
            if name_key:
                name_to_key[name_key] = primary_key

    result = list(consolidated.values())
    logger.info(f"Consolidated {len(all_records)} records into {len(result)} unique strains")
    return result


def _merge_records(target: StrainRecord, source: StrainRecord) -> None:
    """Merge source record into target, filling in missing fields."""
    if not target.name and source.name:
        target.name = source.name
    if not target.scientific_name and source.scientific_name:
        target.scientific_name = source.scientific_name
    if not target.strain_designation and source.strain_designation:
        target.strain_designation = source.strain_designation
    if not target.ncbi_taxon_id and source.ncbi_taxon_id:
        target.ncbi_taxon_id = source.ncbi_taxon_id
    if not target.species_taxon_id and source.species_taxon_id:
        target.species_taxon_id = source.species_taxon_id
    if not target.parent_taxon_id and source.parent_taxon_id:
        target.parent_taxon_id = source.parent_taxon_id
    if not target.bacdive_id and source.bacdive_id:
        target.bacdive_id = source.bacdive_id
    if not target.genome_accession and source.genome_accession:
        target.genome_accession = source.genome_accession
    if not target.has_taxonomic_rank and source.has_taxonomic_rank:
        target.has_taxonomic_rank = source.has_taxonomic_rank

    # Merge collection IDs
    for cc_id in source.culture_collection_ids:
        if cc_id not in target.culture_collection_ids:
            target.culture_collection_ids.append(cc_id)

    # Merge synonyms
    for syn in source.synonyms:
        if syn not in target.synonyms:
            target.synonyms.append(syn)

    # Merge xrefs
    for xref in source.xrefs:
        if xref not in target.xrefs:
            target.xrefs.append(xref)


def infer_species_from_bacdive(records: list[StrainRecord]) -> int:
    """Use BacDive NCBI taxon ID as species_taxon_id for strains.

    BacDive typically provides species-level NCBI taxon IDs for strains.
    If a record has a bacdive_id but no species_taxon_id, and is at strain rank,
    use its ncbi_taxon_id as the species_taxon_id (since it came from BacDive).

    Args:
        records: List of strain records to update

    Returns:
        Number of records whose species_taxon_id was set from BacDive
    """
    inferred = 0
    for record in records:
        if (
            record.bacdive_id
            and record.ncbi_taxon_id
            and not record.species_taxon_id
            and record.has_taxonomic_rank == "strain"
        ):
            # BacDive NCBI taxon IDs are typically species-level
            record.species_taxon_id = record.ncbi_taxon_id.replace("NCBITaxon:", "")
            inferred += 1
    return inferred


def infer_species_from_self(records: list[StrainRecord]) -> int:
    """Infer species_taxon_id for species-level records.

    If a record is at species level (rank == 'species') and has an NCBI taxon ID
    but no species_taxon_id, use its own taxon ID as the species_taxon_id.

    This handles cases where NCBI LineageEx doesn't include the species
    when the taxon itself IS the species.

    Args:
        records: List of strain records to update

    Returns:
        Number of records whose species_taxon_id was set
    """
    inferred = 0
    for record in records:
        if record.ncbi_taxon_id and not record.species_taxon_id and record.has_taxonomic_rank == "species":
            record.species_taxon_id = record.ncbi_taxon_id.replace("NCBITaxon:", "")
            inferred += 1
    return inferred


def infer_taxonomic_rank(records: list[StrainRecord]) -> int:
    """Infer taxonomic rank for records that don't have NCBI rank data.

    NCBI's rank is the authoritative source. We only infer a rank when:
    - The record has no has_taxonomic_rank (no NCBI data)
    - We have evidence it's a strain (strain_designation or bacdive_id)

    If NCBI says it's a species, we trust that even if we have strain_designation.
    The strain_designation in that case refers to a type strain of the species,
    not a separate strain-level taxon.

    Args:
        records: List of strain records to update

    Returns:
        Number of records whose rank was inferred
    """
    inferred = 0
    for record in records:
        # Only infer rank if we don't already have one from NCBI
        if not record.has_taxonomic_rank:
            # Evidence that this is a strain, not just a species
            is_strain = bool(record.strain_designation) or bool(record.bacdive_id)

            if is_strain:
                record.has_taxonomic_rank = "strain"
                logger.debug(
                    f"Inferred rank for {record.name}: strain "
                    f"(has {'strain_designation' if record.strain_designation else 'bacdive_id'})"
                )
            else:
                # Default to species if no strain evidence
                record.has_taxonomic_rank = "species"
                logger.debug(f"Inferred rank for {record.name}: species (no strain evidence)")
            inferred += 1

    return inferred


def deduplicate_by_canonical_id(records: list[StrainRecord]) -> list[StrainRecord]:
    """Deduplicate records by their canonical ID after enrichment.

    This runs after BacDive/NCBI enrichment when records may have acquired
    new identifiers that reveal they are the same entity.

    Args:
        records: List of enriched strain records

    Returns:
        Deduplicated list with merged records
    """
    # Group by canonical ID
    by_canonical: dict[str, list[StrainRecord]] = {}

    for record in records:
        # Compute canonical ID using the same logic as to_kgx_node
        canonical_id = record._determine_canonical_id()
        if canonical_id not in by_canonical:
            by_canonical[canonical_id] = []
        by_canonical[canonical_id].append(record)

    # Merge duplicates
    deduplicated: list[StrainRecord] = []
    merged_count = 0

    for _canonical_id, group in by_canonical.items():
        if len(group) == 1:
            deduplicated.append(group[0])
        else:
            # Merge all records in the group into the first one
            target = group[0]
            for source in group[1:]:
                _merge_records(target, source)
                merged_count += 1
            deduplicated.append(target)

    if merged_count > 0:
        logger.info(
            f"Post-enrichment dedup: merged {merged_count} duplicates, {len(records)} -> {len(deduplicated)} records"
        )

    return deduplicated


# =============================================================================
# BacDive Enrichment Functions
# =============================================================================


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

    Args:
        collection: MongoDB collection
        search_id: Culture collection ID in format "PREFIX NUMBER" (e.g., "ATCC 43883")

    Returns:
        BacDive document or None
    """
    # Use regex query for efficient database-side filtering
    # The field contains comma-separated IDs like "DSM 1337, ATCC 43645, NCIMB 9399"
    # Match as complete token to avoid false positives (e.g., "DSM 1" matching "DSM 11")
    # Use word boundaries or comma separators to ensure exact match
    escaped_id = re.escape(search_id)
    # Pattern: (start of string OR comma+whitespace) + ID + (comma OR end of string)
    pattern = f"(^|,\\s*){escaped_id}(\\s*,|$)"
    
    result: dict[str, Any] | None = collection.find_one(
        {"External links.culture collection no.": {"$regex": pattern, "$options": "i"}}
    )
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


def enrich_strains_with_ncbi(records: list[StrainRecord]) -> tuple[int, int, int, int, int]:
    """Enrich strain records with NCBI Taxonomy data using batch API.

    Fetches synonyms, lineage (species/parent taxon), rank, and external linkouts
    from NCBI Entrez for strains that have NCBITaxon IDs.

    Args:
        records: List of strain records to enrich

    Returns:
        Tuple of (synonym_enriched, species_enriched, parent_enriched, linkout_enriched, total_with_taxon)
    """
    # Collect taxon IDs for batch fetch
    taxon_id_to_records: dict[str, list[StrainRecord]] = {}
    for record in records:
        if record.ncbi_taxon_id:
            taxid = record.ncbi_taxon_id.replace("NCBITaxon:", "")
            if taxid not in taxon_id_to_records:
                taxon_id_to_records[taxid] = []
            taxon_id_to_records[taxid].append(record)

    taxon_ids = list(taxon_id_to_records.keys())
    with_taxon = len(taxon_ids)

    if not taxon_ids:
        return 0, 0, 0, 0, 0

    # Batch fetch taxonomy data
    logger.info(f"Fetching NCBI taxonomy data for {len(taxon_ids)} taxa in batches...")
    ncbi_data_map = fetch_ncbi_batch(taxon_ids)

    # Batch fetch linkouts
    logger.info(f"Fetching NCBI linkouts for {len(taxon_ids)} taxa...")
    linkouts_map = fetch_ncbi_linkouts(taxon_ids)

    # Apply enrichment
    synonym_enriched = 0
    species_enriched = 0
    parent_enriched = 0
    linkout_enriched = 0

    for taxid, record_list in taxon_id_to_records.items():
        ncbi_data = ncbi_data_map.get(taxid)
        linkouts = linkouts_map.get(taxid, [])

        for record in record_list:
            if ncbi_data:
                # Set taxonomic rank - NCBI is authoritative, always overwrite
                ncbi_rank = ncbi_data.get("rank", "")
                if isinstance(ncbi_rank, str) and ncbi_rank:
                    record.has_taxonomic_rank = ncbi_rank

                # Set species_taxon_id from lineage
                if not record.species_taxon_id and ncbi_data["species_taxon_id"]:
                    record.species_taxon_id = ncbi_data["species_taxon_id"]
                    species_enriched += 1

                # Set parent_taxon_id from lineage
                if not record.parent_taxon_id and ncbi_data["parent_taxon_id"]:
                    record.parent_taxon_id = ncbi_data["parent_taxon_id"]
                    parent_enriched += 1

                # Add synonyms
                added_syn = False
                for synonym in ncbi_data["synonyms"]:
                    if synonym not in record.synonyms:
                        record.synonyms.append(synonym)
                        added_syn = True
                for equiv in ncbi_data["equivalent_names"]:
                    if equiv not in record.synonyms:
                        record.synonyms.append(equiv)
                        added_syn = True
                for misspelling in ncbi_data["misspellings"]:
                    if misspelling not in record.synonyms:
                        record.synonyms.append(misspelling)
                        added_syn = True
                for includes in ncbi_data["includes"]:
                    if includes not in record.synonyms:
                        record.synonyms.append(includes)
                        added_syn = True
                if added_syn:
                    synonym_enriched += 1

            # Extract xrefs from linkouts
            if linkouts:
                xrefs = extract_xrefs_from_linkouts(linkouts)
                added_xref = False
                for xref in xrefs:
                    if xref not in record.xrefs:
                        record.xrefs.append(xref)
                        added_xref = True
                    # Also extract BacDive ID if not set
                    if xref.startswith("bacdive:") and not record.bacdive_id:
                        record.bacdive_id = xref.replace("bacdive:", "")
                if added_xref:
                    linkout_enriched += 1

    return synonym_enriched, species_enriched, parent_enriched, linkout_enriched, with_taxon


@dataclass
class EnrichmentStats:
    """Statistics from an enrichment round."""

    records_processed: int = 0
    records_enriched: int = 0
    new_ncbi_ids: int = 0
    new_bacdive_ids: int = 0
    new_species_ids: int = 0
    new_parent_ids: int = 0
    new_synonyms: int = 0
    new_xrefs: int = 0

    def __str__(self) -> str:
        return (
            f"processed={self.records_processed}, enriched={self.records_enriched}, "
            f"ncbi+={self.new_ncbi_ids}, bacdive+={self.new_bacdive_ids}"
        )


class IterativeEnrichmentPipeline:
    """Iterative enrichment pipeline for strain records.

    Runs multiple rounds of enrichment, using results from each round
    to discover new data sources for subsequent rounds.

    Workflow:
        Round 1: Parse input sheets, consolidate duplicates
        Round 2: BacDive enrichment (first pass) - match by name
        Round 3: NCBI enrichment - get lineage, synonyms, external linkouts
        Round 4: BacDive enrichment (second pass) - use NCBI linkouts
        Round 5: PydanticAI reconciliation for ambiguous matches (optional)
        Round 6: Final consolidation and export
    """

    def __init__(
        self,
        strains_tsv: Path,
        taxa_genomes_tsv: Path,
        growth_prefs_tsv: Path,
        bacdive_collection: Collection | None = None,
        use_pydanticai: bool = False,
        skip_ncbi: bool = False,
        verbose: bool = False,
    ):
        self.strains_tsv = strains_tsv
        self.taxa_genomes_tsv = taxa_genomes_tsv
        self.growth_prefs_tsv = growth_prefs_tsv
        self.bacdive_collection = bacdive_collection
        self.use_pydanticai = use_pydanticai
        self.skip_ncbi = skip_ncbi
        self.verbose = verbose

        self.records: list[StrainRecord] = []
        self.round_stats: list[tuple[str, EnrichmentStats]] = []
        self._discovered_bacdive_ids: set[str] = set()

    def run(self) -> list[StrainRecord]:
        """Execute the full iterative enrichment pipeline.

        Returns:
            List of fully enriched StrainRecord objects
        """
        click.echo("=== Iterative Strain Enrichment Pipeline ===\n")

        # Round 1: Parse and consolidate
        self._round_1_parse()

        # Round 2: BacDive first pass
        if self.bacdive_collection is not None:
            self._round_2_bacdive_first_pass()

        # Round 3: NCBI enrichment with linkouts
        if not self.skip_ncbi:
            self._round_3_ncbi_enrichment()
        else:
            click.echo("Round 3: NCBI enrichment skipped (--no-ncbi)\n")

        # Round 4: BacDive second pass using NCBI linkouts
        if self.bacdive_collection is not None and not self.skip_ncbi:
            self._round_4_bacdive_from_linkouts()

        # Round 5: PydanticAI reconciliation (optional)
        if self.use_pydanticai:
            self._round_5_pydanticai_reconciliation()

        # Round 6: Final inference and deduplication
        self._round_6_finalize()

        # Print summary
        self._print_pipeline_summary()

        return self.records

    def _round_1_parse(self) -> None:
        """Round 1: Parse input sheets and consolidate duplicates."""
        click.echo("Round 1: Parsing input sheets")
        stats = EnrichmentStats()

        all_records: list[StrainRecord] = []

        records = parse_strains_tsv(self.strains_tsv)
        all_records.extend(records)
        click.echo(f"  - {self.strains_tsv.name}: {len(records)} records")

        records = parse_taxa_and_genomes_tsv(self.taxa_genomes_tsv)
        all_records.extend(records)
        click.echo(f"  - {self.taxa_genomes_tsv.name}: {len(records)} records")

        records = parse_growth_preferences_tsv(self.growth_prefs_tsv)
        all_records.extend(records)
        click.echo(f"  - {self.growth_prefs_tsv.name}: {len(records)} records")

        stats.records_processed = len(all_records)

        # Consolidate
        self.records = consolidate_strains(all_records)
        stats.records_enriched = len(self.records)

        click.echo(f"  Consolidated: {stats.records_processed} -> {len(self.records)} unique strains\n")
        self.round_stats.append(("Parse & Consolidate", stats))

    def _round_2_bacdive_first_pass(self) -> None:
        """Round 2: BacDive enrichment by name matching."""
        assert self.bacdive_collection is not None, "BacDive collection required for Round 2"  # nosec B101
        click.echo("Round 2: BacDive enrichment (first pass - name matching)")
        stats = EnrichmentStats()

        before_bacdive = sum(1 for r in self.records if r.bacdive_id)
        before_ncbi = sum(1 for r in self.records if r.ncbi_taxon_id)

        enriched, total = enrich_strains_with_bacdive(self.records, self.bacdive_collection)

        stats.records_processed = total
        stats.records_enriched = enriched
        stats.new_bacdive_ids = sum(1 for r in self.records if r.bacdive_id) - before_bacdive
        stats.new_ncbi_ids = sum(1 for r in self.records if r.ncbi_taxon_id) - before_ncbi

        # Track discovered BacDive IDs
        for r in self.records:
            if r.bacdive_id:
                self._discovered_bacdive_ids.add(r.bacdive_id)

        click.echo(f"  Enriched: {enriched}/{total} strains")
        click.echo(f"  New BacDive IDs: +{stats.new_bacdive_ids}")
        click.echo(f"  New NCBI IDs: +{stats.new_ncbi_ids}\n")
        self.round_stats.append(("BacDive (name match)", stats))

    def _round_3_ncbi_enrichment(self) -> None:
        """Round 3: NCBI batch enrichment with linkouts."""
        click.echo("Round 3: NCBI Taxonomy enrichment (batch mode)")
        stats = EnrichmentStats()

        before_species = sum(1 for r in self.records if r.species_taxon_id)
        before_parent = sum(1 for r in self.records if r.parent_taxon_id)
        before_synonyms = sum(len(r.synonyms) for r in self.records)
        before_xrefs = sum(len(r.xrefs) for r in self.records)

        syn, species, parent, linkout, total = enrich_strains_with_ncbi(self.records)

        stats.records_processed = total
        stats.records_enriched = syn + species + parent + linkout
        stats.new_species_ids = sum(1 for r in self.records if r.species_taxon_id) - before_species
        stats.new_parent_ids = sum(1 for r in self.records if r.parent_taxon_id) - before_parent
        stats.new_synonyms = sum(len(r.synonyms) for r in self.records) - before_synonyms
        stats.new_xrefs = sum(len(r.xrefs) for r in self.records) - before_xrefs

        # Track any new BacDive IDs discovered via linkouts
        new_bacdive_from_linkouts = 0
        for r in self.records:
            if r.bacdive_id and r.bacdive_id not in self._discovered_bacdive_ids:
                self._discovered_bacdive_ids.add(r.bacdive_id)
                new_bacdive_from_linkouts += 1
        stats.new_bacdive_ids = new_bacdive_from_linkouts

        click.echo(f"  Processed: {total} taxa")
        click.echo(f"  New species_taxon_id: +{stats.new_species_ids}")
        click.echo(f"  New parent_taxon_id: +{stats.new_parent_ids}")
        click.echo(f"  New synonyms: +{stats.new_synonyms}")
        click.echo(f"  New xrefs (from linkouts): +{stats.new_xrefs}")
        click.echo(f"  New BacDive IDs (from linkouts): +{stats.new_bacdive_ids}\n")
        self.round_stats.append(("NCBI Taxonomy", stats))

    def _round_4_bacdive_from_linkouts(self) -> None:
        """Round 4: BacDive second pass using IDs from NCBI linkouts."""
        click.echo("Round 4: BacDive enrichment (second pass - from NCBI linkouts)")
        stats = EnrichmentStats()

        # Find records that got BacDive IDs from linkouts but weren't enriched
        records_needing_enrichment = [
            r
            for r in self.records
            if r.bacdive_id and not r.xrefs  # Has BacDive ID but no xrefs yet
        ]

        if not records_needing_enrichment:
            click.echo("  No new BacDive IDs to enrich\n")
            self.round_stats.append(("BacDive (linkout)", stats))
            return

        before_xrefs = sum(len(r.xrefs) for r in self.records)

        # Enrich these specific records by BacDive ID
        enriched_count = 0
        for record in records_needing_enrichment:
            if self._enrich_single_by_bacdive_id(record):
                enriched_count += 1

        stats.records_processed = len(records_needing_enrichment)
        stats.records_enriched = enriched_count
        stats.new_xrefs = sum(len(r.xrefs) for r in self.records) - before_xrefs

        click.echo(f"  Enriched: {enriched_count}/{len(records_needing_enrichment)} strains")
        click.echo(f"  New xrefs: +{stats.new_xrefs}\n")
        self.round_stats.append(("BacDive (linkout)", stats))

    def _enrich_single_by_bacdive_id(self, record: StrainRecord) -> bool:
        """Enrich a single record by its BacDive ID."""
        if not record.bacdive_id or self.bacdive_collection is None:
            return False

        try:
            bacdive_id = int(record.bacdive_id)
        except ValueError:
            return False

        doc = self.bacdive_collection.find_one({"bacdive_id": bacdive_id})
        if not doc:
            return False

        # Extract culture collection IDs
        cc_ids = doc.get("culture_collection_ids", [])
        for cc_id in cc_ids:
            if cc_id not in record.culture_collection_ids:
                record.culture_collection_ids.append(cc_id)
            # Also add as xref (culture collection IDs are already in CURIE-like format)
            if cc_id and cc_id not in record.xrefs:
                record.xrefs.append(cc_id)

        return True

    def _round_5_pydanticai_reconciliation(self) -> None:
        """Round 5: PydanticAI reconciliation for ambiguous matches."""
        click.echo("Round 5: PydanticAI reconciliation")
        stats = EnrichmentStats()

        # Find candidates for reconciliation:
        # - Records without BacDive ID (might have matches we missed)
        # - Records with genus synonymy issues (Sinorhizobium/Ensifer)
        candidates = [r for r in self.records if not r.bacdive_id]

        if not candidates:
            click.echo("  No candidates for LLM reconciliation\n")
            self.round_stats.append(("PydanticAI", stats))
            return

        click.echo(f"  Found {len(candidates)} candidates for reconciliation")
        click.echo("  (PydanticAI reconciliation not yet implemented - see issue #74)\n")

        # TODO: Implement PydanticAI reconciliation
        # 1. For each candidate, search BacDive by scientific name
        # 2. Use StrainReconciler to compare candidates
        # 3. If high-confidence match, add bacdive_id
        # 4. Generate same_as edges for KGX clique merge

        self.round_stats.append(("PydanticAI", stats))

    def _round_6_finalize(self) -> None:
        """Round 6: Final inference and deduplication."""
        click.echo("Round 6: Finalizing")
        stats = EnrichmentStats()

        # Infer taxonomic ranks only for records without NCBI rank
        rank_inferred = infer_taxonomic_rank(self.records)
        click.echo(f"  Ranks inferred (no NCBI data): {rank_inferred}")

        # Infer species from BacDive for strains
        species_bacdive = infer_species_from_bacdive(self.records)
        click.echo(f"  Species from BacDive: {species_bacdive}")

        # Infer species from self for species-level records
        species_self = infer_species_from_self(self.records)
        click.echo(f"  Species from self: {species_self}")

        # Final deduplication
        pre_dedup = len(self.records)
        self.records = deduplicate_by_canonical_id(self.records)

        stats.records_processed = pre_dedup
        stats.records_enriched = len(self.records)

        if len(self.records) < pre_dedup:
            click.echo(f"  Deduplication: {pre_dedup} -> {len(self.records)}")

        click.echo()
        self.round_stats.append(("Finalize", stats))

    def _print_pipeline_summary(self) -> None:
        """Print summary of all enrichment rounds."""
        click.echo("=" * 60)
        click.echo("PIPELINE SUMMARY")
        click.echo("=" * 60)

        for round_name, stats in self.round_stats:
            click.echo(f"{round_name}: {stats}")

        click.echo()
        print_validation_summary(self.records)


def compute_validation_summary(records: list[StrainRecord]) -> dict[str, dict[str, int | float]]:
    """Compute field completeness statistics for validation.

    Args:
        records: List of strain records

    Returns:
        Dictionary with field names and their completeness counts
    """
    total = len(records)
    summary: dict[str, dict[str, int | float]] = {}

    # Define fields to check
    fields = [
        ("ncbi_taxon_id", lambda r: bool(r.ncbi_taxon_id)),
        ("species_taxon_id", lambda r: bool(r.species_taxon_id)),
        ("parent_taxon_id", lambda r: bool(r.parent_taxon_id)),
        ("has_taxonomic_rank", lambda r: bool(r.has_taxonomic_rank)),
        ("bacdive_id", lambda r: bool(r.bacdive_id)),
        ("strain_designation", lambda r: bool(r.strain_designation)),
        ("genome_accession", lambda r: bool(r.genome_accession)),
        ("synonyms", lambda r: len(r.synonyms) > 0),
        ("xrefs", lambda r: len(r.xrefs) > 0 or len(r.culture_collection_ids) > 0),
    ]

    for field_name, check_fn in fields:
        present = sum(1 for r in records if check_fn(r))
        summary[field_name] = {
            "present": present,
            "missing": total - present,
            "total": total,
            "percent": round(100 * present / total, 1) if total > 0 else 0,
        }

    return summary


def print_validation_summary(records: list[StrainRecord]) -> None:
    """Print a validation summary showing field completeness.

    Args:
        records: List of strain records
    """
    summary = compute_validation_summary(records)
    total = len(records)

    click.echo("=" * 60)
    click.echo("DATA COMPLETENESS VALIDATION")
    click.echo("=" * 60)
    click.echo(f"Total records: {total}\n")

    click.echo(f"{'Field':<20} {'Present':>8} {'Missing':>8} {'Percent':>8}")
    click.echo("-" * 48)

    for field_name, stats in summary.items():
        pct = stats["percent"]
        status = "OK" if pct == 100 else ("WARN" if pct >= 80 else "LOW")
        click.echo(f"{field_name:<20} {stats['present']:>8} {stats['missing']:>8} {pct:>7.1f}%  [{status}]")

    click.echo("-" * 48)

    # Show records missing critical fields
    missing_ncbi = [r for r in records if not r.ncbi_taxon_id]
    missing_species = [r for r in records if not r.species_taxon_id]
    missing_parent = [r for r in records if not r.parent_taxon_id]

    if missing_ncbi:
        click.echo(f"\nRecords missing ncbi_taxon_id ({len(missing_ncbi)}):")
        for r in missing_ncbi[:5]:
            click.echo(f"  - {r.name or r.strain_designation or 'Unknown'}")
        if len(missing_ncbi) > 5:
            click.echo(f"  ... and {len(missing_ncbi) - 5} more")

    if missing_species:
        click.echo(f"\nRecords missing species_taxon_id ({len(missing_species)}):")
        for r in missing_species[:5]:
            click.echo(f"  - {r.name or r.strain_designation or 'Unknown'} (ncbi: {r.ncbi_taxon_id or 'N/A'})")
        if len(missing_species) > 5:
            click.echo(f"  ... and {len(missing_species) - 5} more")

    if missing_parent:
        click.echo(f"\nRecords missing parent_taxon_id ({len(missing_parent)}):")
        for r in missing_parent[:5]:
            click.echo(f"  - {r.name or r.strain_designation or 'Unknown'} (ncbi: {r.ncbi_taxon_id or 'N/A'})")
        if len(missing_parent) > 5:
            click.echo(f"  ... and {len(missing_parent) - 5} more")

    click.echo("=" * 60 + "\n")


def export_kgx_nodes(records: list[StrainRecord], output_path: Path) -> None:
    """Export strain records to KGX nodes.tsv format.

    Args:
        records: List of consolidated strain records
        output_path: Path to output TSV file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "category",
        "name",
        "strain_designation",
        "ncbi_taxon_id",
        "species_taxon_id",
        "parent_taxon_id",
        "has_taxonomic_rank",
        "bacdive_id",
        "genome_accession",
        "xrefs",
        "synonyms",
        "source_sheet",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()

        for record in records:
            row = record.to_kgx_node()
            writer.writerow(row)

    logger.info(f"Exported {len(records)} strain nodes to {output_path}")


def export_kgx_edges(records: list[StrainRecord], output_path: Path) -> int:
    """Export taxonomic hierarchy edges to KGX edges.tsv format.

    Generates subclass_of edges connecting strains to their parent species taxon.
    Only produces edges when a strain has both:
    - An NCBI taxon ID (or other canonical ID)
    - A species_taxon_id that differs from its primary ID

    Args:
        records: List of consolidated strain records
        output_path: Path to output TSV file

    Returns:
        Number of edges exported
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "subject",
        "predicate",
        "object",
        "category",
    ]

    edge_count = 0
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()

        for record in records:
            # Get the canonical ID for this strain
            node = record.to_kgx_node()
            subject_id = node["id"]

            # Only create edge if we have a species taxon and it's different
            if record.species_taxon_id:
                species_curie = record.species_taxon_id
                if not species_curie.startswith("NCBITaxon:"):
                    species_curie = f"NCBITaxon:{species_curie}"

                # Don't create self-loops
                if species_curie != subject_id:
                    edge_id = f"{subject_id}--{SUBCLASS_OF_PREDICATE}--{species_curie}"
                    writer.writerow(
                        {
                            "id": edge_id,
                            "subject": subject_id,
                            "predicate": SUBCLASS_OF_PREDICATE,
                            "object": species_curie,
                            "category": TAXON_ASSOCIATION_CATEGORY,
                        }
                    )
                    edge_count += 1

    logger.info(f"Exported {edge_count} taxonomic hierarchy edges to {output_path}")
    return edge_count


def export_taxrank_nodes(records: list[StrainRecord], output_path: Path) -> int:
    """Export TaxonomicRank nodes to provide CURIE→label mapping.

    Creates nodes for each TAXRANK term used by the strain records,
    enabling lookup of rank labels by CURIE in the knowledge graph.

    Args:
        records: List of strain records (to determine which ranks are used)
        output_path: Path to output TSV file

    Returns:
        Number of rank nodes exported
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect unique ranks used
    used_ranks: set[str] = set()
    for record in records:
        if record.has_taxonomic_rank:
            taxrank_curie = RANK_TO_TAXRANK.get(record.has_taxonomic_rank, "")
            if taxrank_curie:
                used_ranks.add(taxrank_curie)

    fieldnames = ["id", "category", "name"]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()

        for taxrank_curie in sorted(used_ranks):
            label = TAXRANK_LABELS.get(taxrank_curie, "")
            writer.writerow(
                {
                    "id": taxrank_curie,
                    "category": TAXONOMIC_RANK_CATEGORY,
                    "name": label,
                }
            )

    logger.info(f"Exported {len(used_ranks)} TaxonomicRank nodes to {output_path}")
    return len(used_ranks)


@click.command()
@click.option(
    "--strains-tsv",
    type=click.Path(exists=False, path_type=Path),
    default=DEFAULT_STRAINS,
    help="Path to strains.tsv",
)
@click.option(
    "--taxa-genomes-tsv",
    type=click.Path(exists=False, path_type=Path),
    default=DEFAULT_TAXA_GENOMES,
    help="Path to taxa_and_genomes.tsv",
)
@click.option(
    "--growth-prefs-tsv",
    type=click.Path(exists=False, path_type=Path),
    default=DEFAULT_GROWTH_PREFS,
    help="Path to growth_preferences.tsv",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT,
    help="Output KGX nodes TSV file",
)
@click.option(
    "--edges-output",
    type=click.Path(path_type=Path),
    default=DEFAULT_EDGES_OUTPUT,
    help="Output KGX edges TSV file (taxonomic hierarchy)",
)
@click.option(
    "--taxrank-output",
    type=click.Path(path_type=Path),
    default=DEFAULT_TAXRANK_OUTPUT,
    help="Output KGX nodes TSV file for TaxonomicRank terms (CURIE→label)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Parse and consolidate but don't write output",
)
@click.option(
    "--no-bacdive",
    is_flag=True,
    help="Skip BacDive enrichment (faster, no MongoDB required)",
)
@click.option(
    "--no-ncbi",
    is_flag=True,
    help="Skip NCBI Entrez synonym enrichment (faster, no network required)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
@click.option(
    "--use-pydanticai",
    is_flag=True,
    help="Enable PydanticAI LLM reconciliation for ambiguous matches",
)
def main(
    strains_tsv: Path,
    taxa_genomes_tsv: Path,
    growth_prefs_tsv: Path,
    output: Path,
    edges_output: Path,
    taxrank_output: Path,
    dry_run: bool,
    no_bacdive: bool,
    no_ncbi: bool,
    verbose: bool,
    use_pydanticai: bool,
) -> None:
    """Export strain data from all sheets to KGX nodes and edges format.

    Uses an iterative enrichment pipeline:
        Round 1: Parse input sheets, consolidate duplicates
        Round 2: BacDive enrichment (first pass) - match by name
        Round 3: NCBI enrichment - get lineage, synonyms, external linkouts
        Round 4: BacDive enrichment (second pass) - use NCBI linkouts
        Round 5: PydanticAI reconciliation for ambiguous matches (optional)
        Round 6: Final consolidation and export
    """
    # Load environment variables from .env file
    load_dotenv()

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get BacDive collection if not disabled
    bacdive_collection = None
    if not no_bacdive:
        bacdive_collection = get_bacdive_collection()
        if bacdive_collection is None:
            click.echo("Warning: MongoDB not available, BacDive enrichment will be skipped\n")

    # Create and run the iterative enrichment pipeline
    pipeline = IterativeEnrichmentPipeline(
        strains_tsv=strains_tsv,
        taxa_genomes_tsv=taxa_genomes_tsv,
        growth_prefs_tsv=growth_prefs_tsv,
        bacdive_collection=bacdive_collection,
        use_pydanticai=use_pydanticai,
        skip_ncbi=no_ncbi,
        verbose=verbose,
    )

    # Run the pipeline (includes NCBI enrichment with entrez links and external linkouts)
    consolidated = pipeline.run()

    # Show sample query variants in verbose mode
    if verbose and consolidated:
        sample = consolidated[0]
        queries = generate_query_variants(
            sample.scientific_name,
            sample.strain_designation,
            sample.culture_collection_ids,
        )
        click.echo(f"Sample query variants for '{sample.name}':")
        for q in queries[:5]:
            click.echo(f"  - {q}")
        click.echo()

    # Export
    if dry_run:
        click.echo(f"[DRY RUN] Would export nodes to: {output}")
        click.echo(f"[DRY RUN] Would export edges to: {edges_output}")
        click.echo(f"[DRY RUN] Would export taxrank nodes to: {taxrank_output}")
        click.echo("\nSample output:")
        for record in consolidated[:5]:
            node = record.to_kgx_node()
            click.echo(f"  {node['id']}: {node['name']}")
    else:
        click.echo(f"Exporting to {output}")
        export_kgx_nodes(consolidated, output)
        edge_count = export_kgx_edges(consolidated, edges_output)
        click.echo(f"  Exported {edge_count} taxonomic hierarchy edges")
        rank_count = export_taxrank_nodes(consolidated, taxrank_output)
        click.echo(f"  Exported {rank_count} TaxonomicRank nodes")
        click.echo("\nDone!")


if __name__ == "__main__":
    main()
