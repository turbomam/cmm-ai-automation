#!/usr/bin/env python3
"""Export MediaDive data to KGX format.

Creates KGX-formatted files for MediaDive entities and relationships:

Nodes:
- mediadive.ingredient:{id} - Chemical ingredients (biolink:ChemicalEntity)
- mediadive.solution:{id} - Stock solutions (biolink:ChemicalMixture)
- mediadive.medium:{id} - Growth media (METPO:1004005)

Edges:
- medium -[RO:0001019 contains]-> ingredient (with concentration)
- medium -[RO:0001019 contains]-> solution (with volume)
- solution -[RO:0001019 contains]-> ingredient (with concentration)
- strain -[METPO:2000517 grows_in]-> medium (from medium_strains)
- mediadive.ingredient -[biolink:same_as]-> CHEBI:* (where mapped)

Uses KGX Transformer and Sink classes for proper serialization.
Integrates with LinkML schema via aligned dataclass fields.

Usage:
    uv run python -m cmm_ai_automation.scripts.export_mediadive_kgx
    uv run python -m cmm_ai_automation.scripts.export_mediadive_kgx --format jsonl
    uv run python -m cmm_ai_automation.scripts.export_mediadive_kgx --dry-run
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import click
from kgx.sink import JsonlSink, TsvSink
from kgx.transformer import Transformer

from cmm_ai_automation.clients.mediadive_mongodb import (
    MediaDiveMongoClient,
    MediaDiveMongoIngredient,
    MediaDiveMongoMedium,
    MediaDiveMongoRecipeItem,
    MediaDiveMongoSolution,
    MediaDiveMongoStrainGrowth,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "kgx"

# =============================================================================
# Biolink/METPO categories and predicates
# =============================================================================

# Node categories (from Biolink Model and METPO)
INGREDIENT_CATEGORY = "biolink:ChemicalEntity"
INGREDIENT_CATEGORY_LABEL = "chemical entity"
SOLUTION_CATEGORY = "biolink:ChemicalMixture"
SOLUTION_CATEGORY_LABEL = "chemical mixture"
MEDIUM_CATEGORY = "METPO:1004005"
MEDIUM_CATEGORY_LABEL = "growth medium"

# Edge predicates
CONTAINS_PREDICATE = "RO:0001019"  # contains
CONTAINS_LABEL = "contains"
GROWS_IN_PREDICATE = "METPO:2000517"
GROWS_IN_LABEL = "grows in medium"
SAME_AS_PREDICATE = "biolink:same_as"
SAME_AS_LABEL = "same as"

# Provenance metadata (Biolink enum values)
KNOWLEDGE_LEVEL = "knowledge_assertion"
AGENT_TYPE = "manual_agent"
PROVIDED_BY = "mediadive"


# =============================================================================
# KGX Node/Edge dataclasses
# =============================================================================


@dataclass
class IngredientNode:
    """KGX node for a MediaDive ingredient.

    Aligns with LinkML Ingredient class.
    """

    id: str  # mediadive.ingredient:{id}
    name: str
    category: str = INGREDIENT_CATEGORY
    category_label: str = INGREDIENT_CATEGORY_LABEL
    # Chemical identifiers (xrefs)
    chebi_id: str | None = None
    pubchem_cid: int | None = None
    cas_rn: str | None = None
    kegg_id: str | None = None
    # Properties
    formula: str | None = None
    mass: float | None = None
    is_complex: bool = False

    def to_kgx_node(self) -> dict[str, Any]:
        """Convert to KGX node dict for use with KGX Sink.write_node()."""
        node: dict[str, Any] = {
            "id": self.id,
            "category": [self.category],
            "category_label": [self.category_label],
            "name": self.name,
            "provided_by": [PROVIDED_BY],
        }
        # Add xrefs as pipe-separated list
        xrefs = []
        if self.chebi_id:
            xrefs.append(f"CHEBI:{self.chebi_id}")
        if self.pubchem_cid:
            xrefs.append(f"PUBCHEM.COMPOUND:{self.pubchem_cid}")
        if self.cas_rn:
            xrefs.append(f"CAS:{self.cas_rn}")
        if self.kegg_id:
            xrefs.append(f"KEGG.COMPOUND:{self.kegg_id}")
        if xrefs:
            node["xref"] = xrefs

        if self.formula:
            node["chemical_formula"] = self.formula
        if self.mass:
            node["molecular_mass"] = self.mass
        if self.is_complex:
            node["is_complex_mixture"] = True

        return node


@dataclass
class SolutionNode:
    """KGX node for a MediaDive solution.

    Aligns with LinkML Solution class.
    """

    id: str  # mediadive.solution:{id}
    name: str
    category: str = SOLUTION_CATEGORY
    category_label: str = SOLUTION_CATEGORY_LABEL
    volume: float | None = None

    def to_kgx_node(self) -> dict[str, Any]:
        """Convert to KGX node dict."""
        node: dict[str, Any] = {
            "id": self.id,
            "category": [self.category],
            "category_label": [self.category_label],
            "name": self.name,
            "provided_by": [PROVIDED_BY],
        }
        if self.volume:
            node["volume_ml"] = self.volume
        return node


@dataclass
class MediumNode:
    """KGX node for a MediaDive growth medium.

    Aligns with LinkML GrowthMedium class.
    """

    id: str  # mediadive.medium:{id}
    name: str
    category: str = MEDIUM_CATEGORY
    category_label: str = MEDIUM_CATEGORY_LABEL
    # Properties from LinkML GrowthMedium
    medium_type: str | None = None  # complex or defined
    min_ph: float | None = None
    max_ph: float | None = None
    source: str | None = None
    source_reference: str | None = None  # URL to source

    def to_kgx_node(self) -> dict[str, Any]:
        """Convert to KGX node dict."""
        node: dict[str, Any] = {
            "id": self.id,
            "category": [self.category],
            "category_label": [self.category_label],
            "name": self.name,
            "provided_by": [PROVIDED_BY],
        }
        if self.medium_type:
            node["medium_type"] = self.medium_type
        if self.min_ph is not None:
            node["min_ph"] = self.min_ph
        if self.max_ph is not None:
            node["max_ph"] = self.max_ph
        if self.source:
            node["source"] = self.source
        if self.source_reference:
            node["source_reference"] = self.source_reference
        return node


@dataclass
class CompositionEdge:
    """Edge representing composition (contains) relationship.

    Used for:
    - medium contains ingredient
    - medium contains solution
    - solution contains ingredient
    """

    subject: str  # Medium or solution CURIE
    object: str  # Ingredient or solution CURIE
    predicate: str = CONTAINS_PREDICATE
    predicate_label: str = CONTAINS_LABEL
    # Edge properties (from LinkML IngredientComponent/SolutionComponent)
    concentration_value: float | None = None
    concentration_unit: str | None = None
    optional: bool = False

    def to_kgx_edge(self) -> dict[str, Any]:
        """Convert to KGX edge dict."""
        edge: dict[str, Any] = {
            "subject": self.subject,
            "predicate": self.predicate,
            "relation_label": self.predicate_label,
            "object": self.object,
            "knowledge_level": KNOWLEDGE_LEVEL,
            "agent_type": AGENT_TYPE,
        }
        if self.concentration_value is not None and self.concentration_unit:
            edge["concentration"] = f"{self.concentration_value} {self.concentration_unit}"
        if self.optional:
            edge["optional"] = True
        return edge


@dataclass
class GrowthEdge:
    """Edge representing strain grows in medium.

    Aligns with LinkML GrowthPreference class.
    """

    subject: str  # Strain CURIE (bacdive.strain:*)
    object: str  # Medium CURIE (mediadive.medium:*)
    predicate: str = GROWS_IN_PREDICATE
    predicate_label: str = GROWS_IN_LABEL
    # Strain metadata for provenance
    species: str | None = None
    ccno: str | None = None  # Culture collection number

    def to_kgx_edge(self) -> dict[str, Any]:
        """Convert to KGX edge dict."""
        edge: dict[str, Any] = {
            "subject": self.subject,
            "predicate": self.predicate,
            "relation_label": self.predicate_label,
            "object": self.object,
            "knowledge_level": KNOWLEDGE_LEVEL,
            "agent_type": AGENT_TYPE,
        }
        if self.species:
            edge["species"] = self.species
        if self.ccno:
            edge["culture_collection_id"] = self.ccno
        return edge


@dataclass
class SameAsEdge:
    """Edge representing identity mapping between databases.

    Used to link MediaDive ingredients to ChEBI/PubChem.
    """

    subject: str  # mediadive.ingredient:*
    object: str  # CHEBI:* or PUBCHEM.COMPOUND:*
    predicate: str = SAME_AS_PREDICATE
    predicate_label: str = SAME_AS_LABEL

    def to_kgx_edge(self) -> dict[str, Any]:
        """Convert to KGX edge dict."""
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "relation_label": self.predicate_label,
            "object": self.object,
            "knowledge_level": KNOWLEDGE_LEVEL,
            "agent_type": AGENT_TYPE,
        }


# =============================================================================
# Export result containers
# =============================================================================


@dataclass
class ExportResult:
    """Container for export statistics."""

    ingredient_nodes: int = 0
    solution_nodes: int = 0
    medium_nodes: int = 0
    composition_edges: int = 0
    growth_edges: int = 0
    same_as_edges: int = 0

    def total_nodes(self) -> int:
        return self.ingredient_nodes + self.solution_nodes + self.medium_nodes

    def total_edges(self) -> int:
        return self.composition_edges + self.growth_edges + self.same_as_edges


# =============================================================================
# Conversion functions
# =============================================================================


def ingredient_to_node(ingredient: MediaDiveMongoIngredient) -> IngredientNode:
    """Convert MediaDive ingredient to KGX node."""
    return IngredientNode(
        id=f"mediadive.ingredient:{ingredient.id}",
        name=ingredient.name,
        chebi_id=str(ingredient.chebi) if ingredient.chebi else None,
        pubchem_cid=ingredient.pubchem,
        cas_rn=ingredient.cas_rn,
        kegg_id=ingredient.kegg,
        formula=ingredient.formula,
        mass=ingredient.mass,
        is_complex=ingredient.is_complex,
    )


def solution_to_node(solution: MediaDiveMongoSolution) -> SolutionNode:
    """Convert MediaDive solution to KGX node."""
    return SolutionNode(
        id=f"mediadive.solution:{solution.id}",
        name=solution.name,
        volume=solution.volume,
    )


def medium_to_node(medium: MediaDiveMongoMedium) -> MediumNode:
    """Convert MediaDive medium to KGX node."""
    medium_type = "complex" if medium.complex_medium else "defined"

    return MediumNode(
        id=f"mediadive.medium:{medium.id}",
        name=medium.name,
        medium_type=medium_type,
        min_ph=medium.min_ph,
        max_ph=medium.max_ph,
        source=medium.source,
        source_reference=medium.link,
    )


def recipe_item_to_edge(
    parent_curie: str,
    item: MediaDiveMongoRecipeItem,
) -> CompositionEdge | None:
    """Convert recipe item to composition edge.

    Args:
        parent_curie: CURIE of the containing medium or solution
        item: Recipe item data

    Returns:
        CompositionEdge or None if no valid target
    """
    # Determine the object (ingredient or solution)
    if item.solution_id:
        object_curie = f"mediadive.solution:{item.solution_id}"
    elif item.compound_id:
        object_curie = f"mediadive.ingredient:{item.compound_id}"
    else:
        # No valid target ID
        return None

    # Determine concentration
    concentration_value = item.g_l or item.mmol_l or item.amount
    concentration_unit = None
    if item.g_l:
        concentration_unit = "g/L"
    elif item.mmol_l:
        concentration_unit = "mmol/L"
    elif item.amount and item.unit:
        concentration_unit = item.unit

    return CompositionEdge(
        subject=parent_curie,
        object=object_curie,
        concentration_value=concentration_value,
        concentration_unit=concentration_unit,
        optional=item.optional,
    )


def strain_growth_to_edge(
    medium_id: int,
    strain: MediaDiveMongoStrainGrowth,
) -> GrowthEdge | None:
    """Convert strain growth record to grows_in edge.

    Args:
        medium_id: MediaDive medium ID
        strain: Strain growth data

    Returns:
        GrowthEdge or None if strain doesn't grow or no BacDive ID
    """
    # Only create edge if strain grows and has BacDive ID
    if not strain.growth:
        return None
    if not strain.bacdive_id:
        return None

    return GrowthEdge(
        subject=f"bacdive.strain:{strain.bacdive_id}",
        object=f"mediadive.medium:{medium_id}",
        species=strain.species,
        ccno=strain.ccno,
    )


def ingredient_to_same_as_edges(ingredient: MediaDiveMongoIngredient) -> list[SameAsEdge]:
    """Create same_as edges for ingredient xrefs.

    Args:
        ingredient: MediaDive ingredient with potential xrefs

    Returns:
        List of SameAsEdge objects
    """
    edges = []
    subject = f"mediadive.ingredient:{ingredient.id}"

    # ChEBI is highest priority for chemical identity
    if ingredient.chebi:
        edges.append(SameAsEdge(subject=subject, object=f"CHEBI:{ingredient.chebi}"))

    # PubChem as secondary
    if ingredient.pubchem:
        edges.append(SameAsEdge(subject=subject, object=f"PUBCHEM.COMPOUND:{ingredient.pubchem}"))

    return edges


# =============================================================================
# Main export functions
# =============================================================================


def export_all(
    client: MediaDiveMongoClient,
    output_path: Path,
    output_format: Literal["tsv", "jsonl"] = "tsv",
    include_same_as: bool = True,
) -> ExportResult:
    """Export all MediaDive data to KGX format.

    Args:
        client: MediaDive MongoDB client
        output_path: Base path for output files
        output_format: Output format (tsv or jsonl)
        include_same_as: Whether to include same_as edges for xrefs

    Returns:
        ExportResult with counts
    """
    result = ExportResult()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create KGX transformer and sink
    transformer = Transformer()

    node_props = {
        "id",
        "category",
        "category_label",
        "name",
        "provided_by",
        "xref",
        "chemical_formula",
        "molecular_mass",
        "is_complex_mixture",
        "volume_ml",
        "medium_type",
        "min_ph",
        "max_ph",
        "source",
        "source_reference",
    }
    edge_props = {
        "subject",
        "predicate",
        "relation_label",
        "object",
        "knowledge_level",
        "agent_type",
        "concentration",
        "optional",
        "species",
        "culture_collection_id",
    }

    if output_format == "jsonl":
        sink = JsonlSink(owner=transformer, filename=str(output_path))
    else:
        sink = TsvSink(
            owner=transformer,
            filename=str(output_path),
            format="tsv",
            node_properties=node_props,
            edge_properties=edge_props,
        )

    # --- Export Ingredients ---
    logger.info("Exporting ingredients...")
    ingredients = client.get_all_ingredients()
    ingredient_ids: set[int] = set()

    for ing in ingredients:
        ing_node = ingredient_to_node(ing)
        sink.write_node(ing_node.to_kgx_node())
        result.ingredient_nodes += 1
        ingredient_ids.add(ing.id)

        # Same-as edges for xrefs
        if include_same_as:
            for same_as_edge in ingredient_to_same_as_edges(ing):
                sink.write_edge(same_as_edge.to_kgx_edge())
                result.same_as_edges += 1

    logger.info(f"  Exported {result.ingredient_nodes} ingredient nodes")
    logger.info(f"  Created {result.same_as_edges} same_as edges")

    # --- Export Solutions ---
    logger.info("Exporting solutions...")
    solutions = client.get_all_solution_details()
    solution_ids: set[int] = set()

    for sol in solutions:
        sol_node = solution_to_node(sol)
        sink.write_node(sol_node.to_kgx_node())
        result.solution_nodes += 1
        solution_ids.add(sol.id)

        # Composition edges for solution ingredients
        for item_data in sol.recipe:
            item = client._parse_recipe_item(item_data)
            comp_edge = recipe_item_to_edge(f"mediadive.solution:{sol.id}", item)
            if comp_edge:
                sink.write_edge(comp_edge.to_kgx_edge())
                result.composition_edges += 1

    logger.info(f"  Exported {result.solution_nodes} solution nodes")

    # --- Export Media ---
    logger.info("Exporting media...")
    media = client.get_all_media()

    for med in media:
        med_node = medium_to_node(med)
        sink.write_node(med_node.to_kgx_node())
        result.medium_nodes += 1

    logger.info(f"  Exported {result.medium_nodes} medium nodes")

    # --- Export Strain-Medium Growth Relationships ---
    logger.info("Exporting strain-medium growth edges...")
    medium_strain_data = client.get_all_medium_strain_relationships()

    for medium_id, strains in medium_strain_data:
        for strain in strains:
            growth_edge = strain_growth_to_edge(medium_id, strain)
            if growth_edge:
                sink.write_edge(growth_edge.to_kgx_edge())
                result.growth_edges += 1

    logger.info(f"  Created {result.growth_edges} grows_in edges")
    logger.info(f"  Created {result.composition_edges} composition edges")

    # Finalize
    sink.finalize()

    return result


def dry_run_export(client: MediaDiveMongoClient) -> ExportResult:
    """Perform a dry run to gather statistics without writing files.

    Args:
        client: MediaDive MongoDB client

    Returns:
        ExportResult with counts
    """
    result = ExportResult()

    # Count ingredients
    ingredients = client.get_all_ingredients()
    result.ingredient_nodes = len(ingredients)

    same_as_count = 0
    for ing in ingredients:
        if ing.chebi:
            same_as_count += 1
        if ing.pubchem:
            same_as_count += 1
    result.same_as_edges = same_as_count

    # Count solutions
    solutions = client.get_all_solution_details()
    result.solution_nodes = len(solutions)

    # Count composition edges from solutions
    for sol in solutions:
        for item in sol.recipe:
            if item.get("compound_id") or item.get("solution_id"):
                result.composition_edges += 1

    # Count media
    media = client.get_all_media()
    result.medium_nodes = len(media)

    # Count growth edges
    medium_strains = client.get_all_medium_strain_relationships()
    for _medium_id, strains in medium_strains:
        for strain in strains:
            if strain.growth and strain.bacdive_id:
                result.growth_edges += 1

    return result


# =============================================================================
# CLI
# =============================================================================


@click.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=OUTPUT_DIR / "mediadive",
    help="Output base path (KGX creates _nodes and _edges files)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["tsv", "jsonl"]),
    default="tsv",
    help="Output format",
)
@click.option(
    "--no-same-as",
    is_flag=True,
    help="Skip same_as edges for ingredient xrefs",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Parse data and show statistics without writing files",
)
@click.option(
    "--mongodb-uri",
    default="mongodb://localhost:27017",
    help="MongoDB connection URI",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def main(
    output: Path,
    output_format: Literal["tsv", "jsonl"],
    no_same_as: bool,
    dry_run: bool,
    mongodb_uri: str,
    verbose: bool,
) -> None:
    """Export MediaDive data to KGX format.

    Exports ingredients, solutions, and media as nodes, with composition
    and growth relationship edges.

    Requires MediaDive data loaded in MongoDB (run load_mediadive_mongodb.py first).
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    click.echo("=" * 60)
    click.echo("Export MediaDive to KGX")
    click.echo("=" * 60)
    click.echo()

    # Connect to MongoDB
    client = MediaDiveMongoClient(mongodb_uri=mongodb_uri)

    # Check data availability
    ingredient_count = client.get_ingredient_count()
    solution_count = client.get_solution_count()
    medium_count = client.get_medium_count()

    click.echo("MongoDB data:")
    click.echo(f"  Ingredients: {ingredient_count}")
    click.echo(f"  Solutions:   {solution_count}")
    click.echo(f"  Media:       {medium_count}")
    click.echo()

    if ingredient_count == 0 and solution_count == 0 and medium_count == 0:
        click.echo("ERROR: No data found in MongoDB. Run load_mediadive_mongodb.py first.", err=True)
        client.close()
        raise click.Abort()

    if dry_run:
        click.echo("Performing dry run...")
        result = dry_run_export(client)
    else:
        click.echo(f"Exporting to {output}...")
        result = export_all(
            client,
            output,
            output_format,
            include_same_as=not no_same_as,
        )

    client.close()

    # Summary
    click.echo()
    click.echo("=" * 60)
    click.echo("Summary")
    click.echo("=" * 60)
    click.echo()
    click.echo("Nodes:")
    click.echo(f"  Ingredients:   {result.ingredient_nodes} (mediadive.ingredient:*)")
    click.echo(f"  Solutions:     {result.solution_nodes} (mediadive.solution:*)")
    click.echo(f"  Media:         {result.medium_nodes} (mediadive.medium:*)")
    click.echo(f"  Total:         {result.total_nodes()}")
    click.echo()
    click.echo("Edges:")
    click.echo(f"  Composition:   {result.composition_edges} (RO:0001019 contains)")
    click.echo(f"  Growth:        {result.growth_edges} (METPO:2000517 grows_in)")
    click.echo(f"  Same-as:       {result.same_as_edges} (biolink:same_as)")
    click.echo(f"  Total:         {result.total_edges()}")
    click.echo()

    if dry_run:
        click.echo("[DRY RUN] No files written.")
    else:
        ext = "jsonl" if output_format == "jsonl" else "tsv"
        click.echo("Output files:")
        click.echo(f"  {output}_nodes.{ext}")
        click.echo(f"  {output}_edges.{ext}")
        click.echo()
        click.echo("To validate:")
        click.echo(f"  kgx validate {output}_nodes.{ext} {output}_edges.{ext}")

    click.echo()
    click.echo("Done!")


if __name__ == "__main__":
    main()
