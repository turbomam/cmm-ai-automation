#!/usr/bin/env python3
"""Validate and fix Delaney media KGX files for Biolink/KGX compliance.

This script:
1. Validates nodes and edges against KGX/Biolink requirements
2. Fixes common issues (capitalization, missing required fields)
3. Creates missing nodes for edge objects
4. Generates validation reports

Usage:
    uv run python -m cmm_ai_automation.scripts.validate_fix_delaney_kgx
    uv run python -m cmm_ai_automation.scripts.validate_fix_delaney_kgx --validate-only
    uv run python -m cmm_ai_automation.scripts.validate_fix_delaney_kgx --output-dir output/kgx/
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError

from cmm_ai_automation.transform.kgx import KGXEdge, KGXNode

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Default paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_NODES = PROJECT_ROOT / "data" / "private" / "delaney-media-kgx-nodes.tsv"
DEFAULT_EDGES = PROJECT_ROOT / "data" / "private" / "delaney-media-kgx-edges.tsv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "private"


def read_tsv(file_path: Path) -> list[dict[str, str]]:
    """Read TSV file into list of dicts."""
    with file_path.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def write_tsv(file_path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    """Write list of dicts to TSV file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fix_category(category: str) -> str:
    """Fix category capitalization: Biolink: -> biolink:"""
    if category.startswith("Biolink:"):
        return "biolink:" + category[8:]
    return category


def validate_node(row: dict[str, str]) -> tuple[bool, list[str]]:
    """Validate a node row against KGXNode model.

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    try:
        # Fix category if needed
        category_str = row.get("category", "")
        fixed_category = fix_category(category_str)

        # Create KGXNode to validate
        KGXNode(
            id=row["id"],
            category=[fixed_category] if fixed_category else [],
            name=row.get("name"),
        )

        if category_str != fixed_category:
            errors.append(f"Category capitalization: '{category_str}' should be '{fixed_category}'")

        return (len(errors) == 0, errors)

    except ValidationError as e:
        for error in e.errors():
            field = ".".join(str(x) for x in error["loc"])
            errors.append(f"{field}: {error['msg']}")
        return (False, errors)
    except KeyError as e:
        errors.append(f"Missing required field: {e}")
        return (False, errors)


def validate_edge(row: dict[str, str]) -> tuple[bool, list[str]]:
    """Validate an edge row against KGXEdge model.

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    try:
        # Check required KGX fields
        KGXEdge(
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            knowledge_level=row.get("knowledge_level", "knowledge_assertion"),
            agent_type=row.get("agent_type", "manual_agent"),
        )

        # Check if required fields were missing
        if "knowledge_level" not in row or not row["knowledge_level"]:
            errors.append("Missing required field: knowledge_level")
        if "agent_type" not in row or not row["agent_type"]:
            errors.append("Missing required field: agent_type")

        return (len(errors) == 0, errors)

    except ValidationError as e:
        for error in e.errors():
            field = ".".join(str(x) for x in error["loc"])
            errors.append(f"{field}: {error['msg']}")
        return (False, errors)
    except KeyError as e:
        errors.append(f"Missing required field: {e}")
        return (False, errors)


def create_missing_nodes(edges: list[dict[str, str]], existing_nodes: set[str]) -> list[dict[str, str]]:
    """Create nodes for edge objects that don't have nodes yet.

    Args:
        edges: List of edge dictionaries
        existing_nodes: Set of existing node IDs

    Returns:
        List of new node dictionaries to add
    """
    new_nodes = []
    seen = set()

    for edge in edges:
        obj_id = edge["object"]

        # Skip if node already exists or we've already created it
        if obj_id in existing_nodes or obj_id in seen:
            continue

        seen.add(obj_id)

        # Determine category based on CURIE prefix
        if obj_id.startswith("CHEBI:"):
            category = "biolink:ChemicalEntity"
            name = f"Chemical {obj_id}"
        elif obj_id.startswith("pubchem.compound:"):
            category = "biolink:ChemicalEntity"
            name = f"PubChem Compound {obj_id.split(':')[1]}"
        elif obj_id.startswith("uuid:"):
            # Could be solution or medium - check if it's in edges as subject
            is_subject = any(e["subject"] == obj_id for e in edges)
            if is_subject:
                # It's used as a subject, likely a solution or medium
                category = "biolink:ChemicalMixture"
                name = f"Solution or Medium {obj_id.split(':')[1][:8]}"
            else:
                category = "biolink:ChemicalEntity"
                name = f"Component {obj_id.split(':')[1][:8]}"
        elif obj_id.startswith("doi:"):
            category = "biolink:ComplexMolecularMixture"
            name = f"Medium {obj_id}"
        else:
            logger.warning(f"Unknown CURIE prefix for {obj_id}, using ChemicalEntity")
            category = "biolink:ChemicalEntity"
            name = obj_id

        new_nodes.append(
            {
                "id": obj_id,
                "category": category,
                "name": name,
            }
        )

    return new_nodes


def fix_nodes(nodes: list[dict[str, str]]) -> list[dict[str, str]]:
    """Fix node issues (category capitalization)."""
    fixed = []
    for node in nodes:
        fixed_node = node.copy()
        if "category" in fixed_node:
            fixed_node["category"] = fix_category(fixed_node["category"])
        fixed.append(fixed_node)
    return fixed


