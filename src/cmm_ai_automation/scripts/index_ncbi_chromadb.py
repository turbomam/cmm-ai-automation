#!/usr/bin/env python3
"""Index NCBI cache data into ChromaDB for fuzzy/semantic search.

Creates searchable indexes of NCBI taxonomy and assembly data from
the ncbi_cache MongoDB database.

Usage:
    uv run python -m cmm_ai_automation.scripts.index_ncbi_chromadb
    uv run python -m cmm_ai_automation.scripts.index_ncbi_chromadb --demo
"""

import logging

import chromadb
import click
from pymongo import MongoClient
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CHROMA_PATH = "data/chroma_ncbi"
MONGODB_URI = "mongodb://localhost:27017/"


def flatten_taxonomy_doc(doc: dict) -> tuple[str, dict]:
    """Flatten taxonomy cache document for ChromaDB indexing.

    Returns (searchable_text, metadata).
    """
    parts = []
    metadata = {}

    query_id = doc.get("query_id", "")
    metadata["ncbi_taxon_id"] = query_id

    response = doc.get("response", {})

    # Scientific name
    sci_name = response.get("ScientificName", {}).get("@text", "")
    if sci_name:
        parts.append(f"Scientific name: {sci_name}")
        metadata["scientific_name"] = sci_name

    # Other names
    other_names = response.get("OtherNames", {})
    if other_names:
        # Synonym
        synonym = other_names.get("Synonym", {})
        if isinstance(synonym, dict):
            syn_text = synonym.get("@text", "")
            if syn_text:
                parts.append(f"Synonym: {syn_text}")
        elif isinstance(synonym, list):
            syns = [s.get("@text", "") for s in synonym if isinstance(s, dict)]
            if syns:
                parts.append(f"Synonyms: {', '.join(syns)}")

        # Common name
        common = other_names.get("CommonName", {})
        if isinstance(common, dict):
            common_text = common.get("@text", "")
            if common_text:
                parts.append(f"Common name: {common_text}")
                metadata["common_name"] = common_text

        # GenbankCommonName
        genbank_common = other_names.get("GenbankCommonName", {})
        if isinstance(genbank_common, dict):
            gb_text = genbank_common.get("@text", "")
            if gb_text:
                parts.append(f"GenBank common name: {gb_text}")

    # Rank
    rank = response.get("Rank", {}).get("@text", "")
    if rank:
        parts.append(f"Rank: {rank}")
        metadata["rank"] = rank

    # Lineage
    lineage = response.get("Lineage", {}).get("@text", "")
    if lineage:
        parts.append(f"Lineage: {lineage}")

    # Division
    division = response.get("Division", {}).get("@text", "")
    if division:
        parts.append(f"Division: {division}")
        metadata["division"] = division

    # Parent taxon ID
    parent_id = response.get("ParentTaxId", {}).get("@text", "")
    if parent_id:
        metadata["parent_taxon_id"] = parent_id

    searchable_text = "\n".join(parts)
    return searchable_text, metadata


