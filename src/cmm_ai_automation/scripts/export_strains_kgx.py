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

import logging
from pathlib import Path

import click
from dotenv import load_dotenv

from cmm_ai_automation.strains import (
    IterativeEnrichmentPipeline,
    export_kgx_edges,
    export_kgx_nodes,
    export_taxrank_nodes,
    get_bacdive_collection,
)
from cmm_ai_automation.strains.enrichment import generate_query_variants

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
