#!/usr/bin/env python3
"""Multi-source enrichment pipeline that loads data into EnrichmentStore.

Reads normalized ingredients and enriches them by querying:
- PubChem (chemical identifiers, structure)
- ChEBI (roles, ontology)
- CAS Common Chemistry (mixtures, additional identifiers)
- Node Normalization (identifier resolution)

All data is stored in a linkml-store backed DuckDB database with entity resolution
based on (InChIKey, CAS RN) composite keys. The store tracks data provenance,
handles conflicts, and can export to KGX format for knowledge graph integration.

Usage:
    uv run python -m cmm_ai_automation.scripts.enrich_to_store -i data/private/normalized/ingredients.tsv
    uv run python -m cmm_ai_automation.scripts.enrich_to_store --dry-run
    uv run python -m cmm_ai_automation.scripts.enrich_to_store --export-kgx
"""

import csv
import logging
import sys
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv

from cmm_ai_automation.clients.cas import CASResult, get_cas_client
from cmm_ai_automation.clients.chebi import ChEBIClient, ChEBICompound, ChEBISearchResult
from cmm_ai_automation.clients.node_normalization import NodeNormalizationClient, NormalizedNode
from cmm_ai_automation.clients.pubchem import CompoundResult, PubChemClient
from cmm_ai_automation.store.enrichment_store import EnrichmentStore

# Load environment variables
load_dotenv()

# Default paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "private" / "normalized" / "ingredients.tsv"
DEFAULT_STORE = PROJECT_ROOT / "data" / "enrichment.duckdb"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "kgx" / "ingredients"

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def pubchem_to_dict(result: CompoundResult, query: str) -> dict[str, Any]:
    """Convert PubChem result to enrichment dict."""
    return {
        "name": result.Title or query,
        "pubchem_cid": result.CID,
        "inchikey": result.InChIKey,
        "smiles": result.CanonicalSMILES,
        "chemical_formula": result.MolecularFormula,
        "molecular_mass": result.MolecularWeight,
        "iupac_name": result.IUPACName,
    }