def flatten_assembly_doc(doc: dict) -> tuple[str, dict]:
    """Flatten assembly cache document for ChromaDB indexing.

    Returns (searchable_text, metadata).
    """
    parts = []
    metadata = {}

    query_id = doc.get("query_id", "")
    metadata["query_accession"] = query_id

    response = doc.get("response", {})

    # Get the resolved UID
    uid = response.get("_resolved_uid", "")
    if uid:
        metadata["ncbi_uid"] = uid

    # Get the document data from esummary result
    result = response.get("result", {})
    if not result:
        return "", metadata

    # Get the assembly record (keyed by UID)
    assembly = None
    for key, val in result.items():
        if key != "uids" and isinstance(val, dict):
            assembly = val
            break

    if not assembly:
        return "", metadata

    # Assembly name
    asm_name = assembly.get("assemblyname", "")
    if asm_name:
        parts.append(f"Assembly name: {asm_name}")
        metadata["assembly_name"] = asm_name

    # Organism name
    org_name = assembly.get("organism", "")
    if org_name:
        parts.append(f"Organism: {org_name}")
        metadata["organism"] = org_name

    # Strain/infraspecific name
    infraspecific = assembly.get("infraspecificname", "")
    if infraspecific:
        parts.append(f"Strain: {infraspecific}")
        metadata["strain"] = infraspecific

    # Biosample
    biosample = assembly.get("biosample", "")
    if biosample:
        parts.append(f"BioSample: {biosample}")
        metadata["biosample"] = biosample

    # Accessions
    accession = assembly.get("assemblyaccession", "")
    if accession:
        parts.append(f"Accession: {accession}")
        metadata["accession"] = accession

    genbank = assembly.get("gbuid", "")
    if genbank:
        parts.append(f"GenBank UID: {genbank}")

    refseq = assembly.get("rsuid", "")
    if refseq:
        parts.append(f"RefSeq UID: {refseq}")

    # Submitter
    submitter = assembly.get("submitterorganization", "")
    if submitter:
        parts.append(f"Submitter: {submitter}")

    # Assembly status
    status = assembly.get("assemblystatus", "")
    if status:
        parts.append(f"Status: {status}")
        metadata["status"] = status

    # Taxon ID
    taxid = assembly.get("taxid", "")
    if taxid:
        metadata["ncbi_taxon_id"] = str(taxid)

    searchable_text = "\n".join(parts)
    return searchable_text, metadata


def extract_linkout_info(doc: dict) -> list[dict]:
    """Extract linkout information from elink response."""
    linkouts = []
    response = doc.get("response", {})

    # Navigate the nested structure
    link_set = response.get("LinkSet", {})
    if not link_set:
        return linkouts

    id_url_list = link_set.get("IdUrlList", {})
    if not id_url_list:
        return linkouts

    id_url_set = id_url_list.get("IdUrlSet", {})
    if not id_url_set:
        return linkouts

    obj_urls = id_url_set.get("ObjUrl", [])
    if isinstance(obj_urls, dict):
        obj_urls = [obj_urls]

    for obj in obj_urls:
        if not isinstance(obj, dict):
            continue

        url = obj.get("Url", {}).get("@text", "")
        provider = obj.get("Provider", {})
        provider_name = provider.get("Name", {}).get("@text", "") if isinstance(provider, dict) else ""

        if url:
            linkouts.append(
                {
                    "url": url,
                    "provider": provider_name,
                }
            )

    return linkouts


def extract_entrez_links(doc: dict) -> list[dict]:
    """Extract Entrez internal links from elink response."""
    links = []
    response = doc.get("response", {})

    link_set = response.get("LinkSet", {})
    if not link_set:
        return links

    link_set_dbs = link_set.get("LinkSetDb", [])
    if isinstance(link_set_dbs, dict):
        link_set_dbs = [link_set_dbs]

    for lsdb in link_set_dbs:
        if not isinstance(lsdb, dict):
            continue

        db_to = lsdb.get("DbTo", {}).get("@text", "")
        link_name = lsdb.get("LinkName", {}).get("@text", "")

        link_ids = lsdb.get("Link", [])
        if isinstance(link_ids, dict):
            link_ids = [link_ids]

        ids = []
        for link in link_ids:
            if isinstance(link, dict):
                lid = link.get("Id", {}).get("@text", "")
                if lid:
                    ids.append(lid)

        if db_to and ids:
            links.append(
                {
                    "db": db_to,
                    "link_name": link_name,
                    "count": len(ids),
                    "ids": ids[:10],  # Store first 10 for reference
                }
            )

    return links


