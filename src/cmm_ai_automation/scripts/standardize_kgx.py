import click
import pandas as pd


@click.command()
@click.option("--nodes", type=click.Path(exists=True), required=True, help="Input nodes TSV")
@click.option("--edges", type=click.Path(exists=True), required=True, help="Input edges TSV")
@click.option("--out-nodes", type=click.Path(), required=True, help="Output nodes TSV")
@click.option("--out-edges", type=click.Path(), required=True, help="Output edges TSV")
def standardize(nodes: str, edges: str, out_nodes: str, out_edges: str) -> None:
    """
    Standardize KGX files by ensuring required provenance columns and
    fixing specific prefix case issues (e.g. PUBCHEM.COMPOUND).
    """
    # Load data
    df_nodes = pd.read_csv(nodes, sep="\t", dtype=str)
    df_edges = pd.read_csv(edges, sep="\t", dtype=str)

    # Helper to fix prefixes (ONLY standardizing case for known strictly-cased prefixes)
    def fix_prefix(curie: str) -> str:
        if pd.isna(curie):
            return curie
        if curie.startswith("pubchem.compound:"):
            return curie.replace("pubchem.compound:", "PUBCHEM.COMPOUND:", 1)
        return curie

    # Fix Node IDs
    df_nodes["id"] = df_nodes["id"].apply(fix_prefix)

    # Fix Edge Subject/Object
    df_edges["subject"] = df_edges["subject"].apply(fix_prefix)
    df_edges["object"] = df_edges["object"].apply(fix_prefix)

    # Ensure Provenance Columns exist and are populated
    if "knowledge_level" not in df_edges.columns:
        df_edges["knowledge_level"] = "knowledge_assertion"
    else:
        df_edges["knowledge_level"] = df_edges["knowledge_level"].fillna("knowledge_assertion")

    if "agent_type" not in df_edges.columns:
        df_edges["agent_type"] = "manual_agent"
    else:
        df_edges["agent_type"] = df_edges["agent_type"].fillna("manual_agent")

    # Save
    df_nodes.to_csv(out_nodes, sep="\t", index=False)
    df_edges.to_csv(out_edges, sep="\t", index=False)

    click.echo(f"Written standardized files to {out_nodes} and {out_edges}")


if __name__ == "__main__":
    standardize()
