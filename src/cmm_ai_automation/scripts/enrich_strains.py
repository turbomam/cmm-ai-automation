#!/usr/bin/env python3
"""Enrich CMM strains using multiple data sources.

Uses iterative/spidering approach to gather strain and species data from:
- NCBI Taxonomy E-utilities API
- BacDive API (DSMZ)
- DSMZ web scraping
- ATCC web scraping
- NCBITaxon ChromaDB semantic search

Usage:
    uv run python -m cmm_ai_automation.scripts.enrich_strains

Options:
    --input PATH         Input TSV file (default: data/private/strains.tsv)
    --output PATH        Output TSV file (default: stdout)
    --limit N            Process only first N strains (for testing)
    --bacdive-email      BacDive API email (or BACDIVE_EMAIL env var)
    --bacdive-password   BacDive API password (or BACDIVE_PASSWORD env var)
"""

import argparse
import csv
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import quote_plus
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_INPUT = "./data/private/strains/strains.tsv"
REQUEST_DELAY = 0.5  # Be polite to APIs

# NCBI E-utilities base URL
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# BacDive API base URL
BACDIVE_BASE = "https://bacdive.dsmz.de/api/bacdive"


@dataclass
class EnrichedStrain:
    """Enriched strain data from multiple sources."""

    # Input fields
    strain_id: str
    species_taxon_id: str
    scientific_name: str
    strain_designation: str
    culture_collection_ids: str
    alternative_names: str

    # Enriched fields
    ncbi_species_taxon_id: str | None = None
    ncbi_strain_taxon_id: str | None = None
    ncbi_species_name: str | None = None
    ncbi_synonyms: list[str] = field(default_factory=list)
    ncbi_lineage: str | None = None

    bacdive_id: str | None = None
    bacdive_species_name: str | None = None
    bacdive_ncbi_taxon_id: str | None = None
    bacdive_strain_designation: str | None = None
    bacdive_culture_collections: list[str] = field(default_factory=list)

    dsmz_ncbi_taxon_id: str | None = None
    dsmz_species_name: str | None = None
    dsmz_strain_designation: str | None = None

    atcc_ncbi_taxon_id: str | None = None
    atcc_species_name: str | None = None
    atcc_strain_designation: str | None = None

    chromadb_matched_taxon_id: str | None = None
    chromadb_distance: float | None = None

    # Metadata
    sources_used: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class NCBITaxonomyClient:
    """Client for NCBI Taxonomy E-utilities API."""

    def __init__(self, email: str = "cmm-ai@example.com", api_key: str | None = None):
        self.email = email
        self.api_key = api_key
        self.session = requests.Session()

    def _build_params(self, **kwargs: Any) -> dict[str, Any]:
        """Build request parameters with email and optional API key."""
        params = {"email": self.email, **kwargs}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def search_taxon(self, query: str) -> list[str]:
        """Search NCBI Taxonomy for a query string.

        Args:
            query: Search term (species name, strain name, etc.)

        Returns:
            List of matching taxon IDs
        """
        url = f"{NCBI_BASE}/esearch.fcgi"
        params = self._build_params(
            db="taxonomy",
            term=query,
            retmax=20,
            retmode="json",
        )

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            esearch: dict[str, Any] = data.get("esearchresult", {})
            idlist: list[str] = esearch.get("idlist", [])
            return idlist
        except Exception as e:
            logger.warning(f"NCBI search failed for '{query}': {e}")
            return []

    def fetch_taxon_info(self, taxon_id: str) -> dict[str, Any] | None:
        """Fetch detailed information for a taxon ID.

        Args:
            taxon_id: NCBI Taxonomy ID

        Returns:
            Dict with taxon info or None if not found
        """
        url = f"{NCBI_BASE}/efetch.fcgi"
        params = self._build_params(
            db="taxonomy",
            id=taxon_id,
            retmode="xml",
        )

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            root = ElementTree.fromstring(response.content)
            taxon = root.find(".//Taxon")
            if taxon is None:
                return None

            result: dict[str, Any] = {
                "taxon_id": taxon_id,
                "scientific_name": taxon.findtext("ScientificName", ""),
                "rank": taxon.findtext("Rank", ""),
                "lineage": taxon.findtext("Lineage", ""),
                "synonyms": [],
                "other_names": [],
            }

            # Get synonyms and other names
            for other_name in taxon.findall(".//OtherNames/*"):
                name_text = other_name.text
                if name_text:
                    if other_name.tag == "Synonym":
                        result["synonyms"].append(name_text)
                    else:
                        result["other_names"].append(name_text)

            # Get parent taxon ID
            parent = taxon.find(".//ParentTaxId")
            if parent is not None and parent.text:
                result["parent_taxon_id"] = parent.text

            return result

        except Exception as e:
            logger.warning(f"NCBI fetch failed for taxon {taxon_id}: {e}")
            return None

    def search_strain(self, species_name: str, strain_designation: str) -> dict[str, Any] | None:
        """Search for a specific strain.

        Args:
            species_name: Species scientific name
            strain_designation: Strain designation (e.g., "AM-1", "KT2440")

        Returns:
            Dict with strain taxon info or None
        """
        # Try various query formats
        queries = [
            f'"{species_name}" "{strain_designation}"',
            f'"{species_name}" {strain_designation}',
            f"{species_name} {strain_designation}",
            f'"{species_name} {strain_designation}"[All Names]',
        ]

        for query in queries:
            ids = self.search_taxon(query)
            if ids:
                # Verify the result is actually a strain
                for taxon_id in ids:
                    info = self.fetch_taxon_info(taxon_id)
                    if info and info.get("rank") in ("strain", "no rank"):
                        return info
                    time.sleep(REQUEST_DELAY / 2)
            time.sleep(REQUEST_DELAY)

        return None


