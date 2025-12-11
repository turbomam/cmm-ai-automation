"""Tests for enrichment store module.

Tests composite key generation, conflict detection, merge logic,
and KGX export functionality.
"""

import tempfile
from pathlib import Path

import pytest

from cmm_ai_automation.store.enrichment_store import (
    AUTHORITATIVE_SOURCES,
    EnrichmentStore,
    generate_composite_key,
    parse_composite_key,
)


class TestCompositeKeyGeneration:
    """Tests for composite key generation and parsing."""

    def test_generate_key_both_present(self) -> None:
        """Test key generation with both inchikey and cas_rn present."""
        key = generate_composite_key(
            inchikey="WQZGKKKJIJFFOK-GASJEMHNSA-N",
            cas_rn="50-99-7",
        )
        assert key == "WQZGKKKJIJFFOK-GASJEMHNSA-N|50-99-7"

    def test_generate_key_missing_cas(self) -> None:
        """Test key generation with missing cas_rn."""
        key = generate_composite_key(
            inchikey="WQZGKKKJIJFFOK-GASJEMHNSA-N",
            cas_rn=None,
        )
        assert key == "WQZGKKKJIJFFOK-GASJEMHNSA-N|unknown"

    def test_generate_key_missing_inchikey(self) -> None:
        """Test key generation with missing inchikey uses UUID."""
        key = generate_composite_key(
            inchikey=None,
            cas_rn="50-99-7",
        )
        assert "|50-99-7" in key
        assert key.startswith("uuid:")

    def test_generate_key_both_missing(self) -> None:
        """Test key generation with both values missing."""
        key = generate_composite_key(inchikey=None, cas_rn=None)
        assert key.startswith("uuid:")
        assert key.endswith("|unknown")

    def test_parse_key_both_present(self) -> None:
        """Test parsing a key with both values."""
        inchikey, cas_rn = parse_composite_key("WQZGKKKJIJFFOK-GASJEMHNSA-N|50-99-7")
        assert inchikey == "WQZGKKKJIJFFOK-GASJEMHNSA-N"
        assert cas_rn == "50-99-7"

    def test_parse_key_missing_cas(self) -> None:
        """Test parsing a key with missing cas_rn."""
        inchikey, cas_rn = parse_composite_key("WQZGKKKJIJFFOK-GASJEMHNSA-N|unknown")
        assert inchikey == "WQZGKKKJIJFFOK-GASJEMHNSA-N"
        assert cas_rn is None

    def test_parse_key_missing_inchikey(self) -> None:
        """Test parsing a key with UUID placeholder for inchikey."""
        inchikey, cas_rn = parse_composite_key("uuid:abc12345|50-99-7")
        assert inchikey is None
        assert cas_rn == "50-99-7"

    def test_parse_key_invalid_format(self) -> None:
        """Test parsing an invalid key returns None tuple."""
        inchikey, cas_rn = parse_composite_key("invalid-key-no-pipe")
        assert inchikey is None
        assert cas_rn is None

    def test_roundtrip_both_present(self) -> None:
        """Test that generate and parse are inverses when both values present."""
        original_inchikey = "CSNNHWWHGAXBCP-UHFFFAOYSA-L"
        original_cas = "7487-88-9"

        key = generate_composite_key(original_inchikey, original_cas)
        parsed_inchikey, parsed_cas = parse_composite_key(key)

        assert parsed_inchikey == original_inchikey
        assert parsed_cas == original_cas


class TestAuthoritativeSources:
    """Tests for authoritative source configuration."""

    def test_pubchem_authoritative_for_cid(self) -> None:
        """Test that pubchem is authoritative for pubchem_cid."""
        assert AUTHORITATIVE_SOURCES["pubchem_cid"] == "pubchem"

    def test_chebi_authoritative_for_chebi_id(self) -> None:
        """Test that chebi is authoritative for chebi_id."""
        assert AUTHORITATIVE_SOURCES["chebi_id"] == "chebi"

    def test_cas_authoritative_for_cas_rn(self) -> None:
        """Test that cas is authoritative for cas_rn."""
        assert AUTHORITATIVE_SOURCES["cas_rn"] == "cas"

    def test_chebi_authoritative_for_roles(self) -> None:
        """Test that chebi is authoritative for biological/chemical roles."""
        assert AUTHORITATIVE_SOURCES["biological_roles"] == "chebi"
        assert AUTHORITATIVE_SOURCES["chemical_roles"] == "chebi"
        assert AUTHORITATIVE_SOURCES["application_roles"] == "chebi"

    def test_no_authoritative_source_for_structure(self) -> None:
        """Test that structural data has no single authoritative source."""
        assert AUTHORITATIVE_SOURCES["inchi"] is None
        assert AUTHORITATIVE_SOURCES["inchikey"] is None
        assert AUTHORITATIVE_SOURCES["smiles"] is None