def fix_edges(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    """Fix edge issues (add missing required fields)."""
    fixed = []
    for edge in edges:
        fixed_edge = edge.copy()

        # Add missing required fields with sensible defaults
        if "knowledge_level" not in fixed_edge or not fixed_edge["knowledge_level"]:
            fixed_edge["knowledge_level"] = "knowledge_assertion"

        if "agent_type" not in fixed_edge or not fixed_edge["agent_type"]:
            fixed_edge["agent_type"] = "manual_agent"

        fixed.append(fixed_edge)
    return fixed


@click.command()
@click.option(
    "--nodes-input",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_NODES,
    help="Input nodes TSV file",
)
@click.option(
    "--edges-input",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_EDGES,
    help="Input edges TSV file",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    help="Output directory for fixed files",
)
@click.option(
    "--validate-only",
    is_flag=True,
    help="Only validate, don't write fixed files",
)
def main(
    nodes_input: Path,
    edges_input: Path,
    output_dir: Path,
    validate_only: bool,
) -> None:
    """Validate and fix Delaney media KGX files."""
    logger.info("=" * 80)
    logger.info("Delaney Media KGX Validation and Fix")
    logger.info("=" * 80)

    # Read files
    logger.info(f"\nReading nodes from {nodes_input}")
    nodes = read_tsv(nodes_input)
    logger.info(f"  Found {len(nodes)} nodes")

    logger.info(f"\nReading edges from {edges_input}")
    edges = read_tsv(edges_input)
    logger.info(f"  Found {len(edges)} edges")

    # Validate nodes
    logger.info("\n" + "=" * 80)
    logger.info("VALIDATING NODES")
    logger.info("=" * 80)
    node_errors = 0
    for i, node in enumerate(nodes, 1):
        is_valid, errors = validate_node(node)
        if not is_valid:
            node_errors += 1
            logger.error(f"Node {i} ({node['id']}): INVALID")
            for error in errors:
                logger.error(f"  - {error}")

    if node_errors == 0:
        logger.info("✓ All nodes valid!")
    else:
        logger.warning(f"✗ {node_errors}/{len(nodes)} nodes have errors")

    # Validate edges
    logger.info("\n" + "=" * 80)
    logger.info("VALIDATING EDGES")
    logger.info("=" * 80)
    edge_errors = 0
    for i, edge in enumerate(edges, 1):
        is_valid, errors = validate_edge(edge)
        if not is_valid:
            edge_errors += 1
            if edge_errors <= 5:  # Only show first 5 to avoid spam
                logger.error(f"Edge {i} ({edge['subject']} -> {edge['object']}): INVALID")
                for error in errors:
                    logger.error(f"  - {error}")

    if edge_errors == 0:
        logger.info("✓ All edges valid!")
    else:
        logger.warning(f"✗ {edge_errors}/{len(edges)} edges have errors")
        if edge_errors > 5:
            logger.warning(f"  (showing first 5 errors, {edge_errors - 5} more...)")

    # Check for missing nodes
    logger.info("\n" + "=" * 80)
    logger.info("CHECKING FOR MISSING NODES")
    logger.info("=" * 80)
    existing_node_ids = {node["id"] for node in nodes}
    edge_object_ids = {edge["object"] for edge in edges}
    missing_node_ids = edge_object_ids - existing_node_ids

    if missing_node_ids:
        logger.warning(f"✗ Found {len(missing_node_ids)} edge objects without nodes:")
        for node_id in sorted(missing_node_ids)[:10]:
            logger.warning(f"  - {node_id}")
        if len(missing_node_ids) > 10:
            logger.warning(f"  (and {len(missing_node_ids) - 10} more...)")
    else:
        logger.info("✓ All edge objects have corresponding nodes")

    # Fix and write if not validate-only
    if not validate_only:
        logger.info("\n" + "=" * 80)
        logger.info("FIXING FILES")
        logger.info("=" * 80)

        # Fix nodes
        fixed_nodes = fix_nodes(nodes)
        logger.info(f"✓ Fixed {len(fixed_nodes)} nodes")

        # Create missing nodes
        if missing_node_ids:
            new_nodes = create_missing_nodes(edges, existing_node_ids)
            fixed_nodes.extend(new_nodes)
            logger.info(f"✓ Created {len(new_nodes)} missing nodes")

        # Fix edges
        fixed_edges = fix_edges(edges)
        logger.info(f"✓ Fixed {len(fixed_edges)} edges")

        # Write output
        output_dir.mkdir(parents=True, exist_ok=True)

        nodes_output = output_dir / "delaney-media-kgx-nodes-fixed.tsv"
        edges_output = output_dir / "delaney-media-kgx-edges-fixed.tsv"

        # Get fieldnames from original data
        nodes_fieldnames = list(nodes[0].keys()) if nodes else ["id", "category", "name"]
        edges_fieldnames = (
            list(edges[0].keys()) if edges else ["subject", "predicate", "object", "knowledge_level", "agent_type"]
        )

        # Add required fields if missing
        if "knowledge_level" not in edges_fieldnames:
            edges_fieldnames.insert(3, "knowledge_level")
        if "agent_type" not in edges_fieldnames:
            edges_fieldnames.insert(4, "agent_type")

        write_tsv(nodes_output, fixed_nodes, nodes_fieldnames)
        write_tsv(edges_output, fixed_edges, edges_fieldnames)

        logger.info(f"\n✓ Wrote fixed nodes to {nodes_output}")
        logger.info(f"✓ Wrote fixed edges to {edges_output}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    total_errors = node_errors + edge_errors + len(missing_node_ids)
    if total_errors == 0:
        logger.info("✓ All files are KGX/Biolink compliant!")
    else:
        logger.warning(f"Found {total_errors} total issues:")
        logger.warning(f"  - {node_errors} node validation errors")
        logger.warning(f"  - {edge_errors} edge validation errors")
        logger.warning(f"  - {len(missing_node_ids)} missing nodes")
        if not validate_only:
            logger.info("\n✓ Fixed files have been written to output directory")


if __name__ == "__main__":
    main()
