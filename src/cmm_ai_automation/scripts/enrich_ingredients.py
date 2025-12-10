#!/usr/bin/env python3
"""Enrich ingredients with PubChem data.

Reads an ingredients TSV file and queries PubChem for each ingredient,
adding chemical identifiers like InChIKey, CID, and SMILES.
"""

import csv
import logging
import sys
from pathlib import Path

import click

from cmm_ai_automation.clients.pubchem import CompoundResult, LookupError, PubChemClient

# Default paths relative to project root
# __file__ is src/cmm_ai_automation/scripts/enrich_ingredients.py
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "private" / "normalized" / "ingredients.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "private" / "enriched" / "ingredients_enriched.tsv"

logger = logging.getLogger(__name__)


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
    "--skip-no-chebi",
    is_flag=True,
    default=True,
    help="Skip ingredients marked as no_chebi (undefined mixtures)",
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
def main(
    input_file: Path,
    output_file: Path,
    skip_no_chebi: bool,
    verbose: bool,
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

    # Count skippable ingredients
    no_chebi_count = sum(1 for ing in ingredients if ing.get("needs_curation") == "no_chebi")
    if skip_no_chebi:
        click.echo(f"Will skip {no_chebi_count} undefined mixtures (no_chebi)")

    if dry_run:
        click.echo("\n[DRY RUN] Would query PubChem for:")
        for ing in ingredients:
            if skip_no_chebi and ing.get("needs_curation") == "no_chebi":
                continue
            click.echo(f"  - {ing['ingredient_name']}")
        return

    # Create PubChem client
    client = PubChemClient()

    # Process ingredients
    enriched = []
    success_count = 0
    error_count = 0
    skip_count = 0

    for ing in ingredients:
        name = ing["ingredient_name"]

        # Skip undefined mixtures
        if skip_no_chebi and ing.get("needs_curation") == "no_chebi":
            logger.debug(f"Skipping undefined mixture: {name}")
            enriched.append({
                **ing,
                "pubchem_cid": "",
                "pubchem_inchikey": "",
                "pubchem_canonical_smiles": "",
                "pubchem_molecular_formula": "",
                "pubchem_iupac_name": "",
                "pubchem_title": "",
                "pubchem_error": "SKIPPED_NO_CHEBI",
            })
            skip_count += 1
            continue

        # Query PubChem
        click.echo(f"Looking up: {name}... ", nl=False)
        result = client.get_compound_by_name(name)

        if isinstance(result, CompoundResult):
            click.echo(f"CID:{result.CID}")
            enriched.append({
                **ing,
                "pubchem_cid": str(result.CID),
                "pubchem_inchikey": result.InChIKey or "",
                "pubchem_canonical_smiles": result.CanonicalSMILES or "",
                "pubchem_molecular_formula": result.MolecularFormula or "",
                "pubchem_iupac_name": result.IUPACName or "",
                "pubchem_title": result.Title or "",
                "pubchem_error": "",
            })
            success_count += 1
        elif isinstance(result, LookupError):
            click.echo(f"ERROR: {result.error_code}")
            enriched.append({
                **ing,
                "pubchem_cid": "",
                "pubchem_inchikey": "",
                "pubchem_canonical_smiles": "",
                "pubchem_molecular_formula": "",
                "pubchem_iupac_name": "",
                "pubchem_title": "",
                "pubchem_error": f"{result.error_code}: {result.error_message}",
            })
            error_count += 1

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    click.echo(f"\nWriting enriched data to: {output_file}")

    fieldnames = [
        "ingredient_uuid",
        "ingredient_name",
        "chemical_formula",
        "needs_curation",
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
    click.echo(f"  Success: {success_count}")
    click.echo(f"  Errors:  {error_count}")
    click.echo(f"  Skipped: {skip_count}")
    click.echo(f"  Total:   {len(enriched)}")

    if error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
