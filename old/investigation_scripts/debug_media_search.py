import chromadb

# Connect to Chroma
client_dive = chromadb.PersistentClient(path="data/chroma_mediadive")
col_dive = client_dive.get_collection("mediadive_media")

client_togo = chromadb.PersistentClient(path="data/chroma_togomedium")
col_togo = client_togo.get_collection("togomedium_media")

queries = [
    "Medium 88",
    "Sulphur medium",
    "Paracoccus medium",
    "Hypho",
    "Hyphomicrobium",
    "PIPES",
    "Methanol Peptone Yeast Glucose",
    "MPYG",
]

print("--- MEDIADIVE SEARCH ---")
res_dive = col_dive.query(query_texts=queries, n_results=3)
for q, ids, metas, dists in zip(queries, res_dive["ids"], res_dive["metadatas"], res_dive["distances"], strict=False):
    print(f"\nQuery: {q}")
    for id, meta, dist in zip(ids, metas, dists, strict=False):
        print(f"  [{dist:.3f}] {id}: {meta.get('name')}")

print("\n\n--- TOGOMEDIUM SEARCH ---")
res_togo = col_togo.query(query_texts=queries, n_results=3)
for q, ids, metas, dists in zip(queries, res_togo["ids"], res_togo["metadatas"], res_togo["distances"], strict=False):
    print(f"\nQuery: {q}")
    for id, meta, dist in zip(ids, metas, dists, strict=False):
        print(f"  [{dist:.3f}] {id}: {meta.get('name')} (Orig: {meta.get('original_id')})")
