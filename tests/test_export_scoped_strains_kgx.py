"""Tests for export_scoped_strains_kgx script."""

from pathlib import Path

import pytest

from cmm_ai_automation.scripts.export_scoped_strains_kgx import (
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

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

        assert node is not None
        assert node.id == "bacdive:7142"
        assert node.name == "Methylobacterium extorquens AM-1"  # binomial + " " + strain
        assert hasattr(node, "binomial_name")
        assert node.binomial_name == "Methylobacterium extorquens"
        assert hasattr(node, "strain_designation")
        assert node.strain_designation == "AM-1"  # No commas in this one
        assert "biolink:OrganismTaxon" in node.category

    def test_create_node_with_ncbi_only(self) -> None:
        """Test creating node with only NCBI ID."""
        strain_data = {
            "bacdive_id_mam": "",
            "ncbi_taxon_strain_mam": "408",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

        assert node is not None
        assert node.id == "NCBITaxon:408"
        assert node.name == "Methylobacterium extorquens AM-1"
        assert hasattr(node, "binomial_name")
        assert node.binomial_name == "Methylobacterium extorquens"

    def test_create_node_with_both_ids(self) -> None:
        """Test creating node with both BacDive and NCBI IDs."""
        strain_data = {
            "bacdive_id_mam": "7142",
            "ncbi_taxon_strain_mam": "408",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

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

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

        assert node is None

    def test_node_repacks_strain_designation_with_pipes(self) -> None:
        """Test that strain designation with commas is repacked with pipes."""
        strain_data = {
            "bacdive_id_mam": "7143",
            "ncbi_taxon_strain_mam": "",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "0355, D355, AM1",
        }

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

        assert node is not None
        assert node.id == "bacdive:7143"
        assert node.name == "Methylobacterium extorquens 0355, D355, AM1"  # Name uses original
        assert hasattr(node, "strain_designation")
        assert node.strain_designation == "0355|D355|AM1"  # Repacked with pipes

    def test_node_uses_scientific_name_if_no_designation(self) -> None:
        """Test that scientific name is used when no strain designation."""
        strain_data = {
            "bacdive_id_mam": "7142",
            "ncbi_taxon_strain_mam": "",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "",
        }

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

        assert node is not None
        assert node.name == "Methylobacterium extorquens"
        assert hasattr(node, "binomial_name")
        assert node.binomial_name == "Methylobacterium extorquens"

    def test_node_adds_scientific_name_as_synonym(self) -> None:
        """Test that scientific name becomes synonym when different from name."""
        strain_data = {
            "bacdive_id_mam": "7142",
            "ncbi_taxon_strain_mam": "",
            "scientific_name_sub_or_mpj": "Methylobacterium extorquens",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

        assert node is not None
        # Scientific name is now in binomial_name field, NOT in synonyms
        assert hasattr(node, "binomial_name")
        assert node.binomial_name == "Methylobacterium extorquens"
        # Synonyms should only contain actual synonyms, not the scientific name
        if node.synonym:
            assert "Methylobacterium extorquens" not in node.synonym

    def test_node_no_synonym_if_same_as_name(self) -> None:
        """Test that synonym not added if same as name."""
        strain_data = {
            "bacdive_id_mam": "7142",
            "ncbi_taxon_strain_mam": "",
            "scientific_name_sub_or_mpj": "AM-1",
            "strain_designation_sub_or_mpj": "AM-1",
        }

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

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

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

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

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

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

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

        assert node is not None
        assert node.id == "bacdive:7142"
        assert node.xref is not None and "NCBITaxon:408" in node.xref

    @pytest.mark.integration
    def test_ncbi_enrichment_adds_synonyms_and_xrefs(self) -> None:
        """Test that NCBI enrichment adds synonyms and xrefs (requires network)."""
        # Test with S. meliloti 2011 (NCBITaxon:1286640)
        strain_data = {
            "bacdive_id_mam": "",
            "ncbi_taxon_strain_mam": "1286640",
            "species_taxon_id_sub_or_mpj": "382",  # S. meliloti species
            "scientific_name_sub_or_mpj": "Sinorhizobium meliloti",
            "strain_designation_sub_or_mpj": "2011",
        }

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=True)

        assert node is not None
        assert node.id == "NCBITaxon:1286640"
        assert node.name == "Sinorhizobium meliloti 2011"

        # Check binomial name is separate
        assert hasattr(node, "binomial_name")
        assert node.binomial_name == "Sinorhizobium meliloti"

        # Check that NCBI enrichment added xrefs from linkouts
        assert node.xref is not None
        assert len(node.xref) > 0

        # Species taxon ID should be returned (from input)
        assert species_taxon_id == "382"

    @pytest.mark.integration
    def test_ncbi_enrichment_extracts_species_taxon_id(self) -> None:
        """Test that NCBI enrichment extracts species taxon ID when missing (requires network)."""
        # Test with S. meliloti 2011 but WITHOUT species_taxon_id in input
        strain_data = {
            "bacdive_id_mam": "",
            "ncbi_taxon_strain_mam": "1286640",
            "species_taxon_id_sub_or_mpj": "",  # Empty - should be filled from NCBI
            "scientific_name_sub_or_mpj": "Sinorhizobium meliloti",
            "strain_designation_sub_or_mpj": "2011",
        }

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=True)

        assert node is not None
        assert node.id == "NCBITaxon:1286640"

        # Species taxon ID should be extracted from NCBI
        # S. meliloti 2011 (strain) should have species NCBITaxon:382
        assert species_taxon_id is not None
        assert species_taxon_id == "382"

    def test_ncbi_enrichment_skipped_when_disabled(self) -> None:
        """Test that NCBI enrichment is skipped when enrich_ncbi=False."""
        strain_data = {
            "bacdive_id_mam": "",
            "ncbi_taxon_strain_mam": "1286640",
            "species_taxon_id_sub_or_mpj": "382",
            "scientific_name_sub_or_mpj": "Sinorhizobium meliloti",
            "strain_designation_sub_or_mpj": "2011",
        }

        node, species_taxon_id = create_strain_node(strain_data, bacdive_collection=None, enrich_ncbi=False)

        assert node is not None
        assert node.id == "NCBITaxon:1286640"
        assert node.name == "Sinorhizobium meliloti 2011"
        # Scientific name should be in binomial_name field
        assert hasattr(node, "binomial_name")
        assert node.binomial_name == "Sinorhizobium meliloti"
        # Without NCBI enrichment, synonyms should be empty or None
        assert node.synonym is None or len(node.synonym) == 0
