from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from cmm_ai_automation.scripts.standardize_kgx import standardize


def test_standardize_kgx(tmp_path: Path) -> None:
    """Test the standardize_kgx script."""
    # Create input files
    nodes_file = tmp_path / "nodes.tsv"
    edges_file = tmp_path / "edges.tsv"
    out_nodes_file = tmp_path / "nodes_out.tsv"
    out_edges_file = tmp_path / "edges_out.tsv"

    # Input data with issues to fix:
    # 1. Lowercase prefix: pubchem.compound:123
    # 2. Missing provenance columns
    nodes_data = [
        {"id": "pubchem.compound:123", "name": "Test Node", "category": "biolink:ChemicalEntity"},
        {"id": "NCBITaxon:9606", "name": "Human", "category": "biolink:OrganismTaxon"},
    ]
    edges_data = [
        {
            "id": "e1",
            "subject": "pubchem.compound:123",
            "predicate": "biolink:treats",
            "object": "NCBITaxon:9606",
            # Missing knowledge_level and agent_type
        }
    ]

    # Write input files
    pd.DataFrame(nodes_data).to_csv(nodes_file, sep="\t", index=False)
    pd.DataFrame(edges_data).to_csv(edges_file, sep="\t", index=False)

    runner = CliRunner()
    result = runner.invoke(
        standardize,
        [
            "--nodes",
            str(nodes_file),
            "--edges",
            str(edges_file),
            "--out-nodes",
            str(out_nodes_file),
            "--out-edges",
            str(out_edges_file),
        ],
    )

    assert result.exit_code == 0
    assert "Written standardized files" in result.output

    # Check outputs
    df_nodes = pd.read_csv(out_nodes_file, sep="\t", dtype=str)
    df_edges = pd.read_csv(out_edges_file, sep="\t", dtype=str)

    # Verify Prefix Fixes
    # "pubchem.compound:123" -> "PUBCHEM.COMPOUND:123"
    assert "PUBCHEM.COMPOUND:123" in df_nodes["id"].values
    assert "pubchem.compound:123" not in df_nodes["id"].values

    # "NCBITaxon:9606" should remain unchanged
    assert "NCBITaxon:9606" in df_nodes["id"].values

    # Verify Edge Subject/Object fixes
    assert df_edges.iloc[0]["subject"] == "PUBCHEM.COMPOUND:123"
    assert df_edges.iloc[0]["object"] == "NCBITaxon:9606"

    # Verify Provenance Columns
    assert "knowledge_level" in df_edges.columns
    assert df_edges.iloc[0]["knowledge_level"] == "knowledge_assertion"

    assert "agent_type" in df_edges.columns
    assert df_edges.iloc[0]["agent_type"] == "manual_agent"


def test_standardize_kgx_existing_provenance(tmp_path: Path) -> None:
    """Test that existing provenance data is preserved."""
    nodes_file = tmp_path / "nodes.tsv"
    edges_file = tmp_path / "edges.tsv"
    out_nodes_file = tmp_path / "nodes_out.tsv"
    out_edges_file = tmp_path / "edges_out.tsv"

    # Write input files
    pd.DataFrame([{"id": "A:1"}]).to_csv(nodes_file, sep="\t", index=False)

    edges_data = [
        {
            "subject": "A:1",
            "predicate": "biolink:related_to",
            "object": "A:1",
            "knowledge_level": "custom_level",
            "agent_type": "custom_agent",
        }
    ]
    pd.DataFrame(edges_data).to_csv(edges_file, sep="\t", index=False)

    runner = CliRunner()
    result = runner.invoke(
        standardize,
        [
            "--nodes",
            str(nodes_file),
            "--edges",
            str(edges_file),
            "--out-nodes",
            str(out_nodes_file),
            "--out-edges",
            str(out_edges_file),
        ],
    )

    assert result.exit_code == 0
    df_edges = pd.read_csv(out_edges_file, sep="\t", dtype=str)

    assert df_edges.iloc[0]["knowledge_level"] == "custom_level"
    assert df_edges.iloc[0]["agent_type"] == "custom_agent"
