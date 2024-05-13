#!/usr/bin/env jupyter
"""
Generate metadata files to improve the looks of the datasette tables.
It is mostly boilerplate code but it makes it the tables more accessible.

The goal is to generate multiple files with this schema.
{
    "databases": {
        "data": {
            "source": "Alternative source",
            "source_url": "http://example.com/",
            "tables": {
                "content": {
                    "title": "Dataset Process",
                    "description_html": "Custom <em>table</em> description",
                    "license": "CC BY 3.0 US",
                    "license_url": "https://creativecommons.org/licenses/by/3.0/us/"
                }
            }
        }
    }
}
"""
import json
from importlib.resources import files
from itertools import product
from pathlib import Path


def build_metadata_tree(title) -> dict[str, dict[str, dict[str, dict[str, str]]]]:
    content = {"databases": {"data": {"tables": {"content": {"title": title}}}}}
    return content


def create_metadata_trees(out_path: Path) -> None:
    titles = list(
        map(
            lambda x: " ".join(x),
            (
                product(
                    ("ORF", "CRISPR", "Compound"),
                    ("Gallery", "Matches", "Feature Ranking"),
                )
            ),
        )
    )
    trees = list(map(lambda x: build_metadata_tree(x), titles))
    out_path.mkdir(parents=True, exist_ok=True)
    for tree, title in zip(trees, titles):
        filepath = out_path / "_".join(title.lower().split(" ")[:2])

        with open(f"{filepath}.json", "w") as f:
            json.dump(tree, f)


if __name__ == "__main__":
    src_path = files("jump_rr")
    create_metadata_trees(src_path / ".." / ".." / "metadata")