def index_taxonomy(mongo_client: MongoClient, chroma_client, clear: bool = False) -> int:
    """Index taxonomy data into ChromaDB."""
    logger.info("\n" + "=" * 50)
    logger.info("Indexing NCBI Taxonomy")
    logger.info("=" * 50)

    cache_db = mongo_client["ncbi_cache"]
    tax_cache = cache_db["ncbi_taxonomy_cache"]
    tax_linkouts = cache_db["ncbi_taxonomy_linkouts_cache"]
    tax_entrez = cache_db["ncbi_taxonomy_entrez_cache"]

    collection_name = "ncbi_taxonomy"

    if clear:
        try:
            chroma_client.delete_collection(collection_name)
            logger.info(f"Cleared existing collection '{collection_name}'")
        except Exception:
            pass

    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "NCBI Taxonomy data for semantic search"},
    )

    # Build linkouts and entrez link indexes
    linkouts_by_id = {}
    for doc in tax_linkouts.find({}):
        linkouts_by_id[doc["query_id"]] = extract_linkout_info(doc)

    entrez_by_id = {}
    for doc in tax_entrez.find({}):
        entrez_by_id[doc["query_id"]] = extract_entrez_links(doc)

    # Index taxonomy records
    indexed = 0
    for doc in tqdm(tax_cache.find({}), total=tax_cache.count_documents({}), desc="Taxonomy"):
        query_id = doc.get("query_id", "")
        if not query_id:
            continue

        searchable_text, metadata = flatten_taxonomy_doc(doc)
        if not searchable_text.strip():
            continue

        # Add linkout summary
        linkouts = linkouts_by_id.get(query_id, [])
        if linkouts:
            providers = list({lo["provider"] for lo in linkouts if lo["provider"]})
            if providers:
                searchable_text += f"\nExternal links: {', '.join(providers)}"
                metadata["linkout_providers"] = ",".join(providers)

        # Add entrez link summary
        entrez = entrez_by_id.get(query_id, [])
        if entrez:
            dbs = list({e["db"] for e in entrez})
            if dbs:
                searchable_text += f"\nEntrez links: {', '.join(dbs)}"
                metadata["entrez_dbs"] = ",".join(dbs)

        doc_id = f"NCBITaxon_{query_id}"
        collection.upsert(
            ids=[doc_id],
            documents=[searchable_text],
            metadatas=[metadata],
        )
        indexed += 1

    logger.info(f"Indexed {indexed} taxonomy records")
    logger.info(f"Collection count: {collection.count()}")
    return indexed


def index_assemblies(mongo_client: MongoClient, chroma_client, clear: bool = False) -> int:
    """Index assembly data into ChromaDB."""
    logger.info("\n" + "=" * 50)
    logger.info("Indexing NCBI Assemblies")
    logger.info("=" * 50)

    cache_db = mongo_client["ncbi_cache"]
    asm_cache = cache_db["ncbi_assembly_cache"]
    asm_linkouts = cache_db["ncbi_assembly_linkouts_cache"]
    asm_entrez = cache_db["ncbi_assembly_entrez_cache"]

    collection_name = "ncbi_assembly"

    if clear:
        try:
            chroma_client.delete_collection(collection_name)
            logger.info(f"Cleared existing collection '{collection_name}'")
        except Exception:
            pass

    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "NCBI Assembly data for semantic search"},
    )

    # Build linkouts and entrez link indexes by UID
    linkouts_by_uid = {}
    for doc in asm_linkouts.find({}):
        linkouts_by_uid[doc["query_id"]] = extract_linkout_info(doc)

    entrez_by_uid = {}
    for doc in asm_entrez.find({}):
        entrez_by_uid[doc["query_id"]] = extract_entrez_links(doc)

    # Index assembly records
    indexed = 0
    for doc in tqdm(asm_cache.find({}), total=asm_cache.count_documents({}), desc="Assemblies"):
        query_id = doc.get("query_id", "")
        if not query_id:
            continue

        searchable_text, metadata = flatten_assembly_doc(doc)
        if not searchable_text.strip():
            continue

        # Get UID for linkout/entrez lookup
        uid = metadata.get("ncbi_uid", "")

        # Add linkout summary
        if uid:
            linkouts = linkouts_by_uid.get(uid, [])
            if linkouts:
                providers = list({lo["provider"] for lo in linkouts if lo["provider"]})
                if providers:
                    searchable_text += f"\nExternal links: {', '.join(providers)}"
                    metadata["linkout_providers"] = ",".join(providers)

            # Add entrez link summary
            entrez = entrez_by_uid.get(uid, [])
            if entrez:
                dbs = list({e["db"] for e in entrez})
                if dbs:
                    searchable_text += f"\nEntrez links: {', '.join(dbs)}"
                    metadata["entrez_dbs"] = ",".join(dbs)

        doc_id = f"Assembly_{query_id.replace('.', '_')}"
        collection.upsert(
            ids=[doc_id],
            documents=[searchable_text],
            metadatas=[metadata],
        )
        indexed += 1

    logger.info(f"Indexed {indexed} assembly records")
    logger.info(f"Collection count: {collection.count()}")
    return indexed