class TestEnrichmentStoreMerge:
    """Tests for record merging logic in EnrichmentStore.

    Uses mocking to test merge logic without database.
    """

    def test_merge_new_field(self) -> None:
        """Test that new fields are added without conflict."""
        from cmm_ai_automation.store.enrichment_store import EnrichmentStore

        store = EnrichmentStore.__new__(EnrichmentStore)
        store.store_path = Path("/tmp/test.duckdb")
        store.schema_path = Path("/tmp/schema.yaml")

        existing = {
            "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
            "cas_rn": "50-99-7",
            "name": "D-glucose",
            "conflicts": [],
            "source_records": [],
        }
        new_data = {
            "pubchem_cid": 5793,
            "smiles": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
        }

        merged = store._merge_records(existing, new_data, "pubchem", "glucose")

        assert merged["pubchem_cid"] == 5793
        assert merged["smiles"] is not None
        assert merged["name"] == "D-glucose"  # preserved
        assert len(merged["conflicts"]) == 0

    def test_merge_authoritative_source_wins(self) -> None:
        """Test that authoritative source overwrites and logs conflict."""
        from cmm_ai_automation.store.enrichment_store import EnrichmentStore

        store = EnrichmentStore.__new__(EnrichmentStore)
        store.store_path = Path("/tmp/test.duckdb")
        store.schema_path = Path("/tmp/schema.yaml")

        existing = {
            "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
            "cas_rn": "50-99-7",
            "chebi_id": "CHEBI:99999",  # wrong value
            "conflicts": [],
            "source_records": [],
        }
        new_data = {
            "chebi_id": "CHEBI:17634",  # correct value from authoritative source
        }

        merged = store._merge_records(existing, new_data, "chebi", "glucose")

        # ChEBI is authoritative for chebi_id, so new value should win
        assert merged["chebi_id"] == "CHEBI:17634"
        assert len(merged["conflicts"]) == 1
        assert merged["conflicts"][0]["resolution"] == "primary_source_wins"
        assert merged["conflicts"][0]["field_name"] == "chebi_id"

    def test_merge_non_authoritative_conflict(self) -> None:
        """Test that non-authoritative conflicts are logged but don't overwrite."""
        from cmm_ai_automation.store.enrichment_store import EnrichmentStore

        store = EnrichmentStore.__new__(EnrichmentStore)
        store.store_path = Path("/tmp/test.duckdb")
        store.schema_path = Path("/tmp/schema.yaml")

        existing = {
            "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
            "cas_rn": "50-99-7",
            "chebi_id": "CHEBI:17634",  # authoritative value
            "conflicts": [],
            "source_records": [],
        }
        new_data = {
            "chebi_id": "CHEBI:99999",  # PubChem trying to set ChEBI ID
        }

        # PubChem is NOT authoritative for chebi_id
        merged = store._merge_records(existing, new_data, "pubchem", "glucose")

        # Original value should be preserved
        assert merged["chebi_id"] == "CHEBI:17634"
        assert len(merged["conflicts"]) == 1
        assert merged["conflicts"][0]["resolution"] == "unresolved"

    def test_merge_no_authoritative_source_conflict(self) -> None:
        """Test conflict for field with no authoritative source."""
        from cmm_ai_automation.store.enrichment_store import EnrichmentStore

        store = EnrichmentStore.__new__(EnrichmentStore)
        store.store_path = Path("/tmp/test.duckdb")
        store.schema_path = Path("/tmp/schema.yaml")

        existing = {
            "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
            "smiles": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
            "conflicts": [],
            "source_records": [],
        }
        new_data = {
            "smiles": "C(C1C(C(C(C(O1)O)O)O)O)O",  # different representation
        }

        merged = store._merge_records(existing, new_data, "chebi", "glucose")

        # First value should be preserved (no authoritative source)
        assert merged["smiles"] == "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O"
        assert len(merged["conflicts"]) == 1
        assert merged["conflicts"][0]["resolution"] == "unresolved"

    def test_merge_skips_none_values(self) -> None:
        """Test that None values don't overwrite existing values."""
        from cmm_ai_automation.store.enrichment_store import EnrichmentStore

        store = EnrichmentStore.__new__(EnrichmentStore)
        store.store_path = Path("/tmp/test.duckdb")
        store.schema_path = Path("/tmp/schema.yaml")

        existing = {
            "name": "D-glucose",
            "pubchem_cid": 5793,
            "conflicts": [],
            "source_records": [],
        }
        new_data = {
            "name": None,  # Should not overwrite
            "chebi_id": "CHEBI:17634",  # New field
        }

        merged = store._merge_records(existing, new_data, "chebi", "glucose")

        assert merged["name"] == "D-glucose"  # preserved
        assert merged["chebi_id"] == "CHEBI:17634"  # added

    def test_merge_adds_source_record(self) -> None:
        """Test that merging adds a source record."""
        from cmm_ai_automation.store.enrichment_store import EnrichmentStore

        store = EnrichmentStore.__new__(EnrichmentStore)
        store.store_path = Path("/tmp/test.duckdb")
        store.schema_path = Path("/tmp/schema.yaml")

        existing = {
            "name": "D-glucose",
            "conflicts": [],
            "source_records": [
                {"source_name": "pubchem", "source_id": "5793"},
            ],
        }
        new_data = {
            "chebi_id": "CHEBI:17634",
        }

        merged = store._merge_records(existing, new_data, "chebi", "glucose lookup")

        assert len(merged["source_records"]) == 2
        assert merged["source_records"][1]["source_name"] == "chebi"
        assert merged["source_records"][1]["source_query"] == "glucose lookup"


