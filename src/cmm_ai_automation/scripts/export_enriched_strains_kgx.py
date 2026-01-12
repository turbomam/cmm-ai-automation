#!/usr/bin/env python3
"""Export strain KGX nodes from enriched strains file.

Reads from data/private/derived/strains_enriched.tsv which contains:
- bacdive_id_mam: Manually curated BacDive IDs
- ncbi_taxon_strain_mam: Manually curated NCBI strain-level taxon IDs
- Other enriched metadata from multiple sources

Primary identifier strategy:
1. bacdive:{bacdive_id} - when bacdive_id_mam is present
2. NCBITaxon:{strain_taxon_id} - when only ncbi_taxon_strain_mam is present
3. Skip rows with neither identifier

For NCBI-only strains, fetches additional metadata from NCBI Taxonomy:
- Synonyms from NCBI
- Linkouts to external databases (BacDive, BioCyc, LPSN)
- Cross-references extracted from linkouts

Usage:
    uv run python -m cmm_ai_automation.scripts.export_enriched_strains_kgx
    uv run python -m cmm_ai_automation.scripts.export_enriched_strains_kgx --no-ncbi-enrichment
    uv run python -m cmm_ai_automation.scripts.export_enriched_strains_kgx --output output/kgx/enriched_strains_nodes.tsv
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import click

from cmm_ai_automation.strains.ncbi import (
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


def create_strain_node(strain_data: dict[str, str], enrich_ncbi: bool = True) -> tuple[KGXNode | None, str | None]:
    """Create KGX node from enriched strain data.

    Args:
        strain_data: Dictionary with strain data from enriched file
        enrich_ncbi: If True, fetch additional data from NCBI for NCBI-only strains

    Returns:
        Tuple of (KGXNode or None if no valid identifier, species_taxon_id or None)
    """
    bacdive_id = strain_data.get("bacdive_id_mam", "").strip()
    ncbi_strain_taxon = strain_data.get("ncbi_taxon_strain_mam", "").strip()
    species_taxon_id = strain_data.get("species_taxon_id_sub_or_mpj", "").strip()
    scientific_name = strain_data.get("scientific_name_sub_or_mpj", "").strip()
    strain_designation = strain_data.get("strain_designation_sub_or_mpj", "").strip()

    # Determine primary ID
    if bacdive_id:
        node_id = f"bacdive:{bacdive_id}"
        name = strain_designation or scientific_name or f"BacDive strain {bacdive_id}"
    elif ncbi_strain_taxon:
        node_id = f"NCBITaxon:{ncbi_strain_taxon}"
        name = strain_designation or scientific_name or f"NCBITaxon {ncbi_strain_taxon}"
    else:
        # No valid identifier
        return None, None

    # Create node
    node = KGXNode(
        id=node_id,
        category=["biolink:OrganismTaxon"],
        name=name,
    )

    # Add xrefs
    xrefs = []
    if bacdive_id:
        xrefs.append(f"bacdive:{bacdive_id}")
    if ncbi_strain_taxon:
        xrefs.append(f"NCBITaxon:{ncbi_strain_taxon}")

    # Enrich with NCBI data when NCBI ID is available
    synonyms = []
    if ncbi_strain_taxon and enrich_ncbi:
        logger.info(f"Enriching with NCBI data: {node_id} (NCBITaxon:{ncbi_strain_taxon})")

        # Fetch synonyms from NCBI
        try:
            ncbi_data = fetch_ncbi_synonyms(ncbi_strain_taxon)
            synonyms.extend(ncbi_data.get("synonyms", []))
            synonyms.extend(ncbi_data.get("equivalent_names", []))
            logger.debug(f"  Found {len(synonyms)} synonyms from NCBI")
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

    # Add scientific name as synonym if different from name
    if scientific_name and scientific_name != name:
        synonyms.append(scientific_name)

    if synonyms:
        node.synonym = list(set(synonyms))  # Deduplicate

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
    "--no-ncbi-enrichment",
    is_flag=True,
    help="Disable NCBI enrichment for NCBI-only strains (faster, less complete)",
)
def main(input_path: Path, output_path: Path, edges_output_path: Path, no_ncbi_enrichment: bool) -> None:
    """Export enriched strains to KGX nodes and edges format."""
    enrich_ncbi = not no_ncbi_enrichment

    # Read input
    strains = read_enriched_strains(input_path)

    # Create nodes and edges
    nodes = []
    edges = []
    skipped = 0

    for strain_data in strains:
        node, species_taxon_id = create_strain_node(strain_data, enrich_ncbi=enrich_ncbi)
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
                )
                edges.append(edge)
        else:
            skipped += 1
            logger.debug(f"Skipped strain with no valid identifier: {strain_data}")

    logger.info(f"Created {len(nodes)} KGX nodes, {len(edges)} edges, skipped {skipped} records")

    # Write nodes
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "category", "name", "xref", "synonym"],
            delimiter="\t",
            extrasaction="ignore",
        )
        writer.writeheader()

        for node in nodes:
            row = node.model_dump(exclude_none=True)
            # Convert lists to pipe-separated strings
            if "category" in row:
                row["category"] = "|".join(row["category"])
            if "xref" in row:
                row["xref"] = "|".join(row["xref"])
            if "synonym" in row:
                row["synonym"] = "|".join(row["synonym"])
            writer.writerow(row)

    logger.info(f"Wrote {len(nodes)} nodes to {output_path}")

    # Write edges
    if edges:
        edges_output_path.parent.mkdir(parents=True, exist_ok=True)

        with edges_output_path.open("w") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["subject", "predicate", "object", "knowledge_level", "agent_type"],
                delimiter="\t",
                extrasaction="ignore",
            )
            writer.writeheader()

            for edge in edges:
                row = edge.model_dump(exclude_none=True)
                writer.writerow(row)

        logger.info(f"Wrote {len(edges)} edges to {edges_output_path}")
    else:
        logger.info("No edges to write")


if __name__ == "__main__":
    main()