class BacDiveClient:
    """Client for BacDive API."""

    def __init__(self, email: str | None = None, password: str | None = None):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.authenticated = False

    def authenticate(self) -> bool:
        """Authenticate with BacDive API."""
        if not self.email or not self.password:
            logger.warning("BacDive credentials not provided")
            return False

        try:
            # BacDive uses HTTP Basic Auth
            self.session.auth = (self.email, self.password)
            # Test authentication with a simple request
            response = self.session.get(
                f"{BACDIVE_BASE}/fetch/1",
                timeout=30,
            )
            self.authenticated = response.status_code != 401
            if not self.authenticated:
                logger.warning("BacDive authentication failed")
            return self.authenticated
        except Exception as e:
            logger.warning(f"BacDive authentication error: {e}")
            return False

    def search_by_culture_collection(self, collection: str, number: str) -> list[dict[str, Any]]:
        """Search BacDive by culture collection ID.

        Args:
            collection: Collection abbreviation (e.g., "DSM", "ATCC")
            number: Strain number

        Returns:
            List of matching BacDive entries
        """
        if not self.authenticated and not self.authenticate():
            return []

        try:
            url = f"{BACDIVE_BASE}/culturecollectionno/{collection} {number}/"
            response = self.session.get(url, timeout=30)

            if response.status_code == 404:
                return []

            response.raise_for_status()
            data = response.json()

            # Handle pagination - BacDive returns URLs to individual entries
            results = []
            if "results" in data:
                for entry_url in data["results"].values():
                    entry_response = self.session.get(entry_url, timeout=30)
                    if entry_response.status_code == 200:
                        results.append(entry_response.json())
                    time.sleep(REQUEST_DELAY / 2)

            return results

        except Exception as e:
            logger.warning(f"BacDive search failed for {collection} {number}: {e}")
            return []

    def search_by_species(self, species_name: str) -> list[dict[str, Any]]:
        """Search BacDive by species name.

        Args:
            species_name: Scientific species name

        Returns:
            List of matching BacDive entries
        """
        if not self.authenticated and not self.authenticate():
            return []

        try:
            url = f"{BACDIVE_BASE}/taxon/{quote_plus(species_name)}/"
            response = self.session.get(url, timeout=30)

            if response.status_code == 404:
                return []

            response.raise_for_status()
            data = response.json()

            # Just return first few entries for species-level search
            results = []
            if "results" in data:
                for i, entry_url in enumerate(data["results"].values()):
                    if i >= 5:  # Limit to first 5 entries
                        break
                    entry_response = self.session.get(entry_url, timeout=30)
                    if entry_response.status_code == 200:
                        results.append(entry_response.json())
                    time.sleep(REQUEST_DELAY / 2)

            return results

        except Exception as e:
            logger.warning(f"BacDive species search failed for {species_name}: {e}")
            return []

    @staticmethod
    def extract_ncbi_taxon_id(entry: dict[str, Any]) -> str | None:
        """Extract NCBI taxon ID from BacDive entry."""
        try:
            taxonomy = entry.get("taxonomy_name", {})
            # Check for NCBI link
            ncbi_link = taxonomy.get("ncbi_tax_id")
            if ncbi_link:
                if isinstance(ncbi_link, int):
                    return str(ncbi_link)
                if isinstance(ncbi_link, str):
                    # Extract ID from URL if needed
                    match = re.search(r"(\d+)", ncbi_link)
                    if match:
                        return match.group(1)
            return None
        except Exception:
            return None

    @staticmethod
    def extract_strain_info(entry: dict[str, Any]) -> dict[str, Any]:
        """Extract relevant strain info from BacDive entry."""
        result: dict[str, Any] = {}

        try:
            # Get taxonomy info
            if "taxonomy_name" in entry:
                tax = entry["taxonomy_name"]
                result["species_name"] = tax.get("species", "")
                result["ncbi_taxon_id"] = BacDiveClient.extract_ncbi_taxon_id(entry)

            # Get strain designations
            if "strain_availability" in entry:
                avail = entry["strain_availability"]
                if "strain_designation" in avail:
                    result["strain_designation"] = avail["strain_designation"]

            # Get culture collection IDs
            if "culture_collection_no" in entry:
                result["culture_collections"] = entry["culture_collection_no"]

        except Exception:
            pass

        return result