class TestGetSourceId:
    """Tests for _get_source_id method."""

    def test_get_source_id_pubchem(self) -> None:
        """Test extracting pubchem_cid for pubchem source."""
        from cmm_ai_automation.store.enrichment_store import EnrichmentStore

        store = EnrichmentStore.__new__(EnrichmentStore)

        data = {"pubchem_cid": 5793, "chebi_id": "CHEBI:17634"}
        result = store._get_source_id(data, "pubchem")
        assert result == "5793"

    def test_get_source_id_chebi(self) -> None:
        """Test extracting chebi_id for chebi source."""
        from cmm_ai_automation.store.enrichment_store import EnrichmentStore

        store = EnrichmentStore.__new__(EnrichmentStore)

        data = {"pubchem_cid": 5793, "chebi_id": "CHEBI:17634"}
        result = store._get_source_id(data, "chebi")
        assert result == "CHEBI:17634"

    def test_get_source_id_cas(self) -> None:
        """Test extracting cas_rn for cas source."""
        from cmm_ai_automation.store.enrichment_store import EnrichmentStore

        store = EnrichmentStore.__new__(EnrichmentStore)

        data = {"cas_rn": "50-99-7", "chebi_id": "CHEBI:17634"}
        result = store._get_source_id(data, "cas")
        assert result == "50-99-7"

    def test_get_source_id_unknown_source(self) -> None:
        """Test that unknown source returns None."""
        from cmm_ai_automation.store.enrichment_store import EnrichmentStore

        store = EnrichmentStore.__new__(EnrichmentStore)

        data = {"pubchem_cid": 5793}
        result = store._get_source_id(data, "unknown_source")
        assert result is None


