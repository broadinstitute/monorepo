#!/bin/bash
set -e  # Exit on any failure
# Run copairs examples using the runner
#
# This script demonstrates:
# 1. LINCS workflow: activity analysis → consistency analysis (shared directory)
# 2. JUMP analysis: independent run with timestamped output
#
# Output structure:
# output/
# ├── lincs/shared/      # LINCS workflow outputs
# └── jump-target2/      # JUMP experiment outputs (timestamped)

# Create directories if they don't exist
mkdir -p input

# Download the data file if it doesn't exist
DATA_FILE="input/2016_04_01_a549_48hr_batch1_plateSQ00014812.csv"
if [ ! -f "$DATA_FILE" ]; then
    echo "Downloading data file..."
    COMMIT="da8ae6a3bc103346095d61b4ee02f08fc85a5d98"
    PLATE="SQ00014812"
    URL="https://media.githubusercontent.com/media/broadinstitute/lincs-cell-painting/${COMMIT}/profiles/2016_04_01_a549_48hr_batch1/${PLATE}/${PLATE}_normalized_feature_select.csv.gz"
    
    # Download and decompress
    wget -O "${DATA_FILE}.gz" "$URL"
    gunzip "${DATA_FILE}.gz"
    echo "Data file downloaded successfully!"
else
    echo "Data file already exists, skipping download."
fi

echo -e "\nSetting environment variables..."
export COPAIRS_DATA=.
export COPAIRS_OUTPUT=.

echo -e "\nRunning LINCS workflow..."
echo "1. Phenotypic activity analysis..."
uv run src/copairs_runner/copairs_runner.py --config-dir configs --config-name example_activity_lincs

# Check LINCS activity outputs exist
test -f output/lincs/shared/activity/activity_ap_scores.csv && echo "  ✓ activity_ap_scores.csv"
test -f output/lincs/shared/activity/activity_map_results.csv && echo "  ✓ activity_map_results.csv"
test -f output/lincs/shared/activity/activity_map_plot.png && echo "  ✓ activity_map_plot.png"

# Quick data check - CSV should have more than header row
[ $(wc -l < output/lincs/shared/activity/activity_ap_scores.csv) -gt 1 ] && echo "  ✓ AP scores has data"

# Store a hash of full results for drift detection
AP_HASH=$(tail -n +2 output/lincs/shared/activity/activity_ap_scores.csv | md5sum | cut -c1-8)
echo "  Activity hash: $AP_HASH"

# Validate against expected hash
[ "$AP_HASH" = "c5c5a06a" ] || echo "  WARNING: Output changed! Expected: c5c5a06a, got: $AP_HASH"

echo -e "\n2. Phenotypic consistency analysis (depends on activity results)..."
uv run src/copairs_runner/copairs_runner.py --config-dir configs --config-name example_consistency_lincs

# Check consistency outputs
test -f output/lincs/shared/consistency/consistency_ap_scores.csv && echo "  ✓ consistency_ap_scores.csv"
test -f output/lincs/shared/consistency/consistency_map_results.csv && echo "  ✓ consistency_map_results.csv"
test -f output/lincs/shared/consistency/consistency_map_plot.png && echo "  ✓ consistency_map_plot.png"

# Check consistency hash
CONS_HASH=$(tail -n +2 output/lincs/shared/consistency/consistency_ap_scores.csv | md5sum | cut -c1-8)
echo "  Consistency hash: $CONS_HASH"
[ "$CONS_HASH" = "ee5ff2b3" ] || echo "  WARNING: Output changed! Expected: ee5ff2b3, got: $CONS_HASH"

echo -e "\nRunning JUMP-CP analysis..."
echo "Note: This will download data from S3 on first run"
uv run src/copairs_runner/copairs_runner.py --config-dir configs --config-name example_activity_jump_target2

# Check JUMP outputs (find the timestamped directory)
JUMP_DIR=$(ls -td output/jump-target2/*/*/ 2>/dev/null | head -1)
if [ -n "$JUMP_DIR" ]; then
    test -f "${JUMP_DIR}activity_ap_scores.csv" && echo "  ✓ activity_ap_scores.csv"
    test -f "${JUMP_DIR}activity_map_results.csv" && echo "  ✓ activity_map_results.csv" 
    test -f "${JUMP_DIR}activity_map_plot.png" && echo "  ✓ activity_map_plot.png"
fi

echo -e "\nOutput directories:"
echo "- output/lincs/shared/     # LINCS workflow results"
echo "- output/jump-target2/     # JUMP timestamped results"