class DSMZScraper:
    """Web scraper for DSMZ culture collection pages."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; CMM-AI-Automation/1.0)",
            }
        )

    def fetch_strain_page(self, dsm_number: str) -> dict[str, Any] | None:
        """Fetch and parse a DSMZ strain page.

        Args:
            dsm_number: DSM strain number (e.g., "1337")

        Returns:
            Dict with extracted strain info or None
        """
        url = f"https://www.dsmz.de/collection/catalogue/details/culture/DSM-{dsm_number}"

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 404:
                return None
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            result: dict[str, Any] = {"dsm_number": dsm_number, "url": url}

            # Extract species name from title or main content
            title = soup.find("h1")
            if title:
                result["species_name"] = title.get_text(strip=True)

            # Look for strain designation
            strain_row = soup.find(string=re.compile(r"Strain designation", re.I))
            if strain_row:
                parent = strain_row.find_parent("tr")
                if parent:
                    cells = parent.find_all("td")
                    if len(cells) >= 2:
                        result["strain_designation"] = cells[1].get_text(strip=True)

            # Look for NCBI taxon links
            ncbi_links = soup.find_all("a", href=re.compile(r"ncbi.*taxonomy", re.I))
            for link in ncbi_links:
                href = link.get("href", "")
                href_str = str(href) if href else ""
                match = re.search(r"id=(\d+)", href_str)
                if match:
                    result["ncbi_taxon_id"] = match.group(1)
                    break

            # Look for GenBank accession numbers (can lead to taxon IDs)
            genbank_links = soup.find_all("a", href=re.compile(r"ncbi.*nuccore|genbank", re.I))
            result["genbank_accessions"] = []
            for link in genbank_links:
                acc = link.get_text(strip=True)
                if acc and len(acc) > 5:
                    result["genbank_accessions"].append(acc)

            # Look for other culture collection cross-references
            result["culture_collections"] = []
            # Look for table rows containing collection abbreviations
            for abbrev in ["ATCC", "NCIMB", "JCM", "NBRC", "LMG", "CIP", "CCM", "CECT"]:
                # Find all links and filter by text content
                for link in soup.find_all("a"):
                    text = link.get_text(strip=True)
                    if text and text.upper().startswith(abbrev) and text not in result["culture_collections"]:
                        result["culture_collections"].append(text)

            return result

        except Exception as e:
            logger.warning(f"DSMZ scrape failed for DSM-{dsm_number}: {e}")
            return None


class ATCCScraper:
    """Web scraper for ATCC culture collection pages."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; CMM-AI-Automation/1.0)",
            }
        )

    def fetch_strain_page(self, atcc_number: str) -> dict[str, Any] | None:
        """Fetch and parse an ATCC strain page.

        Args:
            atcc_number: ATCC catalog number (e.g., "43883")

        Returns:
            Dict with extracted strain info or None
        """
        url = f"https://www.atcc.org/products/{atcc_number}"

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 404:
                return None
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            result: dict[str, Any] = {"atcc_number": atcc_number, "url": url}

            # Extract species name from title
            title = soup.find("h1")
            if title:
                result["species_name"] = title.get_text(strip=True)

            # Look for product name which often has species
            product_name = soup.find(attrs={"data-qa": "product-name"})
            if product_name:
                result["product_name"] = product_name.get_text(strip=True)

            # Search for strain designation in the page
            strain_patterns = [
                r"Strain Designation[:\s]+([^\n<]+)",
                r"strain\s+(\S+)",
                r"Depositor.*?(\S+)\s*$",
            ]
            page_text = soup.get_text()
            for pattern in strain_patterns:
                match = re.search(pattern, page_text, re.I)
                if match:
                    result["strain_designation"] = match.group(1).strip()
                    break

            # Look for NCBI taxonomy links
            ncbi_links = soup.find_all("a", href=re.compile(r"ncbi.*taxonomy|txid", re.I))
            for link in ncbi_links:
                href = link.get("href", "")
                href_str = str(href) if href else ""
                match = re.search(r"id=(\d+)|txid(\d+)", href_str)
                if match:
                    result["ncbi_taxon_id"] = match.group(1) or match.group(2)
                    break

            # Look for GenBank accessions
            genbank_pattern = re.compile(r"\b([A-Z]{1,2}\d{5,6})\b")
            result["genbank_accessions"] = genbank_pattern.findall(page_text)[:5]

            # Look for other culture collection references
            result["culture_collections"] = []
            for abbrev in ["DSM", "NCIMB", "JCM", "NBRC", "LMG", "CIP"]:
                cc_pattern = re.compile(rf"{abbrev}[:\s]*(\d+)", re.I)
                matches = cc_pattern.findall(page_text)
                for num in matches:
                    cc_id = f"{abbrev}:{num}"
                    if cc_id not in result["culture_collections"]:
                        result["culture_collections"].append(cc_id)

            return result

        except Exception as e:
            logger.warning(f"ATCC scrape failed for {atcc_number}: {e}")
            return None


