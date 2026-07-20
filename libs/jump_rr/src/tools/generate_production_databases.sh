#!/usr/bin/env bash
# Generate only the paper-specific compound tables; the standard workflow is unchanged.

set -euo pipefail

python "../jump_rr/calculate_production_matches.py"
python "../jump_rr/calculate_production_features.py"
