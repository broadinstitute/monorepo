#!/bin/bash
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

echo -e "\n2. Phenotypic consistency analysis (depends on activity results)..."
uv run src/copairs_runner/copairs_runner.py --config-dir configs --config-name example_consistency_lincs

echo -e "\nRunning JUMP-CP analysis..."
echo "Note: This will download data from S3 on first run"
uv run src/copairs_runner/copairs_runner.py --config-dir configs --config-name example_activity_jump_target2

echo -e "\nAll analyses complete! Check the output directory:"
echo "- output/lincs/shared/     # LINCS workflow results"
echo "- output/jump-target2/     # JUMP timestamped results"
