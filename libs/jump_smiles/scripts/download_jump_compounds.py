#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas>=2.2.0",
#     "pooch>=1.8.0",
#     "tqdm>=4.64.1",
# ]
# ///
"""
Download JUMP compound dataset and extract only SMILES column.

Usage:
    uv run --script scripts/download_jump_compounds.py
"""

import pandas as pd
import pooch
from pathlib import Path

# Configuration
CACHE_DIR = Path(__file__).parent.parent / "test/test_data/jump_compounds"
URL = "https://github.com/jump-cellpainting/datasets/refs/tags/v0.13/metadata/compound.csv.gz"
OUTPUT_FILE = CACHE_DIR / "smiles_only.csv.gz"


def main():
    """Download and process JUMP compounds data."""

    # Create cache directory
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Download with pooch (automatic caching)
    print("Downloading/loading JUMP compounds data...")
    file_path = pooch.retrieve(
        url=URL,
        known_hash=None,  # Will compute on first download
        path=CACHE_DIR,
        fname="compound.csv.gz",
        progressbar=True,
    )

    # Load and extract SMILES column
    print("Extracting SMILES column...")
    df = pd.read_csv(
        file_path, compression="gzip", usecols=["Metadata_JCP2022", "Metadata_SMILES"]
    )

    # Clean data
    original_count = len(df)
    df = df[df["Metadata_SMILES"].notna()]
    df = df[df["Metadata_SMILES"] != ""]

    # Save compressed
    df.to_csv(
        OUTPUT_FILE, compression={"method": "gzip", "compresslevel": 9}, index=False
    )

    # Report
    print(f"Saved {len(df)}/{original_count} valid SMILES")
    print(f"  File: {OUTPUT_FILE}")
    print(f"  Size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
