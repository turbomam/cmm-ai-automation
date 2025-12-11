"""MediaDive MongoDB client.

A client for querying MediaDive data from a local MongoDB database.
The data is loaded by the load_mediadive_mongodb.py script.

This provides faster lookups than the REST API and enables searching
by various fields (name, CAS-RN, ChEBI, etc.) that aren't available
via the REST API.

MediaDive is authoritative for MediaDive ingredient/solution IDs.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

logger = logging.getLogger(__name__)

# Default MongoDB connection settings
DEFAULT_MONGODB_URI = "mongodb://localhost:27017"
DEFAULT_DATABASE_NAME = "mediadive"


@dataclass
class MediaDiveMongoIngredient:
    """Ingredient from MediaDive MongoDB.

    MediaDive is authoritative for these IDs.

    Attributes:
        id: MediaDive ingredient ID
        name: Ingredient name
        cas_rn: CAS Registry Number
        chebi: ChEBI ID
        pubchem: PubChem CID
        kegg: KEGG Compound ID
        metacyc: MetaCyc ID
        formula: Molecular formula
        mass: Molecular mass
        is_complex: True if complex/undefined mixture
        synonyms: List of synonym names
    """

    id: int
    name: str
    cas_rn: str | None = None
    chebi: int | None = None
    pubchem: int | None = None
    kegg: str | None = None
    metacyc: str | None = None
    formula: str | None = None
    mass: float | None = None
    is_complex: bool = False
    synonyms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "mediadive_id": self.id,
            "mediadive_name": self.name,
            "mediadive_cas_rn": self.cas_rn,
            "mediadive_chebi": self.chebi,
            "mediadive_pubchem": self.pubchem,
            "mediadive_kegg": self.kegg,
            "mediadive_metacyc": self.metacyc,
            "mediadive_formula": self.formula,
            "mediadive_mass": self.mass,
            "mediadive_is_complex": self.is_complex,
        }


@dataclass
class MediaDiveMongoSolution:
    """Solution from MediaDive MongoDB.

    Attributes:
        id: MediaDive solution ID
        name: Solution name
        volume: Total volume in ml
        recipe: Recipe items as raw dicts
    """

    id: int
    name: str
    volume: float | None = None
    recipe: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MediaDiveMongoLookupError:
    """Error from a failed MongoDB lookup.

    Attributes:
        query: The query that was made
        error_code: Error code
        error_message: Human-readable error message
    """

    query: str
    error_code: str
    error_message: str


class MediaDiveMongoClient:
    """Client for MediaDive data in MongoDB.

    Provides fast lookups and searching capabilities not available
    via the REST API.

    MediaDive is the authoritative source for MediaDive ingredient/solution IDs.

    Example:
        >>> client = MediaDiveMongoClient()
        >>> result = client.get_ingredient_by_id(1)
        >>> if isinstance(result, MediaDiveMongoIngredient):
        ...     print(f"Name: {result.name}, CAS: {result.cas_rn}")

        >>> # Search by name
        >>> results = client.search_ingredients_by_name("peptone")
        >>> for r in results:
        ...     print(f"{r.id}: {r.name}")

        >>> # Find by ChEBI
        >>> result = client.find_ingredient_by_chebi(30729)
    """

    def __init__(
        self,
        mongodb_uri: str = DEFAULT_MONGODB_URI,
        database_name: str = DEFAULT_DATABASE_NAME,
    ):
        """Initialize MediaDive MongoDB client.

        Args:
            mongodb_uri: MongoDB connection URI
            database_name: Name of the MediaDive database
        """
        self.mongodb_uri = mongodb_uri
        self.database_name = database_name
        self._client: MongoClient[dict[str, Any]] | None = None
        self._db: Database[dict[str, Any]] | None = None

    def _get_db(self) -> Database[dict[str, Any]]:
        """Get or create MongoDB database connection."""
        if self._db is None:
            self._client = MongoClient(self.mongodb_uri)
            self._db = self._client[self.database_name]
        return self._db

    def _get_ingredients_collection(self) -> Collection[dict[str, Any]]:
        """Get the ingredients collection."""
        return self._get_db().ingredients

    def _get_solutions_collection(self) -> Collection[dict[str, Any]]:
        """Get the solutions collection."""
        return self._get_db().solutions

    def close(self) -> None:
        """Close the MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    # =========================================================================
    # Ingredient Lookups (MediaDive is authoritative for these)
    # =========================================================================

    def get_ingredient_by_id(self, ingredient_id: int) -> MediaDiveMongoIngredient | MediaDiveMongoLookupError:
        """Get an ingredient by MediaDive ID.

        Args:
            ingredient_id: MediaDive ingredient ID

        Returns:
            MediaDiveMongoIngredient on success, MediaDiveMongoLookupError on failure
        """
        try:
            collection = self._get_ingredients_collection()
            doc = collection.find_one({"_id": ingredient_id})

            if not doc:
                return MediaDiveMongoLookupError(
                    query=f"ingredient_id:{ingredient_id}",
                    error_code="NOT_FOUND",
                    error_message=f"Ingredient ID {ingredient_id} not found",
                )

            return self._parse_ingredient(doc)

        except Exception as e:
            return MediaDiveMongoLookupError(
                query=f"ingredient_id:{ingredient_id}",
                error_code="MONGODB_ERROR",
                error_message=str(e),
            )

    def search_ingredients_by_name(self, name: str, exact: bool = False) -> list[MediaDiveMongoIngredient]:
        """Search ingredients by name.

        Args:
            name: Name to search for
            exact: If True, require exact match (case-insensitive)

        Returns:
            List of matching ingredients
        """
        try:
            collection = self._get_ingredients_collection()

            if exact:
                # Case-insensitive exact match
                query = {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
            else:
                # Case-insensitive substring match
                query = {"name": {"$regex": re.escape(name), "$options": "i"}}

            results = []
            for doc in collection.find(query):
                results.append(self._parse_ingredient(doc))

            return results

        except Exception as e:
            logger.warning(f"Error searching ingredients by name '{name}': {e}")
            return []

    def find_ingredient_by_cas(self, cas_rn: str) -> MediaDiveMongoIngredient | None:
        """Find an ingredient by CAS Registry Number.

        Args:
            cas_rn: CAS Registry Number (e.g., "50-99-7")

        Returns:
            MediaDiveMongoIngredient if found, None otherwise
        """
        try:
            collection = self._get_ingredients_collection()
            doc = collection.find_one({"CAS-RN": cas_rn})

            if doc:
                return self._parse_ingredient(doc)
            return None

        except Exception as e:
            logger.warning(f"Error finding ingredient by CAS '{cas_rn}': {e}")
            return None

    def find_ingredient_by_chebi(self, chebi_id: int | str) -> MediaDiveMongoIngredient | None:
        """Find an ingredient by ChEBI ID.

        Args:
            chebi_id: ChEBI ID (numeric, without CHEBI: prefix)

        Returns:
            MediaDiveMongoIngredient if found, None otherwise
        """
        try:
            # Normalize to int
            chebi_int = int(str(chebi_id).replace("CHEBI:", ""))

            collection = self._get_ingredients_collection()
            doc = collection.find_one({"ChEBI": chebi_int})

            if doc:
                return self._parse_ingredient(doc)
            return None

        except Exception as e:
            logger.warning(f"Error finding ingredient by ChEBI '{chebi_id}': {e}")
            return None

    def find_ingredient_by_pubchem(self, pubchem_cid: int) -> MediaDiveMongoIngredient | None:
        """Find an ingredient by PubChem CID.

        Args:
            pubchem_cid: PubChem Compound ID

        Returns:
            MediaDiveMongoIngredient if found, None otherwise
        """
        try:
            collection = self._get_ingredients_collection()
            doc = collection.find_one({"PubChem": pubchem_cid})

            if doc:
                return self._parse_ingredient(doc)
            return None

        except Exception as e:
            logger.warning(f"Error finding ingredient by PubChem '{pubchem_cid}': {e}")
            return None

    def find_ingredient_by_kegg(self, kegg_id: str) -> MediaDiveMongoIngredient | None:
        """Find an ingredient by KEGG Compound ID.

        Args:
            kegg_id: KEGG Compound ID (e.g., "C00031")

        Returns:
            MediaDiveMongoIngredient if found, None otherwise
        """
        try:
            collection = self._get_ingredients_collection()
            doc = collection.find_one({"KEGG-Compound": kegg_id})

            if doc:
                return self._parse_ingredient(doc)
            return None

        except Exception as e:
            logger.warning(f"Error finding ingredient by KEGG '{kegg_id}': {e}")
            return None

    def get_all_ingredients_with_chebi(self) -> list[MediaDiveMongoIngredient]:
        """Get all ingredients that have a ChEBI ID.

        Returns:
            List of ingredients with ChEBI IDs
        """
        try:
            collection = self._get_ingredients_collection()
            results = []

            for doc in collection.find({"ChEBI": {"$ne": None}}):
                results.append(self._parse_ingredient(doc))

            return results

        except Exception as e:
            logger.warning(f"Error getting ingredients with ChEBI: {e}")
            return []

    def get_all_ingredients_with_cas(self) -> list[MediaDiveMongoIngredient]:
        """Get all ingredients that have a CAS Registry Number.

        Returns:
            List of ingredients with CAS-RN
        """
        try:
            collection = self._get_ingredients_collection()
            results = []

            for doc in collection.find({"CAS-RN": {"$ne": None}}):
                results.append(self._parse_ingredient(doc))

            return results

        except Exception as e:
            logger.warning(f"Error getting ingredients with CAS: {e}")
            return []

    # =========================================================================
    # Solution Lookups
    # =========================================================================

    def get_solution_by_id(self, solution_id: int) -> MediaDiveMongoSolution | MediaDiveMongoLookupError:
        """Get a solution by MediaDive ID.

        Args:
            solution_id: MediaDive solution ID

        Returns:
            MediaDiveMongoSolution on success, MediaDiveMongoLookupError on failure
        """
        try:
            collection = self._get_solutions_collection()
            doc = collection.find_one({"_id": solution_id})

            if not doc:
                return MediaDiveMongoLookupError(
                    query=f"solution_id:{solution_id}",
                    error_code="NOT_FOUND",
                    error_message=f"Solution ID {solution_id} not found",
                )

            return self._parse_solution(doc)

        except Exception as e:
            return MediaDiveMongoLookupError(
                query=f"solution_id:{solution_id}",
                error_code="MONGODB_ERROR",
                error_message=str(e),
            )

    def search_solutions_by_name(self, name: str, exact: bool = False) -> list[MediaDiveMongoSolution]:
        """Search solutions by name.

        Args:
            name: Name to search for
            exact: If True, require exact match (case-insensitive)

        Returns:
            List of matching solutions
        """
        try:
            collection = self._get_solutions_collection()

            if exact:
                query = {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
            else:
                query = {"name": {"$regex": re.escape(name), "$options": "i"}}

            results = []
            for doc in collection.find(query):
                results.append(self._parse_solution(doc))

            return results

        except Exception as e:
            logger.warning(f"Error searching solutions by name '{name}': {e}")
            return []

    # =========================================================================
    # Stats and Info
    # =========================================================================

    def get_ingredient_count(self) -> int:
        """Get total number of ingredients in the database."""
        try:
            count: int = int(self._get_ingredients_collection().count_documents({}))
            return count
        except Exception:
            return 0

    def get_solution_count(self) -> int:
        """Get total number of solutions in the database."""
        try:
            count: int = int(self._get_solutions_collection().count_documents({}))
            return count
        except Exception:
            return 0

    def get_xref_counts(self) -> dict[str, int]:
        """Get counts of ingredients with each type of cross-reference.

        Returns:
            Dict with counts for each xref type
        """
        try:
            collection = self._get_ingredients_collection()
            return {
                "total": collection.count_documents({}),
                "cas_rn": collection.count_documents({"CAS-RN": {"$ne": None}}),
                "chebi": collection.count_documents({"ChEBI": {"$ne": None}}),
                "pubchem": collection.count_documents({"PubChem": {"$ne": None}}),
                "kegg": collection.count_documents({"KEGG-Compound": {"$ne": None}}),
                "metacyc": collection.count_documents({"MetaCyc": {"$ne": None}}),
            }
        except Exception as e:
            logger.warning(f"Error getting xref counts: {e}")
            return {}

    # =========================================================================
    # Parsing
    # =========================================================================

    def _parse_ingredient(self, doc: dict[str, Any]) -> MediaDiveMongoIngredient:
        """Parse a MongoDB document into a MediaDiveMongoIngredient."""
        return MediaDiveMongoIngredient(
            id=doc.get("id", doc.get("_id", 0)),
            name=doc.get("name", ""),
            cas_rn=doc.get("CAS-RN"),
            chebi=doc.get("ChEBI"),
            pubchem=doc.get("PubChem"),
            kegg=doc.get("KEGG-Compound"),
            metacyc=doc.get("MetaCyc"),
            formula=doc.get("formula"),
            mass=doc.get("mass"),
            is_complex=bool(doc.get("complex_compound")),
            synonyms=doc.get("synonyms", []),
        )

    def _parse_solution(self, doc: dict[str, Any]) -> MediaDiveMongoSolution:
        """Parse a MongoDB document into a MediaDiveMongoSolution."""
        return MediaDiveMongoSolution(
            id=doc.get("id", doc.get("_id", 0)),
            name=doc.get("name", ""),
            volume=doc.get("volume"),
            recipe=doc.get("recipe", []),
        )
