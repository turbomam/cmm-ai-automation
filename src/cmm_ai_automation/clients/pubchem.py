"""PubChem PUG-REST API client.

A thin, typed wrapper around PubChem's PUG-REST JSON API for compound lookups.

References:
    - PUG-REST docs: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
    - CHEMINF ontology: https://pmc.ncbi.nlm.nih.gov/articles/PMC3184996/
"""

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# PubChem rate limit: max 5 requests per second
# We use 0.25s delay to stay well under limit
DEFAULT_RATE_LIMIT_DELAY = 0.25

# Properties to fetch from PubChem
# See: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest#section=Compound-Property-Tables
COMPOUND_PROPERTIES = [
    "MolecularFormula",
    "MolecularWeight",
    "CanonicalSMILES",
    "IsomericSMILES",
    "InChI",
    "InChIKey",
    "IUPACName",
    "Title",  # Common/preferred name
    "XLogP",
    "ExactMass",
    "MonoisotopicMass",
    "Charge",
]


@dataclass
class CompoundResult:
    """Result from a PubChem compound lookup.

    Field names match PubChem PUG-REST API property names.
    See: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest#section=Compound-Property-Tables

    Attributes:
        CID: PubChem Compound ID
        name_queried: The name we searched for (not a PubChem field)
        MolecularFormula: Chemical formula (e.g., "C6H12O6")
        MolecularWeight: Molecular weight in g/mol
        CanonicalSMILES: Canonical SMILES string (no stereochemistry)
        IsomericSMILES: Isomeric SMILES (with stereochemistry)
        InChI: Full InChI string
        InChIKey: InChIKey hash (27 characters)
        IUPACName: IUPAC systematic name
        Title: Common/preferred name from PubChem
        ExactMass: Exact mass
        MonoisotopicMass: Monoisotopic mass
        Charge: Formal charge
        XLogP: Computed XLogP (partition coefficient)
    """

    CID: int
    name_queried: str
    MolecularFormula: str | None = None
    MolecularWeight: float | None = None
    CanonicalSMILES: str | None = None
    IsomericSMILES: str | None = None
    InChI: str | None = None
    InChIKey: str | None = None
    IUPACName: str | None = None
    Title: str | None = None
    ExactMass: float | None = None
    MonoisotopicMass: float | None = None
    Charge: int | None = None
    XLogP: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "CID": self.CID,
            "name_queried": self.name_queried,
            "MolecularFormula": self.MolecularFormula,
            "MolecularWeight": self.MolecularWeight,
            "CanonicalSMILES": self.CanonicalSMILES,
            "IsomericSMILES": self.IsomericSMILES,
            "InChI": self.InChI,
            "InChIKey": self.InChIKey,
            "IUPACName": self.IUPACName,
            "Title": self.Title,
            "ExactMass": self.ExactMass,
            "MonoisotopicMass": self.MonoisotopicMass,
            "Charge": self.Charge,
            "XLogP": self.XLogP,
        }


@dataclass
class LookupError:
    """Error from a failed PubChem lookup.

    Attributes:
        name_queried: The name we searched for
        error_code: PubChem error code (e.g., "PUGREST.NotFound")
        error_message: Human-readable error message
    """

    name_queried: str
    error_code: str
    error_message: str