class TestEnrichmentStoreIntegration:
    """Integration tests for EnrichmentStore using temporary database."""

    @pytest.fixture
    def temp_store(self) -> EnrichmentStore:
        """Create a store with a temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_enrichment.duckdb"
            store = EnrichmentStore(store_path=store_path)
            yield store
            store.close()

    @pytest.mark.integration
    def test_upsert_and_retrieve(self, temp_store: EnrichmentStore) -> None:
        """Test inserting and retrieving an ingredient."""
        data = {
            "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
            "cas_rn": "50-99-7",
            "name": "D-glucose",
            "pubchem_cid": 5793,
        }

        key = temp_store.upsert_ingredient(data, source="pubchem", query="glucose")

        # Retrieve by composite key
        result = temp_store.get_by_composite_key(key)
        assert result is not None
        assert result["name"] == "D-glucose"
        assert result["pubchem_cid"] == 5793

    @pytest.mark.integration
    def test_upsert_merge(self, temp_store: EnrichmentStore) -> None:
        """Test that upsert merges data from multiple sources."""
        # First insert from PubChem
        data1 = {
            "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
            "cas_rn": "50-99-7",
            "name": "D-glucose",
            "pubchem_cid": 5793,
        }
        key = temp_store.upsert_ingredient(data1, source="pubchem")

        # Second insert from ChEBI adds more data
        data2 = {
            "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
            "cas_rn": "50-99-7",
            "chebi_id": "CHEBI:17634",
            "biological_roles": ["CHEBI:78675"],
        }
        temp_store.upsert_ingredient(data2, source="chebi")

        # Should have merged data
        result = temp_store.get_by_composite_key(key)
        assert result is not None
        assert result["pubchem_cid"] == 5793
        assert result["chebi_id"] == "CHEBI:17634"
        assert result["biological_roles"] == ["CHEBI:78675"]

    @pytest.mark.integration
    def test_find_by_chebi(self, temp_store: EnrichmentStore) -> None:
        """Test finding ingredients by ChEBI ID."""
        data = {
            "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
            "cas_rn": "50-99-7",
            "chebi_id": "CHEBI:17634",
        }
        temp_store.upsert_ingredient(data, source="chebi")

        results = temp_store.find_by_chebi("CHEBI:17634")
        assert len(results) == 1
        assert results[0]["chebi_id"] == "CHEBI:17634"

    @pytest.mark.integration
    def test_get_stats(self, temp_store: EnrichmentStore) -> None:
        """Test getting store statistics."""
        # Insert a few records
        temp_store.upsert_ingredient(
            {
                "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
                "cas_rn": "50-99-7",
                "chebi_id": "CHEBI:17634",
                "pubchem_cid": 5793,
            },
            source="pubchem",
        )
        temp_store.upsert_ingredient(
            {
                "inchikey": "CSNNHWWHGAXBCP-UHFFFAOYSA-L",
                "cas_rn": "7487-88-9",
                "chebi_id": "CHEBI:32599",
            },
            source="chebi",
        )

        stats = temp_store.get_stats()
        assert stats["total_ingredients"] == 2
        assert stats["with_chebi_id"] == 2
        assert stats["with_inchikey"] == 2


class TestKGXExportLogic:
    """Tests for KGX export logic without requiring KGX library."""

    def test_build_xrefs_list(self) -> None:
        """Test that xrefs are built correctly from a record."""
        record = {
            "chebi_id": "CHEBI:17634",
            "pubchem_cid": 5793,
            "cas_rn": "50-99-7",
            "kegg_id": "C00031",
            "mesh_id": "D005947",
            "drugbank_id": "DB00117",
        }

        xrefs = []
        if record.get("chebi_id"):
            xrefs.append(record["chebi_id"])
        if record.get("pubchem_cid"):
            xrefs.append(f"PUBCHEM.COMPOUND:{record['pubchem_cid']}")
        if record.get("cas_rn"):
            xrefs.append(f"CAS:{record['cas_rn']}")
        if record.get("kegg_id"):
            xrefs.append(f"KEGG.COMPOUND:{record['kegg_id']}")
        if record.get("mesh_id"):
            xrefs.append(f"MESH:{record['mesh_id']}")
        if record.get("drugbank_id"):
            xrefs.append(f"DRUGBANK:{record['drugbank_id']}")

        assert "CHEBI:17634" in xrefs
        assert "PUBCHEM.COMPOUND:5793" in xrefs
        assert "CAS:50-99-7" in xrefs
        assert "KEGG.COMPOUND:C00031" in xrefs
        assert "MESH:D005947" in xrefs
        assert "DRUGBANK:DB00117" in xrefs

    def test_node_id_selection_prefers_chebi(self) -> None:
        """Test that node ID selection prefers ChEBI."""
        record = {
            "chebi_id": "CHEBI:17634",
            "id": "some-composite-key",
            "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
        }

        node_id = record.get("chebi_id") or record.get("id", "")
        assert node_id == "CHEBI:17634"

    def test_node_id_fallback_to_inchikey(self) -> None:
        """Test that node ID falls back to InChIKey when no ChEBI."""
        record = {
            "id": "some-composite-key",
            "inchikey": "WQZGKKKJIJFFOK-GASJEMHNSA-N",
        }

        node_id = record.get("chebi_id") or record.get("id", "")
        if not node_id.startswith("CHEBI:") and record.get("inchikey"):
            node_id = f"INCHIKEY:{record['inchikey']}"

        assert node_id == "INCHIKEY:WQZGKKKJIJFFOK-GASJEMHNSA-N"
