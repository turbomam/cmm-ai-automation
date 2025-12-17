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

Usage:
    uv run python -m cmm_ai_automation.scripts.export_strains_kgx
    uv run python -m cmm_ai_automation.scripts.export_strains_kgx --dry-run
    uv run python -m cmm_ai_automation.scripts.export_strains_kgx --output output/kgx/strains_nodes.tsv
"""

import csv
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import bioregistry
import click

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Default paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_STRAINS = PROJECT_ROOT / "data" / "private" / "strains.tsv"
DEFAULT_TAXA_GENOMES = PROJECT_ROOT / "data" / "private" / "taxa_and_genomes.tsv"
DEFAULT_GROWTH_PREFS = PROJECT_ROOT / "data" / "private" / "growth_preferences.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "kgx" / "strains_nodes.tsv"

# Biolink category for strains
BIOLINK_CATEGORY = "biolink:OrganismalEntity"

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
}


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

    # Culture collection IDs
    culture_collection_ids: list[str] = field(default_factory=list)
    primary_collection_id: str | None = None  # e.g., DSM:16371

    # BacDive
    bacdive_id: str | None = None

    # Genome
    genome_accession: str | None = None  # GCA_* accession

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
    - Matching culture collection IDs
    - Matching NCBITaxon IDs
    - Similar names

    Args:
        all_records: List of strain records from all sources

    Returns:
        Deduplicated list of consolidated records
    """
    # For now, simple deduplication by NCBITaxon or primary collection ID
    consolidated: dict[str, StrainRecord] = {}

    for record in all_records:
        # Generate a key for deduplication
        key = None
        if record.ncbi_taxon_id:
            key = f"ncbi:{record.ncbi_taxon_id}"
        elif record.primary_collection_id:
            key = f"cc:{record.primary_collection_id}"
        elif record.name:
            key = f"name:{record.name.lower()}"
        else:
            key = f"row:{record.source_sheet}:{record.source_row}"

        if key in consolidated:
            # Merge into existing record
            existing = consolidated[key]
            _merge_records(existing, record)
        else:
            consolidated[key] = record

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
    if not target.bacdive_id and source.bacdive_id:
        target.bacdive_id = source.bacdive_id
    if not target.genome_accession and source.genome_accession:
        target.genome_accession = source.genome_accession

    # Merge collection IDs
    for cc_id in source.culture_collection_ids:
        if cc_id not in target.culture_collection_ids:
            target.culture_collection_ids.append(cc_id)

    # Merge synonyms
    for syn in source.synonyms:
        if syn not in target.synonyms:
            target.synonyms.append(syn)


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
        "ncbi_taxon_id",
        "species_taxon_id",
        "strain_designation",
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
    "--dry-run",
    is_flag=True,
    help="Parse and consolidate but don't write output",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def main(
    strains_tsv: Path,
    taxa_genomes_tsv: Path,
    growth_prefs_tsv: Path,
    output: Path,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Export strain data from all sheets to KGX nodes format."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    click.echo("=== Strain KGX Node Export ===\n")

    # Parse all input sheets
    click.echo("Phase 1: Parsing input sheets")
    all_records: list[StrainRecord] = []

    records = parse_strains_tsv(strains_tsv)
    all_records.extend(records)

    records = parse_taxa_and_genomes_tsv(taxa_genomes_tsv)
    all_records.extend(records)

    records = parse_growth_preferences_tsv(growth_prefs_tsv)
    all_records.extend(records)

    click.echo(f"  Total records from all sheets: {len(all_records)}\n")

    # Consolidate duplicates
    click.echo("Phase 2: Consolidating duplicates")
    consolidated = consolidate_strains(all_records)
    click.echo(f"  Unique strains: {len(consolidated)}\n")

    # Show sample query variants
    if verbose and consolidated:
        sample = consolidated[0]
        queries = generate_query_variants(
            sample.scientific_name,
            sample.strain_designation,
            sample.culture_collection_ids,
        )
        click.echo(f"  Sample query variants for '{sample.name}':")
        for q in queries[:5]:
            click.echo(f"    - {q}")
        click.echo()

    # Export
    if dry_run:
        click.echo("[DRY RUN] Would export to: {output}")
        click.echo("\nSample output:")
        for record in consolidated[:5]:
            node = record.to_kgx_node()
            click.echo(f"  {node['id']}: {node['name']}")
    else:
        click.echo(f"Phase 3: Exporting to {output}")
        export_kgx_nodes(consolidated, output)
        click.echo("\nDone!")


if __name__ == "__main__":
    main()
