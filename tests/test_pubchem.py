"""Tests for PubChem client."""

import pytest

from cmm_ai_automation.clients.pubchem import (
    CompoundResult,
    LookupError,
    PubChemClient,
)


class TestPubChemClient:
    """Tests for PubChemClient."""

    @pytest.fixture
    def client(self) -> PubChemClient:
        """Create a PubChem client for testing."""
        return PubChemClient()

    @pytest.mark.integration
    def test_get_compound_by_name_glucose(self, client: PubChemClient) -> None:
        """Test looking up glucose by name."""
        result = client.get_compound_by_name("glucose")

        assert isinstance(result, CompoundResult)
        assert result.CID == 5793
        assert result.name_queried == "glucose"
        assert result.MolecularFormula == "C6H12O6"
        assert result.InChIKey == "WQZGKKKJIJFFOK-GASJEMHNSA-N"
        assert result.CanonicalSMILES is not None

    @pytest.mark.integration
    def test_get_compound_by_name_not_found(self, client: PubChemClient) -> None:
        """Test looking up a nonexistent compound."""
        result = client.get_compound_by_name("xyznotarealcompound123")

        assert isinstance(result, LookupError)
        assert result.name_queried == "xyznotarealcompound123"
        assert "NotFound" in result.error_code or "PUGREST" in result.error_code

    @pytest.mark.integration
    def test_get_compound_by_cid(self, client: PubChemClient) -> None:
        """Test looking up a compound by CID."""
        result = client.get_compound_by_cid(5793)  # glucose

        assert isinstance(result, CompoundResult)
        assert result.CID == 5793
        assert result.MolecularFormula == "C6H12O6"

    @pytest.mark.integration
    def test_get_synonyms(self, client: PubChemClient) -> None:
        """Test getting synonyms for a compound."""
        result = client.get_synonyms(5793)  # glucose

        assert isinstance(result, list)
        assert len(result) > 0
        # Glucose should have common synonyms
        synonyms_lower = [s.lower() for s in result]
        assert any("glucose" in s for s in synonyms_lower)

    @pytest.mark.integration
    def test_complex_compound_name(self, client: PubChemClient) -> None:
        """Test looking up a compound with a complex name."""
        result = client.get_compound_by_name("magnesium sulfate heptahydrate")

        assert isinstance(result, CompoundResult)
        assert result.CID is not None
        assert result.MolecularFormula is not None

    def test_compound_result_to_dict(self) -> None:
        """Test CompoundResult serialization."""
        result = CompoundResult(
            CID=5793,
            name_queried="glucose",
            MolecularFormula="C6H12O6",
            MolecularWeight=180.16,
            InChIKey="WQZGKKKJIJFFOK-GASJEMHNSA-N",
        )

        d = result.to_dict()
        assert d["CID"] == 5793
        assert d["name_queried"] == "glucose"
        assert d["MolecularFormula"] == "C6H12O6"
        assert d["MolecularWeight"] == 180.16
        assert d["InChIKey"] == "WQZGKKKJIJFFOK-GASJEMHNSA-N"
        assert d["CanonicalSMILES"] is None  # Not set
