#!/usr/bin/env python3
"""Enrich ingredients with PubChem data.

Reads an ingredients TSV file and queries PubChem for each ingredient,
adding chemical identifiers like InChIKey, CID, and SMILES.

Uses a JSON cache to avoid re-querying PubChem for compounds we've already looked up.
"""

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any

import click

from cmm_ai_automation.clients.pubchem import CompoundResult, LookupError, PubChemClient

# Default paths relative to project root
# __file__ is src/cmm_ai_automation/scripts/enrich_ingredients.py
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "private" / "normalized" / "ingredients.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "private" / "enriched" / "ingredients_enriched.tsv"
DEFAULT_CACHE = PROJECT_ROOT / "data" / "private" / "enriched" / "pubchem_cache.json"

logger = logging.getLogger(__name__)


def load_cache(cache_file: Path) -> dict[str, Any]:
    """Load cache from JSON file."""
    if cache_file.exists():
        with cache_file.open(encoding="utf-8") as f:
            cache: dict[str, Any] = json.load(f)
            return cache
    return {}


def save_cache(cache_file: Path, cache: dict[str, Any]) -> None:
    """Save cache to JSON file."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


@click.command()
@click.option(
    "--input",
    "-i",
    "input_file",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_INPUT,
    help="Input TSV file with ingredients",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT,
    help="Output TSV file with enriched data",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
@click.option(
    "--cache",
    "-c",
    "cache_file",
    type=click.Path(path_type=Path),
    default=DEFAULT_CACHE,
    help="JSON cache file for PubChem lookups",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable cache (always query PubChem)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making API calls",
)
def main(
    input_file: Path,
    output_file: Path,
    verbose: bool,
    cache_file: Path,
    no_cache: bool,
    dry_run: bool,
) -> None:
    """Enrich ingredients with PubChem data.

    Reads ingredients from a TSV file, queries PubChem for each one,
    and writes enriched data with chemical identifiers.
    """
    setup_logging(verbose)

    # Read input file
    click.echo(f"Reading ingredients from: {input_file}")
    with input_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        ingredients = list(reader)

    click.echo(f"Found {len(ingredients)} ingredients")

    if dry_run:
        click.echo("\n[DRY RUN] Would query PubChem for:")
        for ing in ingredients:
            click.echo(f"  - {ing['ingredient_name']}")
        return

    # Load cache
    cache: dict[str, Any] = {}
    if not no_cache:
        cache = load_cache(cache_file)
        click.echo(f"Loaded {len(cache)} cached entries from: {cache_file}")

    # Create PubChem client
    client = PubChemClient()

    # Process ingredients
    enriched = []
    success_count = 0
    error_count = 0
    cache_hit_count = 0

    for ing in ingredients:
        name = ing["ingredient_name"]

        # Check cache first
        if not no_cache and name in cache:
            cached = cache[name]
            click.echo(f"Looking up: {name}... CACHED (CID:{cached.get('pubchem_cid', 'N/A')})")
            enriched.append({**ing, **cached})
            if cached.get("pubchem_error"):
                error_count += 1
            else:
                success_count += 1
            cache_hit_count += 1
            continue

        # Query PubChem
        click.echo(f"Looking up: {name}... ", nl=False)
        result = client.get_compound_by_name(name)

        if isinstance(result, CompoundResult):
            click.echo(f"CID:{result.CID}")
            result_dict = {
                "pubchem_cid": str(result.CID),
                "pubchem_inchikey": result.InChIKey or "",
                "pubchem_canonical_smiles": result.CanonicalSMILES or "",
                "pubchem_molecular_formula": result.MolecularFormula or "",
                "pubchem_iupac_name": result.IUPACName or "",
                "pubchem_title": result.Title or "",
                "pubchem_error": "",
            }
            enriched.append({**ing, **result_dict})
            cache[name] = result_dict
            success_count += 1
        elif isinstance(result, LookupError):
            click.echo(f"ERROR: {result.error_code}")
            result_dict = {
                "pubchem_cid": "",
                "pubchem_inchikey": "",
                "pubchem_canonical_smiles": "",
                "pubchem_molecular_formula": "",
                "pubchem_iupac_name": "",
                "pubchem_title": "",
                "pubchem_error": f"{result.error_code}: {result.error_message}",
            }
            enriched.append({**ing, **result_dict})
            cache[name] = result_dict
            error_count += 1

    # Save cache
    if not no_cache:
        save_cache(cache_file, cache)
        click.echo(f"Saved {len(cache)} entries to cache: {cache_file}")

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    click.echo(f"\nWriting enriched data to: {output_file}")

    fieldnames = [
        "ingredient_uuid",
        "ingredient_name",
        "pubchem_cid",
        "pubchem_inchikey",
        "pubchem_canonical_smiles",
        "pubchem_molecular_formula",
        "pubchem_iupac_name",
        "pubchem_title",
        "pubchem_error",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched)

    # Summary
    click.echo()
    click.echo("Summary:")
    click.echo(f"  Success:    {success_count}")
    click.echo(f"  Errors:     {error_count}")
    click.echo(f"  Cache hits: {cache_hit_count}")
    click.echo(f"  Total:      {len(enriched)}")

    if error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
