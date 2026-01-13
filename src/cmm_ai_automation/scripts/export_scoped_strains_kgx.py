#!/usr/bin/env python3
"""Export scoped strain KGX nodes from curated strains file.

Difference from export_strains_kgx.py:
- Input: Single curated file (strains_enriched.tsv) vs. multiple raw TSV files
- Method: Direct read with BacDive + NCBI enrichment vs. full iterative pipeline
- Backend: Requires BacDive MongoDB (for genomes, culture collections)
- Output: Focused subset (6 growth preference strains) vs. comprehensive (27+ strains)
- Output: No taxrank nodes vs. includes taxrank nodes

Reads from data/private/derived/strains_enriched.tsv which contains:
- bacdive_id_mam: Manually curated BacDive IDs
- ncbi_taxon_strain_mam: Manually curated NCBI strain-level taxon IDs
- Other enriched metadata from multiple sources

Primary identifier strategy:
1. bacdive:{bacdive_id} - when bacdive_id_mam is present
2. NCBITaxon:{strain_taxon_id} - when only ncbi_taxon_strain_mam is present
3. Skip rows with neither identifier

BacDive enrichment (enabled by default):
- Culture collection IDs from BacDive's comprehensive cross-reference data
- Genome accessions split by source database (NCBI, IMG, PATRIC, other)
- Synonyms from LPSN (homotypic/heterotypic)
- Strain designation if missing from input file

NCBI enrichment (enabled by default, use --no-ncbi-enrichment to skip):
- Synonyms from NCBI Taxonomy
- Linkouts to external databases (BacDive, BioCyc, LPSN)
- Cross-references extracted from linkouts

Usage:
    uv run python -m cmm_ai_automation.scripts.export_scoped_strains_kgx
    uv run python -m cmm_ai_automation.scripts.export_scoped_strains_kgx --no-ncbi-enrichment
    uv run python -m cmm_ai_automation.scripts.export_scoped_strains_kgx --no-bacdive-enrichment
    uv run python -m cmm_ai_automation.scripts.export_scoped_strains_kgx --output output/kgx/enriched_strains_nodes.tsv
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import click

from cmm_ai_automation.strains.bacdive import extract_bacdive_data, get_bacdive_collection
from cmm_ai_automation.strains.ncbi import (
    extract_genome_accessions_from_linkouts,
    extract_xrefs_from_linkouts,
    fetch_ncbi_linkouts,
    fetch_ncbi_synonyms,
)
from cmm_ai_automation.transform.kgx import KGXEdge, KGXNode

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Default paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "private" / "derived" / "strains_enriched.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "kgx" / "enriched_strains_nodes.tsv"
DEFAULT_EDGES_OUTPUT = PROJECT_ROOT / "output" / "kgx" / "enriched_strains_edges.tsv"


def read_enriched_strains(input_path: Path) -> list[dict[str, str]]:
    """Read strains_enriched.tsv file.

    Args:
        input_path: Path to strains_enriched.tsv

    Returns:
        List of strain dictionaries
    """
    logger.info(f"Reading enriched strains from {input_path}")

    with input_path.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        strains = list(reader)

    logger.info(f"Read {len(strains)} strain records")
    return strains


def create_strain_node(
    strain_data: dict[str, str],
    bacdive_collection: Any | None = None,
    enrich_ncbi: bool = True,
) -> tuple[KGXNode | None, str | None]:
    """Create KGX node from enriched strain data.

    Args:
        strain_data: Dictionary with strain data from enriched file
        bacdive_collection: MongoDB collection for BacDive enrichment (optional)
        enrich_ncbi: If True, fetch additional data from NCBI for NCBI-only strains

    Returns:
        Tuple of (KGXNode or None if no valid identifier, species_taxon_id or None)
    """
    bacdive_id = strain_data.get("bacdive_id_mam", "").strip()
    ncbi_strain_taxon = strain_data.get("ncbi_taxon_strain_mam", "").strip()
    species_taxon_id = strain_data.get("species_taxon_id_sub_or_mpj", "").strip()
    scientific_name = (
        strain_data.get("scientific_name_sub_or_mpj", "").strip()
        or strain_data.get("scientific_name_fresh_lookup", "").strip()
    )
    strain_designation = strain_data.get("strain_designation_sub_or_mpj", "").strip()

    # Initialize additional fields
    culture_collection_ids = []
    genome_accessions_ncbi = []
    genome_accessions_img = []
    genome_accessions_patric = []
    genome_accessions_other = []
    bacdive_synonyms = []

    # Enrich from BacDive if ID is available
    if bacdive_id and bacdive_collection is not None:
        try:
            bacdive_doc = bacdive_collection.find_one({"_id": int(bacdive_id)})
            if bacdive_doc:
                bacdive_data = extract_bacdive_data(bacdive_doc)
                logger.debug(f"Enriching from BacDive: bacdive:{bacdive_id}")

                # Get culture collections from BacDive
                culture_collection_ids = bacdive_data.get("culture_collection_ids", [])

                # Get genome accessions split by source
                genome_accessions_ncbi = bacdive_data.get("genome_accessions_ncbi", [])
                genome_accessions_img = bacdive_data.get("genome_accessions_img", [])
                genome_accessions_patric = bacdive_data.get("genome_accessions_patric", [])
                genome_accessions_other = bacdive_data.get("genome_accessions_other", [])

                # Get synonyms from BacDive
                bacdive_synonyms = bacdive_data.get("synonyms", [])

                # Use BacDive strain designation if missing
                if not strain_designation and bacdive_data.get("strain_designation"):
                    strain_designation = bacdive_data["strain_designation"]

                # Get NCBI taxon from BacDive if missing
                if not ncbi_strain_taxon and bacdive_data.get("ncbi_taxon_id"):
                    ncbi_strain_taxon = str(bacdive_data["ncbi_taxon_id"])

                logger.debug(f"  Found {len(culture_collection_ids)} culture collections")
                logger.debug(f"  Found {len(genome_accessions_ncbi)} NCBI genomes")
        except Exception as e:
            logger.warning(f"Could not enrich from BacDive for {bacdive_id}: {e}")

    # Determine primary ID
    if bacdive_id:
        node_id = f"bacdive:{bacdive_id}"
    elif ncbi_strain_taxon:
        node_id = f"NCBITaxon:{ncbi_strain_taxon}"
    else:
        # No valid identifier
        return None, None

    # Build name from binomial + strain designation
    # Name format: "{binomial_name} {strain_designation}" or fallback
    if strain_designation and scientific_name:
        name = f"{scientific_name} {strain_designation}"
        # Repack strain designation: replace ", " with "|"
        strain_designation = strain_designation.replace(", ", "|")
    elif strain_designation:
        name = strain_designation
        # Repack strain designation: replace ", " with "|"
        strain_designation = strain_designation.replace(", ", "|")
    elif scientific_name:
        name = scientific_name
    else:
        # Fallback name
        name = f"BacDive strain {bacdive_id}" if bacdive_id else f"NCBITaxon {ncbi_strain_taxon}"

    # Create node with extended attributes
    node = KGXNode(
        id=node_id,
        category=["biolink:OrganismTaxon"],
        name=name,
    )

    # Build xrefs
    # Culture collections in bioregistry: atcc, dsmz, jcm, bcrc, nbrc, biocyc, bacdive
    # Not in bioregistry: ncimb, ccug, lmg, kctc, cip, vkm, nrrl, iam, ifo, ncib, cect, etc.
    xrefs = []
    if bacdive_id:
        xrefs.append(f"bacdive:{bacdive_id}")
    if ncbi_strain_taxon:
        xrefs.append(f"NCBITaxon:{ncbi_strain_taxon}")

    # Add culture collection xrefs
    for cc_id in culture_collection_ids:
        # Normalize to CURIE format (e.g., "DSM 1337" → "dsmz:1337")
        if ":" not in cc_id:
            # Parse formats like "DSM 1337" or "ATCC 43645"
            parts = cc_id.split(maxsplit=1)
            if len(parts) == 2:
                prefix, local_id = parts
                prefix_lower = prefix.lower()
                # Map common prefixes
                if prefix_lower in ("dsm", "dsmz"):
                    xrefs.append(f"dsmz:{local_id}")
                elif prefix_lower == "atcc":
                    xrefs.append(f"atcc:{local_id}")
                elif prefix_lower == "jcm":
                    xrefs.append(f"jcm:{local_id}")
                else:
                    xrefs.append(f"{prefix_lower}:{local_id}")
        else:
            xrefs.append(cc_id)

    # Enrich with NCBI data when NCBI ID is available
    ncbi_synonyms = []
    if ncbi_strain_taxon and enrich_ncbi:
        logger.info(f"Enriching with NCBI data: {node_id} (NCBITaxon:{ncbi_strain_taxon})")

        # Fetch synonyms and taxonomy data from NCBI
        try:
            ncbi_data = fetch_ncbi_synonyms(ncbi_strain_taxon)
            ncbi_synonyms.extend(ncbi_data.get("synonyms", []))
            ncbi_synonyms.extend(ncbi_data.get("equivalent_names", []))
            logger.debug(f"  Found {len(ncbi_synonyms)} synonyms from NCBI")

            # Use NCBI species taxon ID if not provided in input
            if not species_taxon_id and ncbi_data.get("species_taxon_id"):
                species_taxon_id = ncbi_data["species_taxon_id"]
                logger.debug(f"  Using species taxon ID from NCBI: {species_taxon_id}")

        except Exception as e:
            logger.warning(f"  Could not fetch NCBI synonyms: {e}")

        # Fetch linkouts and extract xrefs
        try:
            linkouts_data = fetch_ncbi_linkouts([ncbi_strain_taxon])
            if ncbi_strain_taxon in linkouts_data:
                linkouts = linkouts_data[ncbi_strain_taxon]
                extracted_xrefs = extract_xrefs_from_linkouts(linkouts)
                xrefs.extend(extracted_xrefs)
                logger.debug(f"  Found {len(extracted_xrefs)} xrefs from NCBI linkouts")
        except Exception as e:
            logger.warning(f"  Could not fetch NCBI linkouts: {e}")

    if xrefs and len(xrefs) > 1:
        # Remove primary ID from xrefs
        node.xref = [x for x in xrefs if x != node_id]

    # Combine synonyms from all sources
    # Note: scientific_name is now in binomial_name field, not in synonyms
    all_synonyms = []

    # Add BacDive synonyms
    all_synonyms.extend(bacdive_synonyms)

    # Add NCBI synonyms
    all_synonyms.extend(ncbi_synonyms)

    if all_synonyms:
        node.synonym = list(set(all_synonyms))  # Deduplicate

    # Store binomial name (scientific name) as separate field
    if scientific_name:
        node.binomial_name = scientific_name

    # Store genome accessions as additional node attributes (sorted)
    # Note: KGXNode doesn't have these fields by default, so we'll add them as custom attributes
    if genome_accessions_ncbi:
        node.genome_accessions_ncbi = "|".join(sorted(genome_accessions_ncbi))
    if genome_accessions_img:
        node.genome_accessions_img = "|".join(sorted(genome_accessions_img))
    if genome_accessions_patric:
        node.genome_accessions_patric = "|".join(sorted(genome_accessions_patric))
    if genome_accessions_other:
        node.genome_accessions_other = "|".join(sorted(genome_accessions_other))

    # Store strain designation (repacked with | instead of ", ")
    if strain_designation:
        node.strain_designation = strain_designation

    # Add taxonomic rank for strains
    node.has_taxonomic_rank = "strain"

    return node, species_taxon_id


@click.command()
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_INPUT,
    help="Path to strains_enriched.tsv file",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT,
    help="Path to output KGX nodes file",
)
@click.option(
    "--edges-output",
    "edges_output_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_EDGES_OUTPUT,
    help="Path to output KGX edges file",
)
@click.option(
    "--no-bacdive-enrichment",
    is_flag=True,
    help="Disable BacDive enrichment (faster, no MongoDB required, less complete)",
)
@click.option(
    "--no-ncbi-enrichment",
    is_flag=True,
    help="Disable NCBI enrichment for NCBI-only strains (faster, less complete)",
)
def main(
    input_path: Path,
    output_path: Path,
    edges_output_path: Path,
    no_bacdive_enrichment: bool,
    no_ncbi_enrichment: bool,
) -> None:
    """Export enriched strains to KGX nodes and edges format."""
    enrich_ncbi = not no_ncbi_enrichment

    # Get BacDive collection if not disabled
    bacdive_collection = None
    if not no_bacdive_enrichment:
        bacdive_collection = get_bacdive_collection()
        if bacdive_collection is None:
            logger.warning("MongoDB not available, BacDive enrichment will be skipped")

    # Read input
    strains = read_enriched_strains(input_path)

    # Create nodes and edges
    nodes = []
    edges = []
    skipped = 0

    for strain_data in strains:
        node, species_taxon_id = create_strain_node(
            strain_data,
            bacdive_collection=bacdive_collection,
            enrich_ncbi=enrich_ncbi,
        )
        if node:
            nodes.append(node)

            # Create in_taxon edge if species taxon ID exists and differs from strain ID
            if species_taxon_id and f"NCBITaxon:{species_taxon_id}" != node.id:
                edge = KGXEdge(
                    subject=node.id,
                    predicate="biolink:in_taxon",
                    object=f"NCBITaxon:{species_taxon_id}",
                    knowledge_level="knowledge_assertion",
                    agent_type="manual_agent",
                    primary_knowledge_source=["infores:cmm-ai-automation"],
                )
                edges.append(edge)
        else:
            skipped += 1
            logger.debug(f"Skipped strain with no valid identifier: {strain_data}")

    logger.info(f"Created {len(nodes)} strain nodes, {len(edges)} edges, skipped {skipped} records")

    # Create species taxon nodes for all unique species in edges
    if enrich_ncbi:
        species_taxon_ids = set()
        for edge in edges:
            # Extract species taxon ID from object (e.g., "NCBITaxon:408" -> "408")
            if edge.object.startswith("NCBITaxon:"):
                species_id = edge.object.split(":", 1)[1]
                species_taxon_ids.add(species_id)

        logger.info(f"Enriching {len(species_taxon_ids)} unique species taxa with NCBI data")

        # Fetch linkouts for all species taxa (batch operation)
        species_ids_list = sorted(species_taxon_ids)
        logger.info(f"Fetching NCBI linkouts for {len(species_ids_list)} species taxa")
        linkouts_by_taxon = fetch_ncbi_linkouts(species_ids_list)

        for species_id in species_ids_list:
            try:
                ncbi_data = fetch_ncbi_synonyms(species_id)

                # Get scientific name (with fallback)
                scientific_name = ncbi_data.get("scientific_name", "")
                if not scientific_name:
                    # Fallback to first synonym or equivalent name
                    if ncbi_data.get("synonyms"):
                        scientific_name = ncbi_data["synonyms"][0]
                    elif ncbi_data.get("equivalent_names"):
                        scientific_name = ncbi_data["equivalent_names"][0]
                    else:
                        scientific_name = f"NCBITaxon:{species_id}"

                # Create species node
                species_node = KGXNode(
                    id=f"NCBITaxon:{species_id}",
                    category=["biolink:OrganismTaxon"],
                    name=scientific_name,
                )

                # Add synonyms if available
                all_synonyms = []
                all_synonyms.extend(ncbi_data.get("synonyms", []))
                all_synonyms.extend(ncbi_data.get("equivalent_names", []))
                if all_synonyms:
                    species_node.synonym = all_synonyms  # Keep as list, will be joined during write

                # Add taxonomic rank
                rank = ncbi_data.get("rank", "")
                if rank:
                    species_node.has_taxonomic_rank = rank

                # Add xrefs and genome accessions from NCBI linkouts
                linkouts = linkouts_by_taxon.get(species_id, [])
                if linkouts:
                    xrefs = extract_xrefs_from_linkouts(linkouts)
                    if xrefs:
                        species_node.xref = xrefs
                        logger.debug(f"  Added {len(xrefs)} xrefs: {', '.join(xrefs[:3])}...")

                    # Extract genome accessions (sorted)
                    genome_data = extract_genome_accessions_from_linkouts(linkouts)
                    if genome_data.get("genome_accessions_img"):
                        species_node.genome_accessions_img = "|".join(sorted(genome_data["genome_accessions_img"]))
                    if genome_data.get("genome_accessions_other"):
                        species_node.genome_accessions_other = "|".join(sorted(genome_data["genome_accessions_other"]))

                nodes.append(species_node)
                logger.debug(f"  Added species node: NCBITaxon:{species_id} - {scientific_name} ({rank})")

            except Exception as e:
                logger.warning(f"  Could not enrich species NCBITaxon:{species_id}: {e}")
                # Create minimal node even if enrichment fails
                species_node = KGXNode(
                    id=f"NCBITaxon:{species_id}",
                    category=["biolink:OrganismTaxon"],
                    name=f"NCBITaxon:{species_id}",
                )
                nodes.append(species_node)

    logger.info(f"Total {len(nodes)} nodes (strains + species)")

    # Write nodes
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Extended fieldnames to include all additional attributes
    fieldnames = [
        "id",
        "category",
        "name",
        "binomial_name",
        "strain_designation",
        "xref",
        "synonym",
        "has_taxonomic_rank",
        "genome_accessions_ncbi",
        "genome_accessions_img",
        "genome_accessions_patric",
        "genome_accessions_other",
    ]

    with output_path.open("w") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
            extrasaction="ignore",
        )
        writer.writeheader()

        for node in nodes:
            row = node.model_dump(exclude_none=True)
            # Convert lists to pipe-separated strings (sorted)
            if "category" in row:
                row["category"] = "|".join(sorted(row["category"]))
            if "xref" in row:
                row["xref"] = "|".join(sorted(row["xref"]))
            if "synonym" in row:
                row["synonym"] = "|".join(sorted(row["synonym"]))

            # Add custom attributes that were set via setattr()
            for attr in [
                "binomial_name",
                "strain_designation",
                "has_taxonomic_rank",
                "parent_taxon_id",
                "genome_accessions_ncbi",
                "genome_accessions_img",
                "genome_accessions_patric",
                "genome_accessions_other",
            ]:
                if hasattr(node, attr):
                    row[attr] = getattr(node, attr)

            writer.writerow(row)

    logger.info(f"Wrote {len(nodes)} nodes to {output_path}")

    # Write edges
    if edges:
        edges_output_path.parent.mkdir(parents=True, exist_ok=True)

        with edges_output_path.open("w") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "subject",
                    "predicate",
                    "object",
                    "knowledge_level",
                    "agent_type",
                    "primary_knowledge_source",
                ],
                delimiter="\t",
                extrasaction="ignore",
            )
            writer.writeheader()

            for edge in edges:
                row = edge.model_dump(exclude_none=True)
                # Flatten list fields for TSV format (sorted)
                for key, value in row.items():
                    if isinstance(value, list):
                        if len(value) == 1:
                            row[key] = value[0]  # Single value - unwrap
                        else:
                            row[key] = "|".join(
                                str(v) for v in sorted(value)
                            )  # Multiple values - pipe-separated and sorted
                writer.writerow(row)

        logger.info(f"Wrote {len(edges)} edges to {edges_output_path}")
    else:
        logger.info("No edges to write")


if __name__ == "__main__":
    main()