class StrainEnricher:
    """Main strain enrichment pipeline."""

    def __init__(
        self,
        ncbi_client: NCBITaxonomyClient,
        bacdive_client: BacDiveClient | None,
        dsmz_scraper: DSMZScraper,
        atcc_scraper: ATCCScraper,
        chromadb_collection: Any | None = None,
    ):
        self.ncbi = ncbi_client
        self.bacdive = bacdive_client
        self.dsmz = dsmz_scraper
        self.atcc = atcc_scraper
        self.chromadb = chromadb_collection

    def parse_culture_collection_ids(self, ids_string: str) -> list[tuple[str, str]]:
        """Parse culture collection IDs string into list of (collection, number) tuples."""
        if not ids_string:
            return []

        results = []
        # Split by semicolon or comma
        parts = re.split(r"[;,]", ids_string)
        for part in parts:
            part = part.strip()
            # Try to parse "DSM:1337" or "DSM 1337" format
            match = re.match(r"([A-Z]+)[:\s]+(\d+[a-z]?)", part, re.I)
            if match:
                results.append((match.group(1).upper(), match.group(2)))

        return results

    def enrich_from_ncbi(self, strain: EnrichedStrain, species_taxon_id: str | None = None) -> None:
        """Enrich strain data from NCBI Taxonomy."""
        try:
            # If we have a species taxon ID, fetch its info
            if species_taxon_id:
                info = self.ncbi.fetch_taxon_info(species_taxon_id)
                if info:
                    strain.ncbi_species_taxon_id = species_taxon_id
                    strain.ncbi_species_name = info.get("scientific_name")
                    strain.ncbi_synonyms = info.get("synonyms", [])
                    strain.ncbi_lineage = info.get("lineage")
                    strain.sources_used.append("ncbi_species")
                    time.sleep(REQUEST_DELAY)

            # Try to find strain-level taxon
            if strain.strain_designation and strain.scientific_name:
                strain_info = self.ncbi.search_strain(strain.scientific_name, strain.strain_designation)
                if strain_info:
                    strain.ncbi_strain_taxon_id = strain_info.get("taxon_id")
                    strain.sources_used.append("ncbi_strain")
            # Also try with synonym names
            elif strain.strain_designation and strain.alternative_names:
                for alt_name in strain.alternative_names.split(";"):
                    alt_name = alt_name.strip()
                    if alt_name:
                        strain_info = self.ncbi.search_strain(alt_name, strain.strain_designation)
                        if strain_info:
                            strain.ncbi_strain_taxon_id = strain_info.get("taxon_id")
                            strain.sources_used.append("ncbi_strain_via_synonym")
                            break
                        time.sleep(REQUEST_DELAY)

        except Exception as e:
            strain.errors.append(f"NCBI error: {e}")

    def enrich_from_bacdive(self, strain: EnrichedStrain) -> None:
        """Enrich strain data from BacDive."""
        if not self.bacdive or not self.bacdive.authenticated:
            return

        try:
            # Try each culture collection ID
            cc_ids = self.parse_culture_collection_ids(strain.culture_collection_ids)
            for collection, number in cc_ids:
                if collection in ("DSM", "ATCC", "JCM", "NBRC", "NCIMB", "LMG"):
                    entries = self.bacdive.search_by_culture_collection(collection, number)
                    if entries:
                        entry = entries[0]
                        info = BacDiveClient.extract_strain_info(entry)

                        strain.bacdive_id = str(entry.get("id", ""))
                        strain.bacdive_species_name = info.get("species_name")
                        strain.bacdive_ncbi_taxon_id = info.get("ncbi_taxon_id")
                        strain.bacdive_strain_designation = info.get("strain_designation")
                        strain.bacdive_culture_collections = info.get("culture_collections", [])
                        strain.sources_used.append(f"bacdive_{collection}")
                        break

                    time.sleep(REQUEST_DELAY)

        except Exception as e:
            strain.errors.append(f"BacDive error: {e}")

    def enrich_from_dsmz(self, strain: EnrichedStrain) -> None:
        """Enrich strain data from DSMZ web scraping."""
        try:
            cc_ids = self.parse_culture_collection_ids(strain.culture_collection_ids)
            for collection, number in cc_ids:
                if collection == "DSM":
                    info = self.dsmz.fetch_strain_page(number)
                    if info:
                        strain.dsmz_ncbi_taxon_id = info.get("ncbi_taxon_id")
                        strain.dsmz_species_name = info.get("species_name")
                        strain.dsmz_strain_designation = info.get("strain_designation")
                        strain.sources_used.append("dsmz_web")
                        break

                    time.sleep(REQUEST_DELAY)

        except Exception as e:
            strain.errors.append(f"DSMZ error: {e}")

    def enrich_from_atcc(self, strain: EnrichedStrain) -> None:
        """Enrich strain data from ATCC web scraping."""
        try:
            cc_ids = self.parse_culture_collection_ids(strain.culture_collection_ids)
            for collection, number in cc_ids:
                if collection == "ATCC":
                    info = self.atcc.fetch_strain_page(number)
                    if info:
                        strain.atcc_ncbi_taxon_id = info.get("ncbi_taxon_id")
                        strain.atcc_species_name = info.get("species_name")
                        strain.atcc_strain_designation = info.get("strain_designation")
                        strain.sources_used.append("atcc_web")
                        break

                    time.sleep(REQUEST_DELAY)

        except Exception as e:
            strain.errors.append(f"ATCC error: {e}")

    def enrich_from_chromadb(self, strain: EnrichedStrain) -> None:
        """Enrich strain data from ChromaDB semantic search."""
        if not self.chromadb:
            return

        try:
            import openai

            # Build query from available info
            query_parts = []
            if strain.scientific_name:
                query_parts.append(strain.scientific_name)
            if strain.strain_designation:
                # Normalize strain designation
                normalized = strain.strain_designation.replace("-", "")
                query_parts.append(normalized)

            if not query_parts:
                return

            query = " ".join(query_parts)

            # Generate embedding and search
            response = openai.embeddings.create(
                model="text-embedding-3-small",
                input=query,
            )
            query_embedding = response.data[0].embedding

            results = self.chromadb.query(
                query_embeddings=[query_embedding],
                n_results=1,
                include=["metadatas", "distances"],
            )

            if results["ids"][0]:
                iri = results["metadatas"][0][0].get("iri", "")
                taxon_id = iri.split("/")[-1].replace("NCBITaxon_", "")
                distance = results["distances"][0][0]

                strain.chromadb_matched_taxon_id = taxon_id
                strain.chromadb_distance = distance
                strain.sources_used.append("chromadb")

        except Exception as e:
            strain.errors.append(f"ChromaDB error: {e}")

    def enrich_strain(self, row: dict[str, str]) -> EnrichedStrain:
        """Enrich a single strain with data from all sources.

        Args:
            row: Input row from strains TSV

        Returns:
            EnrichedStrain with data from all sources
        """
        strain = EnrichedStrain(
            strain_id=row.get("strain_id", ""),
            species_taxon_id=row.get("species_taxon_id", ""),
            scientific_name=row.get("scientific_name", ""),
            strain_designation=row.get("strain_designation", ""),
            culture_collection_ids=row.get("culture_collection_ids", ""),
            alternative_names=row.get("alternative_names", ""),
        )

        # Enrich from each source
        logger.info(f"Enriching {strain.strain_id or strain.scientific_name}...")

        # 1. NCBI Taxonomy (primary source)
        self.enrich_from_ncbi(strain, strain.species_taxon_id or None)

        # 2. BacDive API
        self.enrich_from_bacdive(strain)

        # 3. DSMZ web scraping
        self.enrich_from_dsmz(strain)

        # 4. ATCC web scraping
        self.enrich_from_atcc(strain)

        # 5. ChromaDB semantic search (fallback)
        self.enrich_from_chromadb(strain)

        return strain


