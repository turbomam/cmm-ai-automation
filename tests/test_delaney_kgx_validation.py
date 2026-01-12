"""Tests for Delaney media KGX validation and compliance."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from pydantic import ValidationError

from cmm_ai_automation.transform.kgx import KGXEdge, KGXNode

# Path to delaney files
DATA_DIR = Path(__file__).parent.parent / "data" / "private"
NODES_FILE = DATA_DIR / "delaney-media-kgx-nodes-fixed.tsv"
EDGES_FILE = DATA_DIR / "delaney-media-kgx-edges-fixed.tsv"


def read_tsv(file_path: Path) -> list[dict[str, str]]:
    """Read TSV file into list of dicts."""
    with file_path.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


@pytest.mark.integration
class TestDelaneyNodesCompliance:
    """Test that Delaney media nodes are KGX/Biolink compliant."""

    @pytest.fixture
    def nodes(self) -> list[dict[str, str]]:
        """Load nodes from TSV file."""
        if not NODES_FILE.exists():
            pytest.skip(f"Fixed nodes file not found: {NODES_FILE}")
        return read_tsv(NODES_FILE)

    def test_nodes_file_exists(self) -> None:
        """Test that fixed nodes file exists."""
        if not NODES_FILE.exists():
            pytest.skip("Run validate_fix_delaney_kgx.py first to generate fixed files")

    def test_all_nodes_have_required_fields(self, nodes: list[dict[str, str]]) -> None:
        """Test that all nodes have id and category."""
        for node in nodes:
            assert "id" in node, f"Node missing id: {node}"
            assert "category" in node, f"Node {node['id']} missing category"
            assert node["id"], f"Node has empty id"
            assert node["category"], f"Node {node['id']} has empty category"

    def test_all_nodes_validate_against_kgx_model(self, nodes: list[dict[str, str]]) -> None:
        """Test that all nodes pass KGXNode validation."""
        errors = []
        for node in nodes:
            try:
                KGXNode(
                    id=node["id"],
                    category=[node["category"]],
                    name=node.get("name"),
                )
            except ValidationError as e:
                errors.append((node["id"], str(e)))

        if errors:
            error_msg = "\n".join(f"  {node_id}: {err}" for node_id, err in errors[:5])
            pytest.fail(f"{len(errors)} nodes failed validation:\n{error_msg}")

    def test_categories_use_lowercase_biolink_prefix(self, nodes: list[dict[str, str]]) -> None:
        """Test that all categories use lowercase 'biolink:' prefix."""
        invalid = []
        for node in nodes:
            category = node.get("category", "")
            if category.startswith("Biolink:"):
                invalid.append((node["id"], category))

        if invalid:
            pytest.fail(
                f"{len(invalid)} nodes have incorrect capitalization:\n" +
                "\n".join(f"  {node_id}: {cat}" for node_id, cat in invalid[:5])
            )

    def test_chemical_entities_have_chebi_or_pubchem_ids(self, nodes: list[dict[str, str]]) -> None:
        """Test that ChemicalEntity nodes have appropriate CURIEs."""
        invalid = []
        for node in nodes:
            if "ChemicalEntity" in node.get("category", ""):
                node_id = node["id"]
                if not (node_id.startswith("CHEBI:") or node_id.startswith("pubchem.compound:")):
                    invalid.append(node_id)

        if invalid:
            pytest.fail(
                f"{len(invalid)} ChemicalEntity nodes have non-CHEBI/PubChem IDs:\n" +
                "\n".join(f"  {node_id}" for node_id in invalid[:10])
            )

    def test_mixtures_have_appropriate_identifiers(self, nodes: list[dict[str, str]]) -> None:
        """Test that mixture nodes use DOI or UUID identifiers."""
        invalid = []
        for node in nodes:
            category = node.get("category", "")
            if "Mixture" in category or "mixture" in category.lower():
                node_id = node["id"]
                if not (node_id.startswith("doi:") or node_id.startswith("uuid:")):
                    invalid.append((node_id, category))

        if invalid:
            pytest.fail(
                f"{len(invalid)} mixture nodes have invalid identifiers:\n" +
                "\n".join(f"  {node_id} ({cat})" for node_id, cat in invalid[:10])
            )


@pytest.mark.integration
class TestDelaneyEdgesCompliance:
    """Test that Delaney media edges are KGX/Biolink compliant."""

    @pytest.fixture
    def edges(self) -> list[dict[str, str]]:
        """Load edges from TSV file."""
        if not EDGES_FILE.exists():
            pytest.skip(f"Fixed edges file not found: {EDGES_FILE}")
        return read_tsv(EDGES_FILE)

    @pytest.fixture
    def nodes(self) -> list[dict[str, str]]:
        """Load nodes from TSV file."""
        if not NODES_FILE.exists():
            pytest.skip(f"Fixed nodes file not found: {NODES_FILE}")
        return read_tsv(NODES_FILE)

    def test_edges_file_exists(self) -> None:
        """Test that fixed edges file exists."""
        if not EDGES_FILE.exists():
            pytest.skip("Run validate_fix_delaney_kgx.py first to generate fixed files")

    def test_all_edges_have_required_fields(self, edges: list[dict[str, str]]) -> None:
        """Test that all edges have required KGX fields."""
        required_fields = ["subject", "predicate", "object", "knowledge_level", "agent_type"]

        for edge in edges:
            for field in required_fields:
                assert field in edge, f"Edge missing {field}: {edge.get('subject', '?')} -> {edge.get('object', '?')}"
                assert edge[field], f"Edge has empty {field}: {edge.get('subject', '?')} -> {edge.get('object', '?')}"

    def test_all_edges_validate_against_kgx_model(self, edges: list[dict[str, str]]) -> None:
        """Test that all edges pass KGXEdge validation."""
        errors = []
        for edge in edges:
            try:
                KGXEdge(
                    subject=edge["subject"],
                    predicate=edge["predicate"],
                    object=edge["object"],
                    knowledge_level=edge["knowledge_level"],
                    agent_type=edge["agent_type"],
                )
            except ValidationError as e:
                errors.append((f"{edge['subject']} -> {edge['object']}", str(e)))

        if errors:
            error_msg = "\n".join(f"  {edge}: {err}" for edge, err in errors[:5])
            pytest.fail(f"{len(errors)} edges failed validation:\n{error_msg}")

    def test_all_edge_objects_have_nodes(self, edges: list[dict[str, str]], nodes: list[dict[str, str]]) -> None:
        """Test that all edge objects have corresponding nodes."""
        node_ids = {node["id"] for node in nodes}
        missing = set()

        for edge in edges:
            if edge["object"] not in node_ids:
                missing.add(edge["object"])

        if missing:
            pytest.fail(
                f"{len(missing)} edge objects don't have nodes:\n" +
                "\n".join(f"  {obj_id}" for obj_id in sorted(missing)[:10])
            )

    def test_predicates_use_biolink_namespace(self, edges: list[dict[str, str]]) -> None:
        """Test that all predicates use biolink: prefix."""
        invalid = []
        for edge in edges:
            predicate = edge.get("predicate", "")
            if not predicate.startswith("biolink:"):
                invalid.append((
                    f"{edge['subject']} -> {edge['object']}",
                    predicate
                ))

        if invalid:
            pytest.fail(
                f"{len(invalid)} edges have invalid predicates:\n" +
                "\n".join(f"  {edge}: '{pred}'" for edge, pred in invalid[:10])
            )

    def test_has_part_relationships_are_used(self, edges: list[dict[str, str]]) -> None:
        """Test that has_part is the dominant relationship (as expected)."""
        predicates = [edge["predicate"] for edge in edges]
        has_part_count = predicates.count("biolink:has_part")

        # Should be mostly has_part relationships
        assert has_part_count > 0, "No has_part relationships found"
        assert has_part_count / len(predicates) > 0.8, "Expected > 80% has_part relationships"

    def test_knowledge_level_values_are_valid(self, edges: list[dict[str, str]]) -> None:
        """Test that knowledge_level values are from allowed set."""
        valid_levels = {
            "knowledge_assertion",
            "logical_entailment",
            "prediction",
            "statistical_association",
            "observation",
            "not_provided",
        }

        invalid = []
        for edge in edges:
            level = edge.get("knowledge_level", "")
            if level not in valid_levels:
                invalid.append((
                    f"{edge['subject']} -> {edge['object']}",
                    level
                ))

        if invalid:
            pytest.fail(
                f"{len(invalid)} edges have invalid knowledge_level:\n" +
                "\n".join(f"  {edge}: '{level}'" for edge, level in invalid[:10])
            )

    def test_agent_type_values_are_valid(self, edges: list[dict[str, str]]) -> None:
        """Test that agent_type values are from allowed set."""
        valid_types = {
            "manual_agent",
            "automated_agent",
            "data_analysis_pipeline",
            "computational_model",
            "text_mining_agent",
            "image_processing_agent",
            "manual_validation_of_automated_agent",
            "not_provided",
        }

        invalid = []
        for edge in edges:
            agent = edge.get("agent_type", "")
            if agent not in valid_types:
                invalid.append((
                    f"{edge['subject']} -> {edge['object']}",
                    agent
                ))

        if invalid:
            pytest.fail(
                f"{len(invalid)} edges have invalid agent_type:\n" +
                "\n".join(f"  {edge}: '{agent}'" for edge, agent in invalid[:10])
            )