def chebi_to_dict(result: ChEBISearchResult, compound_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convert ChEBI result to enrichment dict.

    Args:
        result: ChEBI search result
        compound_data: Optional full compound data from get_compound_by_id
    """
    data: dict[str, Any] = {
        "name": result.name or result.ascii_name,
        "chebi_id": result.chebi_id,
    }

    # Add full compound data if available
    if compound_data:
        if compound_data.get("inchikey"):
            data["inchikey"] = compound_data["inchikey"]
        if compound_data.get("smiles"):
            data["smiles"] = compound_data["smiles"]
        if compound_data.get("chemical_formula"):
            data["chemical_formula"] = compound_data["chemical_formula"]
        if compound_data.get("molecular_mass"):
            data["molecular_mass"] = compound_data["molecular_mass"]
        if compound_data.get("definition"):
            data["description"] = compound_data["definition"]

        # Add roles
        roles = compound_data.get("chebi_ontology_roles", [])
        if roles:
            data["biological_roles"] = roles

    return data


def cas_to_dict(result: CASResult, query: str) -> dict[str, Any]:
    """Convert CAS result to enrichment dict."""
    data: dict[str, Any] = {
        "name": result.name or query,
        "cas_rn": result.rn,
        "is_mixture": result.is_mixture,
    }

    if result.inchikey:
        data["inchikey"] = result.inchikey
    if result.smiles:
        data["smiles"] = result.smiles
    if result.molecular_formula:
        data["chemical_formula"] = result.molecular_formula
    if result.molecular_mass:
        data["molecular_mass"] = result.molecular_mass

    return data


def node_norm_to_dict(result: NormalizedNode) -> dict[str, Any]:
    """Convert Node Normalization result to enrichment dict."""
    data: dict[str, Any] = {}

    # Extract IDs from equivalent_ids using helper methods
    chebi_ids = result.get_chebi_ids()
    if chebi_ids:
        data["chebi_id"] = f"CHEBI:{chebi_ids[0]}"

    pubchem_cids = result.get_pubchem_cids()
    if pubchem_cids:
        data["pubchem_cid"] = pubchem_cids[0]

    if result.cas_rn:
        data["cas_rn"] = result.cas_rn
    if result.inchikey:
        data["inchikey"] = result.inchikey

    return data


@click.command()
@click.option(
    "--input",
    "-i",
    "input_file",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_INPUT,
    help="Input TSV file with normalized ingredients",
)
@click.option(
    "--store",
    "-s",
    "store_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_STORE,
    help="Path to DuckDB enrichment store",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making API calls",
)
@click.option(
    "--export-kgx",
    is_flag=True,
    help="Export to KGX TSV format after enrichment",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT,
    help="Base path for KGX output (creates {path}_nodes.tsv and {path}_edges.tsv)",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    help="Limit number of ingredients to process (for testing)",
)
@click.option(
    "--no-pubchem",
    is_flag=True,
    help="Skip PubChem lookups",
)
@click.option(
    "--no-chebi",
    is_flag=True,
    help="Skip ChEBI lookups",
)
@click.option(
    "--no-cas",
    is_flag=True,
    help="Skip CAS lookups",
)
@click.option(
    "--no-node-norm",
    is_flag=True,
    help="Skip Node Normalization lookups",
)
def main(
    input_file: Path,
    store_path: Path,
    verbose: bool,
    dry_run: bool,
    export_kgx: bool,
    output_path: Path,
    limit: int | None,
    no_pubchem: bool,
    no_chebi: bool,
    no_cas: bool,
    no_node_norm: bool,
) -> None:
    """Multi-source enrichment pipeline with EnrichmentStore.

    Enriches ingredients by querying multiple APIs and storing results
    in a linkml-store backed database with entity resolution and provenance.

    Example:
        # Enrich all ingredients
        uv run python -m cmm_ai_automation.scripts.enrich_to_store

        # Test with first 5 ingredients
        uv run python -m cmm_ai_automation.scripts.enrich_to_store --limit 5 --verbose

        # Enrich and export to KGX
        uv run python -m cmm_ai_automation.scripts.enrich_to_store --export-kgx
    """
    setup_logging(verbose)

    # Read input ingredients
    click.echo(f"Reading ingredients from: {input_file}")
    with input_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        ingredients = list(reader)

    if limit:
        ingredients = ingredients[:limit]
        click.echo(f"Limited to first {limit} ingredients")

    click.echo(f"Found {len(ingredients)} ingredients to process")

    # Validate required columns
    if ingredients:
        required_columns = ["ingredient_name"]
        missing = [col for col in required_columns if col not in ingredients[0]]
        if missing:
            click.echo(f"ERROR: Missing required columns: {', '.join(missing)}")
            sys.exit(1)

    if dry_run:
        click.echo("\n[DRY RUN] Would enrich ingredients:")
        for ing in ingredients:
            name = ing.get("ingredient_name", "UNKNOWN")
            click.echo(f"  - {name}")
            if not no_pubchem:
                click.echo("    → PubChem: search by name")
            if not no_chebi:
                click.echo("    → ChEBI: search by name")
            if not no_cas:
                click.echo("    → CAS: search by name")
            if not no_node_norm:
                click.echo("    → Node Normalization: resolve IDs")
        return

    # Initialize store
    click.echo(f"\nInitializing enrichment store: {store_path}")
    store = EnrichmentStore(store_path=store_path)

    # Ensure schema includes all fields by inserting a dummy record with all fields
    # This forces linkml-store to create all columns in DuckDB
    # We'll delete this immediately after
    if (store_path.exists() and store_path.stat().st_size == 0) or not store_path.exists():
        click.echo("Initializing database schema with all fields...")
        dummy_record = {
            "name": "_schema_init_",
            "inchikey": "DUMMY",
            "cas_rn": "0-00-0",
            "chebi_id": "CHEBI:0",
            "pubchem_cid": 0,
            "mediadive_id": 0,
            "kegg_id": "C00000",
            "mesh_id": "D000000",
            "drugbank_id": "DB00000",
            "chemical_formula": "X",
            "smiles": "C",
            "inchi": "InChI=1S/X",
            "molecular_mass": 0.0,
            "monoisotopic_mass": 0.0,
            "charge": 0,
            "iupac_name": "dummy",
            "biological_roles": ["dummy"],
            "chemical_roles": ["dummy"],
            "application_roles": ["dummy"],
            "is_mixture": False,
        }
        store.upsert_ingredient(dummy_record, source="_schema_init_", query="_init_")
        # Delete the dummy record
        collection = store._get_collection()
        collection.delete_where({"id": "DUMMY|0-00-0"})
        click.echo("Schema initialized")

    # Initialize API clients
    pubchem_client = PubChemClient() if not no_pubchem else None
    chebi_client = ChEBIClient() if not no_chebi else None
    cas_client = get_cas_client() if not no_cas else None
    node_norm_client = NodeNormalizationClient() if not no_node_norm else None

    if cas_client:
        click.echo("CAS Common Chemistry API enabled")
    elif not no_cas:
        click.echo("CAS API key not found, skipping CAS lookups")

    # Track statistics
    stats = {
        "processed": 0,
        "pubchem_success": 0,
        "chebi_success": 0,
        "cas_success": 0,
        "node_norm_success": 0,
        "errors": 0,
    }

    # Process each ingredient
    for idx, ing in enumerate(ingredients, 1):
        name = ing["ingredient_name"]
        click.echo(f"\n[{idx}/{len(ingredients)}] Processing: {name}")

        stats["processed"] += 1

        # Collect data from all sources into a single dict for proper entity resolution
        # We'll track which sources contributed to the final record
        sources_data: dict[str, dict[str, Any]] = {}

        # 1. Query PubChem
        if pubchem_client:
            click.echo("  → PubChem: ", nl=False)
            try:
                results = pubchem_client.get_compounds_by_name(name)
                if isinstance(results, list) and results:
                    click.echo(f"Found {len(results)} compound(s)")
                    # Take first result for now (could handle multiple)
                    result = results[0]
                    sources_data["pubchem"] = pubchem_to_dict(result, name)
                    stats["pubchem_success"] += 1
                else:
                    click.echo("No results")
            except Exception as e:
                click.echo(f"ERROR: {e}")
                logger.debug(f"PubChem error for {name}", exc_info=True)
                stats["errors"] += 1

        # 2. Query ChEBI
        if chebi_client:
            click.echo("  → ChEBI: ", nl=False)
            try:
                chebi_result = chebi_client.search_exact(name)
                if isinstance(chebi_result, ChEBISearchResult):
                    click.echo(f"Found {chebi_result.chebi_id}")
                    # Get full compound details for roles
                    compound = chebi_client.get_compound(chebi_result.chebi_id)
                    compound_dict = compound.to_dict() if isinstance(compound, ChEBICompound) else None
                    sources_data["chebi"] = chebi_to_dict(chebi_result, compound_dict)
                    stats["chebi_success"] += 1
                else:
                    click.echo("No exact match")
            except Exception as e:
                click.echo(f"ERROR: {e}")
                logger.debug(f"ChEBI error for {name}", exc_info=True)
                stats["errors"] += 1

        # 3. Query CAS
        if cas_client:
            click.echo("  → CAS: ", nl=False)
            try:
                cas_results = cas_client.search_by_name(name)
                if isinstance(cas_results, list) and cas_results:
                    cas_result = cas_results[0]
                    click.echo(f"Found {cas_result.rn} (mixture={cas_result.is_mixture})")
                    sources_data["cas"] = cas_to_dict(cas_result, name)
                    stats["cas_success"] += 1
                else:
                    click.echo("No results")
            except Exception as e:
                click.echo(f"ERROR: {e}")
                logger.debug(f"CAS error for {name}", exc_info=True)
                stats["errors"] += 1

        # Merge all source data into a single record for this ingredient
        # This ensures proper entity resolution and one record per ingredient
        if sources_data:
            # Start with the first source's data as base
            merged_data: dict[str, Any] = {}

            # Merge all fields from all sources
            for _source, data in sources_data.items():
                for key, value in data.items():
                    if value is not None and key not in merged_data:
                        merged_data[key] = value

            # Now upsert the merged data for each source to track provenance
            # This ensures the store has proper source_records tracking
            for source, data in sources_data.items():
                # Upsert with the merged key fields so all sources update the same record
                data_with_keys = {**data}
                # Add the InChIKey and CAS RN from merged data if not present in source data
                if "inchikey" not in data_with_keys and merged_data.get("inchikey"):
                    data_with_keys["inchikey"] = merged_data["inchikey"]
                if "cas_rn" not in data_with_keys and merged_data.get("cas_rn"):
                    data_with_keys["cas_rn"] = merged_data["cas_rn"]

                store.upsert_ingredient(data_with_keys, source=source, query=name)

        # 4. Query Node Normalization (if we collected any IDs)
        if node_norm_client and sources_data:
            # Check what IDs we got from any source
            chebi_id = None
            pubchem_cid = None
            for source_data in sources_data.values():
                if not chebi_id and source_data.get("chebi_id"):
                    chebi_id = source_data["chebi_id"]
                if not pubchem_cid and source_data.get("pubchem_cid"):
                    pubchem_cid = source_data["pubchem_cid"]

            if chebi_id or pubchem_cid:
                click.echo("  → Node Normalization: ", nl=False)
                try:
                    query_id = chebi_id if chebi_id else f"PUBCHEM.COMPOUND:{pubchem_cid}"
                    node_norm_result = node_norm_client.normalize(query_id)

                    if isinstance(node_norm_result, NormalizedNode):
                        click.echo(f"Resolved {len(node_norm_result.equivalent_ids)} IDs")
                        data = node_norm_to_dict(node_norm_result)
                        if data:  # Only upsert if we got new data
                            store.upsert_ingredient(data, source="node_normalization", query=query_id)
                            stats["node_norm_success"] += 1
                    else:
                        click.echo("No normalization found")
                except Exception as e:
                    click.echo(f"ERROR: {e}")
                    logger.debug(f"Node Normalization error for {name}", exc_info=True)
                    stats["errors"] += 1

    # Print statistics
    click.echo("\n" + "=" * 60)
    click.echo("Enrichment Statistics:")
    click.echo("=" * 60)
    click.echo(f"  Ingredients processed:    {stats['processed']}")
    click.echo(f"  PubChem successes:        {stats['pubchem_success']}")
    click.echo(f"  ChEBI successes:          {stats['chebi_success']}")
    click.echo(f"  CAS successes:            {stats['cas_success']}")
    click.echo(f"  Node Norm successes:      {stats['node_norm_success']}")
    click.echo(f"  Errors encountered:       {stats['errors']}")

    # Get store statistics
    store_stats = store.get_stats()
    click.echo("\n" + "=" * 60)
    click.echo("EnrichmentStore Statistics:")
    click.echo("=" * 60)
    click.echo(f"  Total ingredients:        {store_stats['total_ingredients']}")
    click.echo(f"  With ChEBI ID:            {store_stats['with_chebi_id']} ({store_stats['coverage_chebi']:.1%})")
    click.echo(f"  With PubChem CID:         {store_stats['with_pubchem_cid']} ({store_stats['coverage_pubchem']:.1%})")
    click.echo(f"  With CAS RN:              {store_stats['with_cas_rn']} ({store_stats['coverage_cas']:.1%})")
    click.echo(f"  With InChIKey:            {store_stats['with_inchikey']}")
    click.echo(f"  With biological roles:    {store_stats['with_biological_roles']}")
    click.echo(f"  With conflicts:           {store_stats['with_conflicts']}")

    # Export to KGX if requested
    if export_kgx:
        click.echo("\n" + "=" * 60)
        click.echo("Exporting to KGX format...")
        click.echo("=" * 60)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        nodes_count, edges_count = store.export_to_kgx(output_path)
        click.echo(f"\n✓ Exported {nodes_count} nodes and {edges_count} edges")
        click.echo(f"  Nodes: {output_path}_nodes.tsv")
        click.echo(f"  Edges: {output_path}_edges.tsv")

    store.close()

    if stats["errors"] > 0:
        click.echo(f"\n⚠ Completed with {stats['errors']} error(s)")
        sys.exit(1)
    else:
        click.echo("\n✓ Enrichment completed successfully!")


if __name__ == "__main__":
    main()
