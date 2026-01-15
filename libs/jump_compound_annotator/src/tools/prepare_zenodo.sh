#!/bin/bash
# Prepare jump_compound_annotator outputs for Zenodo deposit
# Usage: ./prepare_zenodo.sh <input_dir> <output_dir>

set -e

INPUT_DIR="$1"
OUTPUT_DIR="$2"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "$INPUT_DIR" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Usage: $0 <input_dir> <output_dir>"
    exit 1
fi

[ -d "$OUTPUT_DIR" ] && echo "Error: $OUTPUT_DIR already exists" && exit 1

echo "Preparing Zenodo deposit: $INPUT_DIR -> $OUTPUT_DIR"

# Create directories
mkdir -p "$OUTPUT_DIR"/{annotations,mappings,intermediate,raw_sources}

# Copy and rename annotation files
cp "$INPUT_DIR/annotations.parquet" "$OUTPUT_DIR/annotations/compound_gene.parquet" 2>/dev/null || true
cp "$INPUT_DIR/gene_interactions.parquet" "$OUTPUT_DIR/annotations/gene_gene.parquet" 2>/dev/null || true
cp "$INPUT_DIR/compound_interactions.parquet" "$OUTPUT_DIR/annotations/compound_compound.parquet" 2>/dev/null || true
cp "$INPUT_DIR/filtered_annotations.parquet" "$OUTPUT_DIR/annotations/compound_gene_curated.parquet" 2>/dev/null || true

# Copy mapper files
for f in pointers.csv unichem_{chembl,drugbank,pubchem}_mapper.parquet mychem_{chembl,drugbank,pubchem}_mapper.parquet; do
    cp "$INPUT_DIR/$f" "$OUTPUT_DIR/mappings/" 2>/dev/null || true
done

# Compress intermediate directories
for d in ids errors external_ids; do
    [ -d "$INPUT_DIR/$d" ] && tar -czf "$OUTPUT_DIR/intermediate/$d.tar.gz" -C "$INPUT_DIR" "$d"
done

# Compress raw source directories
for d in biokg dgidb drugrep hetionet hgnc ncbi openbiolink opentargets pharmebinet primekg; do
    [ -d "$INPUT_DIR/$d" ] && tar -czf "$OUTPUT_DIR/raw_sources/$d.tar.gz" -C "$INPUT_DIR" "$d"
done

echo "Done! Total size: $(du -sh "$OUTPUT_DIR" | cut -f1)"