def main() -> None:
    """Enrich CMM strains using multiple data sources."""
    parser = argparse.ArgumentParser(description="Enrich CMM strains using multiple data sources")
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help="Input TSV file",
    )
    parser.add_argument(
        "--output",
        help="Output TSV file (default: stdout)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only first N strains",
    )
    parser.add_argument(
        "--bacdive-email",
        help="BacDive API email",
    )
    parser.add_argument(
        "--bacdive-password",
        help="BacDive API password",
    )
    parser.add_argument(
        "--ncbi-api-key",
        help="NCBI API key (optional, increases rate limit)",
    )
    parser.add_argument(
        "--chroma-path",
        default="./data/chroma_ncbitaxon",
        help="ChromaDB directory",
    )
    parser.add_argument(
        "--env-file",
        help="Path to .env file",
    )
    args = parser.parse_args()

    # Load environment
    if args.env_file:
        load_dotenv(args.env_file)
    else:
        load_dotenv()

    # Get credentials from args or environment
    bacdive_email = args.bacdive_email or os.environ.get("BACDIVE_EMAIL")
    bacdive_password = args.bacdive_password or os.environ.get("BACDIVE_PASSWORD")
    ncbi_api_key = args.ncbi_api_key or os.environ.get("NCBI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if openai_key:
        import openai

        openai.api_key = openai_key

    # Initialize clients
    ncbi_client = NCBITaxonomyClient(api_key=ncbi_api_key)
    bacdive_client = None
    if bacdive_email and bacdive_password:
        bacdive_client = BacDiveClient(bacdive_email, bacdive_password)
        if bacdive_client.authenticate():
            logger.info("BacDive authentication successful")
        else:
            logger.warning("BacDive authentication failed, skipping BacDive")
            bacdive_client = None
    else:
        logger.info("BacDive credentials not provided, skipping BacDive")

    dsmz_scraper = DSMZScraper()
    atcc_scraper = ATCCScraper()

    # Initialize ChromaDB if available
    chromadb_collection = None
    try:
        if Path(args.chroma_path).exists():
            import chromadb
            from chromadb.config import Settings

            client = chromadb.PersistentClient(
                path=args.chroma_path,
                settings=Settings(anonymized_telemetry=False),
            )
            chromadb_collection = client.get_collection(name="ncbitaxon_embeddings")
            logger.info(f"ChromaDB collection loaded with {chromadb_collection.count()} entries")
    except Exception as e:
        logger.warning(f"ChromaDB not available: {e}")

    # Create enricher
    enricher = StrainEnricher(
        ncbi_client=ncbi_client,
        bacdive_client=bacdive_client,
        dsmz_scraper=dsmz_scraper,
        atcc_scraper=atcc_scraper,
        chromadb_collection=chromadb_collection,
    )

    # Read input strains
    logger.info(f"Reading strains from {args.input}")
    strains: list[dict[str, str]] = []
    with Path(args.input).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            strains.append(row)

    if args.limit:
        strains = strains[: args.limit]

    logger.info(f"Processing {len(strains)} strains...")

    # Process each strain
    results: list[EnrichedStrain] = []
    for i, strain_row in enumerate(strains):
        if i > 0 and i % 5 == 0:
            logger.info(f"  Progress: {i}/{len(strains)}")

        enriched = enricher.enrich_strain(strain_row)
        results.append(enriched)

    # Output results
    fieldnames = [
        "strain_id",
        "scientific_name",
        "strain_designation",
        "species_taxon_id",
        "culture_collection_ids",
        "ncbi_species_taxon_id",
        "ncbi_strain_taxon_id",
        "ncbi_species_name",
        "ncbi_synonyms",
        "bacdive_id",
        "bacdive_ncbi_taxon_id",
        "dsmz_ncbi_taxon_id",
        "atcc_ncbi_taxon_id",
        "chromadb_matched_taxon_id",
        "chromadb_distance",
        "sources_used",
        "errors",
    ]

    def get_output_file() -> TextIO:
        if args.output:
            return Path(args.output).open("w", newline="", encoding="utf-8")
        return sys.stdout

    with get_output_file() as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()

        for enriched in results:
            writer.writerow(
                {
                    "strain_id": enriched.strain_id,
                    "scientific_name": enriched.scientific_name,
                    "strain_designation": enriched.strain_designation,
                    "species_taxon_id": enriched.species_taxon_id,
                    "culture_collection_ids": enriched.culture_collection_ids,
                    "ncbi_species_taxon_id": enriched.ncbi_species_taxon_id or "",
                    "ncbi_strain_taxon_id": enriched.ncbi_strain_taxon_id or "",
                    "ncbi_species_name": enriched.ncbi_species_name or "",
                    "ncbi_synonyms": "; ".join(enriched.ncbi_synonyms),
                    "bacdive_id": enriched.bacdive_id or "",
                    "bacdive_ncbi_taxon_id": enriched.bacdive_ncbi_taxon_id or "",
                    "dsmz_ncbi_taxon_id": enriched.dsmz_ncbi_taxon_id or "",
                    "atcc_ncbi_taxon_id": enriched.atcc_ncbi_taxon_id or "",
                    "chromadb_matched_taxon_id": enriched.chromadb_matched_taxon_id or "",
                    "chromadb_distance": f"{enriched.chromadb_distance:.4f}" if enriched.chromadb_distance else "",
                    "sources_used": "; ".join(enriched.sources_used),
                    "errors": "; ".join(enriched.errors),
                }
            )

    # Summary
    logger.info("\n=== Summary ===")
    logger.info(f"  Total strains: {len(results)}")

    source_counts: dict[str, int] = {}
    for r in results:
        for src in r.sources_used:
            source_counts[src] = source_counts.get(src, 0) + 1

    logger.info("  Sources used:")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        logger.info(f"    {src}: {count}")

    error_count = sum(1 for r in results if r.errors)
    logger.info(f"  Strains with errors: {error_count}")


if __name__ == "__main__":
    main()