class PubChemClient:
    """Client for PubChem PUG-REST API.

    Example:
        >>> client = PubChemClient()
        >>> result = client.get_compound_by_name("glucose")
        >>> if isinstance(result, CompoundResult):
        ...     print(f"CID: {result.cid}, InChIKey: {result.inchikey}")
        CID: 5793, InChIKey: WQZGKKKJIJFFOK-GASJEMHNSA-N
    """

    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    def __init__(
        self,
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
        timeout: float = 30.0,
    ):
        """Initialize PubChem client.

        Args:
            rate_limit_delay: Seconds to wait between requests (default: 0.25)
            timeout: Request timeout in seconds (default: 30)
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self._last_request_time: float = 0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "cmm-ai-automation/0.1.0 (https://github.com/turbomam/cmm-ai-automation)",
            }
        )

    def _wait_for_rate_limit(self) -> None:
        """Wait if needed to respect rate limit."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str) -> dict[str, Any]:
        """Make a GET request with rate limiting.

        Args:
            url: Full URL to fetch

        Returns:
            Parsed JSON response

        Raises:
            requests.RequestException: On network errors
        """
        self._wait_for_rate_limit()
        logger.debug(f"GET {url}")
        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def get_compound_by_name(
        self, name: str
    ) -> CompoundResult | LookupError:
        """Look up a compound by name.

        Args:
            name: Chemical name to search (e.g., "glucose", "magnesium sulfate heptahydrate")

        Returns:
            CompoundResult on success, LookupError on failure
        """
        # URL-encode the name
        encoded_name = quote(name)
        properties = ",".join(COMPOUND_PROPERTIES)
        url = f"{self.BASE_URL}/compound/name/{encoded_name}/property/{properties}/JSON"

        try:
            data = self._get(url)
        except requests.HTTPError as e:
            # Try to parse PubChem error response
            try:
                error_data = e.response.json()
                fault = error_data.get("Fault", {})
                return LookupError(
                    name_queried=name,
                    error_code=fault.get("Code", "UNKNOWN"),
                    error_message=fault.get("Message", str(e)),
                )
            except Exception:
                return LookupError(
                    name_queried=name,
                    error_code="HTTP_ERROR",
                    error_message=str(e),
                )
        except requests.RequestException as e:
            return LookupError(
                name_queried=name,
                error_code="REQUEST_ERROR",
                error_message=str(e),
            )

        # Parse successful response
        # Note: PubChem returns "ConnectivitySMILES" for canonical and "SMILES" for isomeric
        try:
            props = data["PropertyTable"]["Properties"][0]
            return CompoundResult(
                CID=props["CID"],
                name_queried=name,
                MolecularFormula=props.get("MolecularFormula"),
                MolecularWeight=_to_float(props.get("MolecularWeight")),
                CanonicalSMILES=props.get("ConnectivitySMILES"),
                IsomericSMILES=props.get("SMILES"),
                InChI=props.get("InChI"),
                InChIKey=props.get("InChIKey"),
                IUPACName=props.get("IUPACName"),
                Title=props.get("Title"),
                ExactMass=_to_float(props.get("ExactMass")),
                MonoisotopicMass=_to_float(props.get("MonoisotopicMass")),
                Charge=props.get("Charge"),
                XLogP=_to_float(props.get("XLogP")),
            )
        except (KeyError, IndexError) as e:
            return LookupError(
                name_queried=name,
                error_code="PARSE_ERROR",
                error_message=f"Failed to parse response: {e}",
            )

    def get_compound_by_cid(self, cid: int) -> CompoundResult | LookupError:
        """Look up a compound by PubChem CID.

        Args:
            cid: PubChem Compound ID

        Returns:
            CompoundResult on success, LookupError on failure
        """
        properties = ",".join(COMPOUND_PROPERTIES)
        url = f"{self.BASE_URL}/compound/cid/{cid}/property/{properties}/JSON"

        try:
            data = self._get(url)
        except requests.HTTPError as e:
            try:
                error_data = e.response.json()
                fault = error_data.get("Fault", {})
                return LookupError(
                    name_queried=f"CID:{cid}",
                    error_code=fault.get("Code", "UNKNOWN"),
                    error_message=fault.get("Message", str(e)),
                )
            except Exception:
                return LookupError(
                    name_queried=f"CID:{cid}",
                    error_code="HTTP_ERROR",
                    error_message=str(e),
                )
        except requests.RequestException as e:
            return LookupError(
                name_queried=f"CID:{cid}",
                error_code="REQUEST_ERROR",
                error_message=str(e),
            )

        try:
            props = data["PropertyTable"]["Properties"][0]
            return CompoundResult(
                CID=props["CID"],
                name_queried=f"CID:{cid}",
                MolecularFormula=props.get("MolecularFormula"),
                MolecularWeight=_to_float(props.get("MolecularWeight")),
                CanonicalSMILES=props.get("ConnectivitySMILES"),
                IsomericSMILES=props.get("SMILES"),
                InChI=props.get("InChI"),
                InChIKey=props.get("InChIKey"),
                IUPACName=props.get("IUPACName"),
                Title=props.get("Title"),
                ExactMass=_to_float(props.get("ExactMass")),
                MonoisotopicMass=_to_float(props.get("MonoisotopicMass")),
                Charge=props.get("Charge"),
                XLogP=_to_float(props.get("XLogP")),
            )
        except (KeyError, IndexError) as e:
            return LookupError(
                name_queried=f"CID:{cid}",
                error_code="PARSE_ERROR",
                error_message=f"Failed to parse response: {e}",
            )

    def get_synonyms(self, cid: int) -> list[str] | LookupError:
        """Get all synonyms for a compound by CID.

        Args:
            cid: PubChem Compound ID

        Returns:
            List of synonym strings on success, LookupError on failure
        """
        url = f"{self.BASE_URL}/compound/cid/{cid}/synonyms/JSON"

        try:
            data = self._get(url)
        except requests.HTTPError as e:
            try:
                error_data = e.response.json()
                fault = error_data.get("Fault", {})
                return LookupError(
                    name_queried=f"CID:{cid}",
                    error_code=fault.get("Code", "UNKNOWN"),
                    error_message=fault.get("Message", str(e)),
                )
            except Exception:
                return LookupError(
                    name_queried=f"CID:{cid}",
                    error_code="HTTP_ERROR",
                    error_message=str(e),
                )
        except requests.RequestException as e:
            return LookupError(
                name_queried=f"CID:{cid}",
                error_code="REQUEST_ERROR",
                error_message=str(e),
            )

        try:
            synonyms: list[str] = data["InformationList"]["Information"][0]["Synonym"]
            return synonyms
        except (KeyError, IndexError):
            return []


def _to_float(value: Any) -> float | None:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