def demo_searches(chroma_client) -> None:
    """Demonstrate search capabilities."""
    logger.info("\n" + "=" * 60)
    logger.info("DEMO: NCBI ChromaDB Search")
    logger.info("=" * 60)

    # Taxonomy searches
    try:
        tax_collection = chroma_client.get_collection("ncbi_taxonomy")
        logger.info(f"\nTaxonomy collection: {tax_collection.count()} documents")

        tax_queries = [
            ("Methylobacterium", "Genus search"),
            ("methylotroph", "Phenotype/metabolism term"),
            ("Pseudomonas putida", "Species search"),
            ("soil bacteria", "Habitat search"),
        ]

        for query, desc in tax_queries:
            logger.info(f"\n--- Query: '{query}' ({desc}) ---")
            results = tax_collection.query(query_texts=[query], n_results=3)

            for i, (_doc_id, dist, meta) in enumerate(
                zip(results["ids"][0], results["distances"][0], results["metadatas"][0], strict=False)
            ):
                name = meta.get("scientific_name", "Unknown")
                rank = meta.get("rank", "")
                logger.info(f"  {i + 1}. {name} ({rank}) - dist: {dist:.3f}")

    except Exception as e:
        logger.warning(f"Taxonomy demo failed: {e}")

    # Assembly searches
    try:
        asm_collection = chroma_client.get_collection("ncbi_assembly")
        logger.info(f"\nAssembly collection: {asm_collection.count()} documents")

        asm_queries = [
            ("Methylobacterium extorquens", "Species assembly"),
            ("complete genome", "Assembly status"),
            ("GCA_000025305", "Accession search"),
        ]

        for query, desc in asm_queries:
            logger.info(f"\n--- Query: '{query}' ({desc}) ---")
            results = asm_collection.query(query_texts=[query], n_results=3)

            for i, (_doc_id, dist, meta) in enumerate(
                zip(results["ids"][0], results["distances"][0], results["metadatas"][0], strict=False)
            ):
                org = meta.get("organism", "Unknown")
                acc = meta.get("accession", "")
                logger.info(f"  {i + 1}. {org} ({acc}) - dist: {dist:.3f}")

    except Exception as e:
        logger.warning(f"Assembly demo failed: {e}")


@click.command()
@click.option("--clear/--no-clear", default=True, help="Clear existing collections")
@click.option("--demo/--no-demo", default=False, help="Run demo searches after indexing")
@click.option("--demo-only", is_flag=True, help="Only run demo (skip indexing)")
def main(clear: bool, demo: bool, demo_only: bool) -> None:
    """Index NCBI cache data into ChromaDB."""
    logger.info("=" * 60)
    logger.info("NCBI ChromaDB Indexer")
    logger.info("=" * 60)

    mongo_client: MongoClient = MongoClient(MONGODB_URI)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

    if not demo_only:
        index_taxonomy(mongo_client, chroma_client, clear=clear)
        index_assemblies(mongo_client, chroma_client, clear=clear)

    if demo or demo_only:
        demo_searches(chroma_client)

    logger.info("\nDone!")


if __name__ == "__main__":
    main()
