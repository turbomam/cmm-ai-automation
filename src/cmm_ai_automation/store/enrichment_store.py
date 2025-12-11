"""Enrichment store using linkml-store for ingredient data management.

This module provides a schema-aware data store for enriched ingredients,
using linkml-store with DuckDB backend for local persistence.

Key features:
- (inchikey, cas_rn) tuple as primary key for entity resolution
- Source-specific authoritative IDs (each API owns its own ID type)
- Conflict detection and logging
- Provenance tracking per field

References:
    - linkml-store: https://linkml.io/linkml-store/
    - KGX format: https://github.com/biolink/kgx
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from linkml_store import Client
from linkml_store.api import Collection, Database

logger = logging.getLogger(__name__)

# Schema path
SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "cmm_ai_automation.yaml"

# Default store path
DEFAULT_STORE_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "enrichment.duckdb"

# Authoritative sources for each field type
AUTHORITATIVE_SOURCES = {
    # Each API is authoritative for its own primary ID
    "pubchem_cid": "pubchem",
    "chebi_id": "chebi",
    "cas_rn": "cas",
    "mediadive_id": "mediadive",
    # ChEBI is authoritative for roles
    "biological_roles": "chebi",
    "chemical_roles": "chebi",
    "application_roles": "chebi",
    # Chemical structure - first source wins
    "inchi": None,  # No single authoritative source
    "inchikey": None,
    "smiles": None,
}


def generate_composite_key(inchikey: str | None, cas_rn: str | None) -> str:
    """Generate a composite key from (inchikey, cas_rn) tuple.

    The composite key format is: {inchikey}|{cas_rn}
    If either is missing, a UUID is generated for that part.

    Args:
        inchikey: InChIKey string (may be None)
        cas_rn: CAS Registry Number (may be None)

    Returns:
        Composite key string
    """
    ik_part = inchikey if inchikey else f"uuid:{uuid.uuid4().hex[:8]}"
    cas_part = cas_rn if cas_rn else "unknown"
    return f"{ik_part}|{cas_part}"


def parse_composite_key(key: str) -> tuple[str | None, str | None]:
    """Parse a composite key back to (inchikey, cas_rn) tuple.

    Args:
        key: Composite key string

    Returns:
        Tuple of (inchikey, cas_rn) - may contain None for missing parts
    """
    parts = key.split("|", 1)
    if len(parts) != 2:
        return (None, None)

    inchikey = None if parts[0].startswith("uuid:") else parts[0]
    cas_rn = None if parts[1] == "unknown" else parts[1]
    return (inchikey, cas_rn)


class EnrichmentStore:
    """Store for enriched ingredient data using linkml-store.

    Uses (inchikey, cas_rn) tuple as primary key for entity resolution.
    Each API is authoritative for its own ID type.

    Example:
        >>> store = EnrichmentStore()
        >>> store.upsert_ingredient({
        ...     "inchikey": "CSNNHWWHGAXBCP-UHFFFAOYSA-L",
        ...     "cas_rn": "7487-88-9",
        ...     "name": "magnesium sulfate",
        ...     "pubchem_cid": 24083,
        ... }, source="pubchem")
        >>> ingredient = store.get_by_key("CSNNHWWHGAXBCP-UHFFFAOYSA-L", "7487-88-9")
    """

    def __init__(
        self,
        store_path: Path | str | None = None,
        schema_path: Path | str | None = None,
    ):
        """Initialize the enrichment store.

        Args:
            store_path: Path to DuckDB database file
            schema_path: Path to LinkML schema file
        """
        self.store_path = Path(store_path) if store_path else DEFAULT_STORE_PATH
        self.schema_path = Path(schema_path) if schema_path else SCHEMA_PATH

        # Ensure store directory exists
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize linkml-store client
        self._client: Client | None = None
        self._db: Database | None = None
        self._collection: Collection | None = None

    def _get_client(self) -> Client:
        """Get or create the linkml-store client."""
        if self._client is None:
            self._client = Client()
        return self._client

    def _get_db(self) -> Database:
        """Get or create the database connection."""
        if self._db is None:
            client = self._get_client()
            # Use DuckDB backend
            db_url = f"duckdb:///{self.store_path}"
            self._db = client.attach_database(db_url, alias="enrichment")
        return self._db

    def _get_collection(self) -> Collection:
        """Get or create the enriched_ingredients collection."""
        if self._collection is None:
            db = self._get_db()
            # Create or get the collection with schema
            # Use EnrichedIngredient class from LinkML schema to define structure
            self._collection = db.create_collection(
                "enriched_ingredients",
                recreate_if_exists=False,
                class_name="EnrichedIngredient",
                schema_location=str(self.schema_path),
            )
        return self._collection

    def close(self) -> None:
        """Close the store connection."""
        self._collection = None
        self._db = None
        self._client = None

    def upsert_ingredient(
        self,
        data: dict[str, Any],
        source: str,
        query: str | None = None,
    ) -> str:
        """Insert or update an enriched ingredient.

        Uses (inchikey, cas_rn) for entity resolution. If an existing record
        is found with the same key, fields are merged with conflict detection.

        Args:
            data: Ingredient data dictionary
            source: Name of the data source (pubchem, chebi, cas, etc.)
            query: Original query used to retrieve this data

        Returns:
            The composite key of the upserted record
        """
        collection = self._get_collection()

        # Generate composite key
        inchikey = data.get("inchikey")
        cas_rn = data.get("cas_rn")
        composite_key = generate_composite_key(inchikey, cas_rn)

        # Check for existing record
        existing = self.get_by_composite_key(composite_key)

        if existing:
            # Merge with existing record
            merged = self._merge_records(existing, data, source, query)
            merged["id"] = composite_key
            merged["last_enriched"] = datetime.now().isoformat()
            # Delete existing record and insert merged (upsert not implemented in DuckDB backend)
            # NOTE: This is not atomic - if insert fails, data is lost. Consider using transactions
            # or a backup strategy for production use. For now, log the merged data before operations.
            logger.debug(f"Updating ingredient {composite_key}: {merged}")
            try:
                collection.delete_where({"id": composite_key})
                collection.insert([merged])
                collection.commit()  # Ensure changes are persisted
                logger.info(f"Updated ingredient: {composite_key}")
            except Exception as e:
                logger.error(f"Failed to update ingredient {composite_key}: {e}")
                logger.error(f"Merged data that was lost: {merged}")
                raise
        else:
            # New record
            data["id"] = composite_key
            data["last_enriched"] = datetime.now().isoformat()
            data["source_records"] = [
                {
                    "source_name": source,
                    "source_id": self._get_source_id(data, source),
                    "source_timestamp": datetime.now().isoformat(),
                    "source_query": query,
                    "source_fields": list(data.keys()),
                }
            ]
            data["conflicts"] = []
            collection.insert([data])
            logger.info(f"Inserted new ingredient: {composite_key}")

        return composite_key

    def _get_source_id(self, data: dict[str, Any], source: str) -> str | None:
        """Extract the relevant ID from data based on source."""
        source_id_fields = {
            "pubchem": "pubchem_cid",
            "chebi": "chebi_id",
            "cas": "cas_rn",
            "mediadive": "mediadive_id",
            "node_normalization": "chebi_id",
        }
        field = source_id_fields.get(source)
        if field:
            return str(data.get(field, ""))
        return None

    def _merge_records(
        self,
        existing: dict[str, Any],
        new_data: dict[str, Any],
        source: str,
        query: str | None,
    ) -> dict[str, Any]:
        """Merge new data into existing record with conflict detection.

        Primary APIs are authoritative for their own ID types.
        """
        merged = existing.copy()
        conflicts = list(existing.get("conflicts", []))
        source_records = list(existing.get("source_records", []))

        # Track fields updated by this source
        updated_fields = []

        for field, new_value in new_data.items():
            if field in ("id", "source_records", "conflicts", "last_enriched"):
                continue

            if new_value is None:
                continue

            existing_value = merged.get(field)

            if existing_value is None:
                # No existing value, use new one
                merged[field] = new_value
                updated_fields.append(field)
            elif existing_value != new_value:
                # Conflict detected - check authoritativeness
                authoritative_source = AUTHORITATIVE_SOURCES.get(field)

                if authoritative_source == source:
                    # This source is authoritative for this field - overwrite
                    merged[field] = new_value
                    updated_fields.append(field)
                    conflicts.append(
                        {
                            "field_name": field,
                            "primary_source": source,
                            "primary_value": str(new_value),
                            "conflicting_source": "previous",
                            "conflicting_value": str(existing_value),
                            "resolution": "primary_source_wins",
                            "resolution_notes": f"{source} is authoritative for {field}",
                        }
                    )
                elif authoritative_source is None:
                    # No authoritative source - keep existing value but log
                    conflicts.append(
                        {
                            "field_name": field,
                            "primary_source": "first_source",
                            "primary_value": str(existing_value),
                            "conflicting_source": source,
                            "conflicting_value": str(new_value),
                            "resolution": "unresolved",
                            "resolution_notes": "No authoritative source defined, keeping first value",
                        }
                    )
                else:
                    # Different authoritative source - log conflict
                    conflicts.append(
                        {
                            "field_name": field,
                            "primary_source": authoritative_source,
                            "primary_value": str(existing_value),
                            "conflicting_source": source,
                            "conflicting_value": str(new_value),
                            "resolution": "unresolved",
                            "resolution_notes": f"Authoritative source is {authoritative_source}, not {source}",
                        }
                    )

        # Add source record
        source_records.append(
            {
                "source_name": source,
                "source_id": self._get_source_id(new_data, source),
                "source_timestamp": datetime.now().isoformat(),
                "source_query": query,
                "source_fields": updated_fields,
            }
        )

        merged["conflicts"] = conflicts
        merged["source_records"] = source_records

        return merged

    def get_by_composite_key(self, composite_key: str) -> dict[str, Any] | None:
        """Get an ingredient by composite key.

        Args:
            composite_key: The composite key ({inchikey}|{cas_rn})

        Returns:
            Ingredient data dict or None if not found
        """
        collection = self._get_collection()
        results = collection.find({"id": composite_key})
        # QueryResult has a rows attribute containing list of dicts
        if results.rows:
            row: dict[str, Any] = results.rows[0]
            return row
        return None

    def get_by_key(self, inchikey: str | None, cas_rn: str | None) -> dict[str, Any] | None:
        """Get an ingredient by (inchikey, cas_rn) tuple.

        Args:
            inchikey: InChIKey string
            cas_rn: CAS Registry Number

        Returns:
            Ingredient data dict or None if not found
        """
        composite_key = generate_composite_key(inchikey, cas_rn)
        return self.get_by_composite_key(composite_key)

    def find_by_chebi(self, chebi_id: str) -> list[dict[str, Any]]:
        """Find ingredients by ChEBI ID.

        Args:
            chebi_id: ChEBI ID (e.g., "CHEBI:32599")

        Returns:
            List of matching ingredient records
        """
        collection = self._get_collection()
        results = collection.find({"chebi_id": chebi_id})
        return results.rows or []

    def find_by_pubchem(self, pubchem_cid: int) -> list[dict[str, Any]]:
        """Find ingredients by PubChem CID.

        Args:
            pubchem_cid: PubChem Compound ID

        Returns:
            List of matching ingredient records
        """
        collection = self._get_collection()
        results = collection.find({"pubchem_cid": pubchem_cid})
        return results.rows or []

    def find_by_cas(self, cas_rn: str) -> list[dict[str, Any]]:
        """Find ingredients by CAS Registry Number.

        Args:
            cas_rn: CAS Registry Number

        Returns:
            List of matching ingredient records
        """
        collection = self._get_collection()
        results = collection.find({"cas_rn": cas_rn})
        return results.rows or []

    def get_all_conflicts(self) -> list[dict[str, Any]]:
        """Get all records that have unresolved conflicts.

        Returns:
            List of records with conflicts
        """
        collection = self._get_collection()
        all_records = collection.find({})
        return [
            r
            for r in (all_records.rows or [])
            if r.get("conflicts") and any(c.get("resolution") == "unresolved" for c in r.get("conflicts", []))
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the enrichment store.

        Returns:
            Dict with counts and coverage statistics
        """
        collection = self._get_collection()
        all_records = collection.find({}).rows or []

        total = len(all_records)
        with_chebi = sum(1 for r in all_records if r.get("chebi_id"))
        with_pubchem = sum(1 for r in all_records if r.get("pubchem_cid"))
        with_cas = sum(1 for r in all_records if r.get("cas_rn"))
        with_inchikey = sum(1 for r in all_records if r.get("inchikey"))
        with_roles = sum(1 for r in all_records if r.get("biological_roles"))
        with_conflicts = sum(1 for r in all_records if r.get("conflicts"))

        return {
            "total_ingredients": total,
            "with_chebi_id": with_chebi,
            "with_pubchem_cid": with_pubchem,
            "with_cas_rn": with_cas,
            "with_inchikey": with_inchikey,
            "with_biological_roles": with_roles,
            "with_conflicts": with_conflicts,
            "coverage_chebi": with_chebi / total if total > 0 else 0,
            "coverage_pubchem": with_pubchem / total if total > 0 else 0,
            "coverage_cas": with_cas / total if total > 0 else 0,
        }

    def export_to_kgx(self, output_path: Path) -> tuple[int, int]:
        """Export enriched ingredients to KGX TSV format using KGX API.

        Uses the KGX TsvSink for proper KGX-compatible output.
        KGX format is used by KG-Microbe and other KG-Hub projects.

        Creates:
        - {output_path}_nodes.tsv - All ingredient nodes (biolink:SmallMolecule)
        - {output_path}_edges.tsv - Cross-reference relationships

        Args:
            output_path: Base path for output files (without _nodes.tsv suffix)

        Returns:
            Tuple of (nodes_exported, edges_exported)
        """
        from kgx.graph.nx_graph import NxGraph
        from kgx.sink.tsv_sink import TsvSink

        collection = self._get_collection()
        all_records = list(collection.find({}))

        # Create KGX graph
        graph = NxGraph()
        graph.name = "cmm-ai-automation"

        # Add custom node properties to track
        custom_node_props = {
            "xref",
            "inchikey",
            "cas_rn",
            "chebi_id",
            "pubchem_cid",
            "chemical_formula",
            "smiles",
            "biological_roles",
            "molecular_mass",
        }

        # Edge properties - per Chris's request for better edge property usage
        custom_edge_props = {
            "knowledge_source",
            "primary_knowledge_source",
            "aggregator_knowledge_source",
            "original_subject",
            "original_object",
        }

        node_count = 0
        edge_count = 0

        for record in all_records:
            # Build xrefs list
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

            # Determine best ID for node (prefer ChEBI)
            node_id = record.get("chebi_id") or record.get("id", "")
            if not node_id.startswith("CHEBI:") and record.get("inchikey"):
                node_id = f"INCHIKEY:{record['inchikey']}"

            # Build node attributes
            node_attrs = {
                "name": record.get("name", ""),
                "category": ["biolink:SmallMolecule"],
                "provided_by": ["cmm-ai-automation"],
            }

            if record.get("description"):
                node_attrs["description"] = record["description"]
            if xrefs:
                node_attrs["xref"] = xrefs
            if record.get("inchikey"):
                node_attrs["inchikey"] = record["inchikey"]
            if record.get("cas_rn"):
                node_attrs["cas_rn"] = record["cas_rn"]
            if record.get("chebi_id"):
                node_attrs["chebi_id"] = record["chebi_id"]
            if record.get("pubchem_cid"):
                node_attrs["pubchem_cid"] = record["pubchem_cid"]
            if record.get("chemical_formula"):
                node_attrs["chemical_formula"] = record["chemical_formula"]
            if record.get("smiles"):
                node_attrs["smiles"] = record["smiles"]
            if record.get("molecular_mass"):
                node_attrs["molecular_mass"] = record["molecular_mass"]
            if record.get("biological_roles"):
                node_attrs["biological_roles"] = record["biological_roles"]

            # Add node to graph
            graph.add_node(node_id, **node_attrs)
            node_count += 1

            # Create edges for "same_as" relationships between identifiers
            # This captures the entity resolution we've done
            if record.get("chebi_id") and record.get("pubchem_cid"):
                pubchem_id = f"PUBCHEM.COMPOUND:{record['pubchem_cid']}"
                edge_id = f"{record['chebi_id']}-same_as-{pubchem_id}"

                # Rich edge properties per Chris's guidance
                graph.add_edge(
                    record["chebi_id"],
                    pubchem_id,
                    id=edge_id,
                    subject=record["chebi_id"],
                    predicate="biolink:same_as",
                    object=pubchem_id,
                    category=["biolink:ChemicalToChemicalAssociation"],
                    provided_by=["cmm-ai-automation"],
                    knowledge_source=["infores:cmm-ai-automation"],
                    primary_knowledge_source="infores:cmm-ai-automation",
                    aggregator_knowledge_source=["infores:chebi", "infores:pubchem"],
                )
                edge_count += 1

        # Write using TsvSink
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sink = TsvSink(owner=None, filename=str(output_path), format="tsv")

        # Add custom properties to sink
        sink.node_properties.update(custom_node_props)
        sink.edge_properties.update(custom_edge_props)

        # Write nodes
        for node_id, node_data in graph.nodes(data=True):
            record = {"id": node_id, **node_data}
            sink.write_node(record)

        # Write edges
        for s, o, edge_data in graph.edges(data=True):
            record = edge_data.copy()
            if "id" not in record:
                record["id"] = f"{s}-{record.get('predicate', 'related_to')}-{o}"
            sink.write_edge(record)

        sink.finalize()

        logger.info(f"Exported {node_count} nodes and {edge_count} edges to {output_path}")
        return (node_count, edge_count)

    def export_to_kgx_nodes(self, output_path: Path) -> int:
        """Export enriched ingredients to KGX nodes TSV format (legacy method).

        Deprecated: Use export_to_kgx() instead for proper KGX API usage.

        Args:
            output_path: Path to write nodes TSV file

        Returns:
            Number of nodes exported
        """
        # Convert to base path for new method
        base_path = output_path.parent / output_path.stem.replace("_nodes", "")
        nodes, _ = self.export_to_kgx(base_path)
        return nodes
