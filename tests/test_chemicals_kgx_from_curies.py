"""Tests for chemicals_kgx_from_curies script."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from cmm_ai_automation.scripts.chemicals_kgx_from_curies import (
    BIOLINK_CHEMICAL_ENTITY,
    BIOLINK_CHEMICAL_ROLE,
    ChemicalResult,
    parse_curie,
    read_chemicals_from_file,
    sample_entries,
    write_kgx_edges,
    write_kgx_nodes,
    write_role_nodes,
)


class TestParseCurie:
    """Tests for parse_curie function."""

    def test_parse_chebi_curie(self) -> None:
        """Test parsing CHEBI CURIE."""
        prefix, local_id = parse_curie("CHEBI:17790")
        assert prefix == "CHEBI"
        assert local_id == "17790"

    def test_parse_pubchem_curie(self) -> None:
        """Test parsing PUBCHEM.COMPOUND CURIE."""
        prefix, local_id = parse_curie("PUBCHEM.COMPOUND:16217523")
        assert prefix == "PUBCHEM.COMPOUND"
        assert local_id == "16217523"

    def test_parse_curie_with_whitespace(self) -> None:
        """Test parsing CURIE with surrounding whitespace."""
        prefix, local_id = parse_curie("  CHEBI:17790  ")
        assert prefix == "CHEBI"
        assert local_id == "17790"

    def test_parse_invalid_curie_no_colon(self) -> None:
        """Test that invalid CURIE without colon raises ValueError."""
        with pytest.raises(ValueError, match="no colon"):
            parse_curie("CHEBI17790")

    def test_parse_doi_curie(self) -> None:
        """Test parsing doi CURIE (non-chemical but valid format)."""
        prefix, local_id = parse_curie("doi:10.1371/journal.pone.0062957")
        assert prefix == "doi"
        assert local_id == "10.1371/journal.pone.0062957"


class TestChemicalResult:
    """Tests for ChemicalResult dataclass."""

    def test_create_basic_result(self) -> None:
        """Test creating a basic ChemicalResult."""
        result = ChemicalResult(
            input_curie="CHEBI:17790",
            canonical_id="CHEBI:17790",
            name="methanol",
            formula="CH4O",
            mass=32.042,
        )
        assert result.input_curie == "CHEBI:17790"
        assert result.canonical_id == "CHEBI:17790"
        assert result.name == "methanol"
        assert result.formula == "CH4O"
        assert result.mass == 32.042
        assert result.category == BIOLINK_CHEMICAL_ENTITY

    def test_to_kgx_node_basic(self) -> None:
        """Test converting ChemicalResult to KGX node."""
        result = ChemicalResult(
            input_curie="CHEBI:17790",
            canonical_id="CHEBI:17790",
            name="methanol",
            formula="CH4O",
            mass=32.042,
            inchikey="OKKJLVBELUTLKV-UHFFFAOYSA-N",
        )
        node = result.to_kgx_node()

        assert node["id"] == "CHEBI:17790"
        assert node["category"] == BIOLINK_CHEMICAL_ENTITY
        assert node["name"] == "methanol"
        assert node["formula"] == "CH4O"
        assert node["mass"] == "32.042"
        assert node["inchikey"] == "OKKJLVBELUTLKV-UHFFFAOYSA-N"

    def test_to_kgx_node_with_cas_numbers(self) -> None:
        """Test that CAS numbers are converted to xrefs."""
        result = ChemicalResult(
            input_curie="CHEBI:17790",
            canonical_id="CHEBI:17790",
            name="methanol",
            cas_numbers=["67-56-1"],
        )
        node = result.to_kgx_node()

        assert "casrn:67-56-1" in node["xref"]

    def test_to_kgx_node_with_synonyms(self) -> None:
        """Test that synonyms are pipe-delimited."""
        result = ChemicalResult(
            input_curie="CHEBI:17790",
            canonical_id="CHEBI:17790",
            name="methanol",
            synonyms=["MeOH", "wood alcohol", "carbinol"],
        )
        node = result.to_kgx_node()

        assert "MeOH" in node["synonym"]
        assert "wood alcohol" in node["synonym"]
        assert "|" in node["synonym"]

    def test_to_kgx_node_with_xrefs(self) -> None:
        """Test that xrefs are properly formatted."""
        result = ChemicalResult(
            input_curie="CHEBI:17790",
            canonical_id="CHEBI:17790",
            name="methanol",
            xrefs=["PUBCHEM.COMPOUND:887", "KEGG.COMPOUND:C00132"],
            cas_numbers=["67-56-1"],
        )
        node = result.to_kgx_node()

        # CAS should be added as xref
        assert "casrn:67-56-1" in node["xref"]
        assert "PUBCHEM.COMPOUND:887" in node["xref"]
        assert "KEGG.COMPOUND:C00132" in node["xref"]

    def test_to_kgx_node_empty_mass(self) -> None:
        """Test that None mass produces empty string."""
        result = ChemicalResult(
            input_curie="CHEBI:17790",
            canonical_id="CHEBI:17790",
            name="methanol",
            mass=None,
        )
        node = result.to_kgx_node()

        assert node["mass"] == ""

    def test_to_kgx_node_with_roles(self) -> None:
        """Test that roles are stored but not in node output."""
        result = ChemicalResult(
            input_curie="CHEBI:17790",
            canonical_id="CHEBI:17790",
            name="methanol",
            chebi_roles=[("CHEBI:33292", "fuel"), ("CHEBI:77746", "human metabolite")],
        )
        node = result.to_kgx_node()

        # Roles should not appear in node output (they go in edges and role nodes)
        assert "chebi_role" not in node


class TestSampleEntries:
    """Tests for sample_entries function."""

    def test_sample_n(self) -> None:
        """Test sampling N entries."""
        entries = [{"curie": f"CHEBI:{i}"} for i in range(100)]
        sampled = sample_entries(entries, sample_n=10)

        assert len(sampled) == 10
        # All sampled entries should be from original list
        for entry in sampled:
            assert entry in entries

    def test_sample_n_larger_than_list(self) -> None:
        """Test sampling more than available."""
        entries = [{"curie": f"CHEBI:{i}"} for i in range(5)]
        sampled = sample_entries(entries, sample_n=10)

        assert len(sampled) == 5

    def test_sample_fraction(self) -> None:
        """Test sampling by fraction."""
        entries = [{"curie": f"CHEBI:{i}"} for i in range(100)]
        sampled = sample_entries(entries, sample_fraction=0.1)

        assert len(sampled) == 10

    def test_sample_fraction_minimum_one(self) -> None:
        """Test that fraction sampling returns at least 1."""
        entries = [{"curie": f"CHEBI:{i}"} for i in range(100)]
        sampled = sample_entries(entries, sample_fraction=0.001)

        assert len(sampled) >= 1

    def test_no_sampling(self) -> None:
        """Test that no sampling returns original list."""
        entries = [{"curie": f"CHEBI:{i}"} for i in range(10)]
        sampled = sample_entries(entries)

        assert sampled == entries


class TestReadChemicalsFromFile:
    """Tests for read_chemicals_from_file function."""

    def test_read_tsv_file(self, tmp_path: Path) -> None:
        """Test reading TSV file."""
        test_file = tmp_path / "chemicals.tsv"
        test_file.write_text("id\tname\tcomments\nCHEBI:17790\tmethanol\ta fuel\nPUBCHEM.COMPOUND:887\tmethanol\t\n")

        entries = read_chemicals_from_file(test_file, "id")

        assert len(entries) == 2
        assert entries[0]["curie"] == "CHEBI:17790"
        assert entries[1]["curie"] == "PUBCHEM.COMPOUND:887"

    def test_read_with_name_field(self, tmp_path: Path) -> None:
        """Test reading with name field."""
        test_file = tmp_path / "chemicals.tsv"
        test_file.write_text("id\tchemical_name\nCHEBI:17790\tMethanol\n")

        entries = read_chemicals_from_file(test_file, "id", name_field="chemical_name")

        assert entries[0]["name"] == "Methanol"

    def test_read_with_comments_field(self, tmp_path: Path) -> None:
        """Test reading with comments field."""
        test_file = tmp_path / "chemicals.tsv"
        test_file.write_text("id\tnotes\nCHEBI:17790\tUsed as solvent\n")

        entries = read_chemicals_from_file(test_file, "id", comments_field="notes")

        assert entries[0]["comments"] == "Used as solvent"

    def test_read_skips_empty_ids(self, tmp_path: Path) -> None:
        """Test that empty IDs are skipped."""
        test_file = tmp_path / "chemicals.tsv"
        test_file.write_text("id\tname\nCHEBI:17790\tmethanol\n\tno_id\nCHEBI:31795\tmagnesium sulfate\n")

        entries = read_chemicals_from_file(test_file, "id")

        assert len(entries) == 2
        assert entries[0]["curie"] == "CHEBI:17790"
        assert entries[1]["curie"] == "CHEBI:31795"


class TestWriteKgxNodes:
    """Tests for write_kgx_nodes function."""

    def test_write_nodes_creates_file(self, tmp_path: Path) -> None:
        """Test that write_kgx_nodes creates a TSV file."""
        output_path = tmp_path / "chemicals_nodes.tsv"
        results = [
            ChemicalResult(
                input_curie="CHEBI:17790",
                canonical_id="CHEBI:17790",
                name="methanol",
                formula="CH4O",
                mass=32.042,
            )
        ]

        write_kgx_nodes(results, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "CHEBI:17790" in content
        assert "methanol" in content
        assert "CH4O" in content

    def test_write_nodes_has_header(self, tmp_path: Path) -> None:
        """Test that output has proper header."""
        output_path = tmp_path / "chemicals_nodes.tsv"
        results = [
            ChemicalResult(
                input_curie="CHEBI:17790",
                canonical_id="CHEBI:17790",
                name="methanol",
            )
        ]

        write_kgx_nodes(results, output_path)

        lines = output_path.read_text().strip().split("\n")
        header = lines[0]
        assert "id" in header
        assert "category" in header
        assert "name" in header
        assert "formula" in header


class TestWriteRoleNodes:
    """Tests for write_role_nodes function."""

    def test_write_role_nodes_appends(self, tmp_path: Path) -> None:
        """Test that role nodes are appended to existing file."""
        output_path = tmp_path / "chemicals_nodes.tsv"

        # First write chemical nodes
        results = [
            ChemicalResult(
                input_curie="CHEBI:17790",
                canonical_id="CHEBI:17790",
                name="methanol",
                chebi_roles=[("CHEBI:33292", "fuel")],
            )
        ]
        write_kgx_nodes(results, output_path)

        # Then append role nodes
        count = write_role_nodes(results, output_path)

        assert count == 1
        content = output_path.read_text()
        assert "CHEBI:33292" in content
        assert BIOLINK_CHEMICAL_ROLE in content
        assert "fuel" in content

    def test_write_role_nodes_deduplicates(self, tmp_path: Path) -> None:
        """Test that duplicate roles are not written twice."""
        output_path = tmp_path / "chemicals_nodes.tsv"

        results = [
            ChemicalResult(
                input_curie="CHEBI:17790",
                canonical_id="CHEBI:17790",
                name="methanol",
                chebi_roles=[("CHEBI:33292", "fuel")],
            ),
            ChemicalResult(
                input_curie="CHEBI:31795",
                canonical_id="CHEBI:31795",
                name="magnesium sulfate",
                chebi_roles=[("CHEBI:33292", "fuel")],  # Same role
            ),
        ]
        write_kgx_nodes(results, output_path)
        count = write_role_nodes(results, output_path)

        assert count == 1  # Only one role node despite two chemicals having it


class TestWriteKgxEdges:
    """Tests for write_kgx_edges function."""

    def test_write_edges_creates_file(self, tmp_path: Path) -> None:
        """Test that write_kgx_edges creates a TSV file."""
        output_path = tmp_path / "chemicals_edges.tsv"
        results = [
            ChemicalResult(
                input_curie="CHEBI:17790",
                canonical_id="CHEBI:17790",
                name="methanol",
                chebi_roles=[("CHEBI:33292", "fuel"), ("CHEBI:77746", "human metabolite")],
            )
        ]

        edge_count = write_kgx_edges(results, output_path)

        assert edge_count == 2
        assert output_path.exists()
        content = output_path.read_text()
        assert "CHEBI:17790" in content
        assert "biolink:has_role" in content
        assert "CHEBI:33292" in content
        assert "CHEBI:77746" in content

    def test_write_edges_has_provenance(self, tmp_path: Path) -> None:
        """Test that edges have proper provenance fields."""
        output_path = tmp_path / "chemicals_edges.tsv"
        results = [
            ChemicalResult(
                input_curie="CHEBI:17790",
                canonical_id="CHEBI:17790",
                name="methanol",
                chebi_roles=[("CHEBI:33292", "fuel")],
            )
        ]

        write_kgx_edges(results, output_path)

        content = output_path.read_text()
        assert "knowledge_assertion" in content
        assert "manual_agent" in content
        assert "infores:cmm-ai-automation" in content

    def test_write_edges_no_roles(self, tmp_path: Path) -> None:
        """Test that chemicals without roles produce no edges."""
        output_path = tmp_path / "chemicals_edges.tsv"
        results = [
            ChemicalResult(
                input_curie="CHEBI:17790",
                canonical_id="CHEBI:17790",
                name="methanol",
                chebi_roles=[],
            )
        ]

        edge_count = write_kgx_edges(results, output_path)

        assert edge_count == 0
