#!/usr/bin/env python3
"""
Extract edge patterns from KGX files with flat naming convention.

For files named *_nodes.tsv and *_edges.tsv in a single directory.
Output format matches extract_edge_patterns.py:
    source | subject_category | subject_prefix | predicate | object_category | object_prefix | count
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

CURIE_PATTERN = re.compile(r"^([^:]+):(.+)$")


def extract_prefix(curie: str) -> str:
    """Extract prefix from CURIE."""
    if not curie:
        return "(empty)"
    match = CURIE_PATTERN.match(curie.strip())
    if match:
        return match.group(1)
    return "(invalid)"


def load_node_categories(nodes_files: list[Path]) -> dict:
    """Load node categories from multiple node files."""
    node_categories = {}
    for nodes_file in nodes_files:
        with nodes_file.open() as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                node_id = row.get("id", "").strip()
                category = row.get("category", "").strip()
                if node_id:
                    node_categories[node_id] = category if category else "(empty)"
    return node_categories


def analyze_edges(edges_file: Path, node_categories: dict, source: str) -> Counter:
    """Analyze edges and return patterns."""
    patterns = Counter()
    with edges_file.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            subj = row.get("subject", "").strip()
            pred = row.get("predicate", "").strip()
            obj = row.get("object", "").strip()

            subj_cat = node_categories.get(subj, "(unknown)")
            obj_cat = node_categories.get(obj, "(unknown)")

            subj_prefix = extract_prefix(subj)
            obj_prefix = extract_prefix(obj)

            pattern = (source, subj_cat, subj_prefix, pred, obj_cat, obj_prefix)
            patterns[pattern] += 1

    return patterns


def main():
    """Main function to analyze KGX files."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_kgx_patterns.py <kgx_dir>", file=sys.stderr)
        sys.exit(1)

    kgx_dir = Path(sys.argv[1])
    if not kgx_dir.is_dir():
        print(f"Error: {kgx_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Find all *_nodes.tsv and *_edges.tsv files
    nodes_files = sorted(kgx_dir.glob("*_nodes.tsv"))
    edges_files = sorted(kgx_dir.glob("*_edges.tsv"))

    if not nodes_files:
        print(f"Error: No *_nodes.tsv files found in {kgx_dir}", file=sys.stderr)
        sys.exit(1)

    if not edges_files:
        print(f"Error: No *_edges.tsv files found in {kgx_dir}", file=sys.stderr)
        sys.exit(1)

    # Load all node categories from all node files
    node_categories = load_node_categories(nodes_files)

    # Analyze all edge files
    all_patterns = Counter()
    for edges_file in edges_files:
        source = edges_file.stem.replace("_edges", "")
        patterns = analyze_edges(edges_file, node_categories, source)
        all_patterns.update(patterns)

    # Output as TSV (same format as extract_edge_patterns.py)
    writer = csv.writer(sys.stdout, delimiter="\t")
    writer.writerow(
        ["source", "subject_category", "subject_prefix", "predicate", "object_category", "object_prefix", "count"]
    )

    # Sort by count descending
    for pattern, count in sorted(all_patterns.items(), key=lambda x: -x[1]):
        writer.writerow([*pattern, count])


if __name__ == "__main__":
    main()
