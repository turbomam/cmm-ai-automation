"""Tests for export_enriched_strains_kgx script."""

from pathlib import Path

from cmm_ai_automation.scripts.export_enriched_strains_kgx import (
    create_strain_node,
    read_enriched_strains,
)


class TestReadEnrichedStrains:
    """Tests for read_enriched_strains function."""

    def test_reads_enriched_file(self, tmp_path: Path) -> None:
        """Test reading enriched strains file."""
        # Create test file
        test_file = tmp_path / "test_strains.tsv"
        with test_file.open("w") as f:
            f.write("bacdive_id_mam\tncbi_taxon_strain_mam\tscientific_name_sub_or_mpj\n")
            f.write("7142\t\tmethylobacterium extorquens\n")
            f.write("\t408\tmethobacterium extorquens AM1\n")

        strains = read_enriched_strains(test_file)

        assert len(strains) == 2
        assert strains[0]["bacdive_id_mam"] == "7142"
        assert strains[1]["ncbi_taxon_strain_mam"] == "408"


class TestCreateStrainNode:
    """Tests for create_strain_node function."""

    def test_create_node_with_bacdive_id(self) -> None:
        """Test creating node with BacDive ID."""
        strain_data = {
            "bacdive_id_mam": "7142",
            "ncbi_taxon_strain_mam": "",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data)

        assert node is not None
        assert node.id == "bacdive:7142"
        assert node.name == "AM-1"
        assert "biolink:OrganismTaxon" in node.category

    def test_create_node_with_ncbi_only(self) -> None:
        """Test creating node with only NCBI ID."""
        strain_data = {
            "bacdive_id_mam": "",
            "ncbi_taxon_strain_mam": "408",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data)

        assert node is not None
        assert node.id == "NCBITaxon:408"
        assert node.name == "AM-1"

    def test_create_node_with_both_ids(self) -> None:
        """Test creating node with both BacDive and NCBI IDs."""
        strain_data = {
            "bacdive_id_mam": "7142",
            "ncbi_taxon_strain_mam": "408",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data)

        assert node is not None
        assert node.id == "bacdive:7142"  # BacDive is primary
        assert node.xref is not None
        assert "NCBITaxon:408" in node.xref

    def test_create_node_no_ids_returns_none(self) -> None:
        """Test that node creation returns None without IDs."""
        strain_data = {
            "bacdive_id_mam": "",
            "ncbi_taxon_strain_mam": "",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data)

        assert node is None

    def test_node_uses_scientific_name_if_no_designation(self) -> None:
        """Test that scientific name is used when no strain designation."""
        strain_data = {
            "bacdive_id_mam": "7142",
            "ncbi_taxon_strain_mam": "",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "",
        }

        node, species_taxon_id = create_strain_node(strain_data)

        assert node is not None
        assert node.name == "Methylobacterium extorquens"

    def test_node_adds_scientific_name_as_synonym(self) -> None:
        """Test that scientific name becomes synonym when different from name."""
        strain_data = {
            "bacdive_id_mam": "7142",
            "ncbi_taxon_strain_mam": "",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data)

        assert node is not None
        assert node.synonym is not None
        assert "Methylobacterium extorquens" in node.synonym

    def test_node_no_synonym_if_same_as_name(self) -> None:
        """Test that synonym not added if same as name."""
        strain_data = {
            "bacdive_id_mam": "7142",
            "ncbi_taxon_strain_mam": "",
            "scientific_name_sub_or_mpj": "AM-1",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data)

        assert node is not None
        assert node.synonym is None or len(node.synonym) == 0

    def test_node_fallback_name_for_bacdive(self) -> None:
        """Test fallback name generation for BacDive."""
        strain_data = {
            "bacdive_id_mam": "7142",
            "ncbi_taxon_strain_mam": "",
            "scientific_name_sub_or_mpj": "",
            "strain_designation_sub_or_mpj": "",
        }

        node, species_taxon_id = create_strain_node(strain_data)

        assert node is not None
        assert node.name == "BacDive strain 7142"

    def test_node_fallback_name_for_ncbi(self) -> None:
        """Test fallback name generation for NCBI."""
        strain_data = {
            "bacdive_id_mam": "",
            "ncbi_taxon_strain_mam": "408",
            "scientific_name_sub_or_mpj": "",
            "strain_designation_sub_or_mpj": "",
        }

        node, species_taxon_id = create_strain_node(strain_data)

        assert node is not None
        assert node.name == "NCBITaxon 408"

    def test_handles_whitespace_in_ids(self) -> None:
        """Test that whitespace in IDs is stripped."""
        strain_data = {
            "bacdive_id_mam": "  7142  ",
            "ncbi_taxon_strain_mam": "  408  ",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data)

        assert node is not None
        assert node.id == "bacdive:7142"
        assert node.xref is not None and "NCBITaxon:408" in node.xref
