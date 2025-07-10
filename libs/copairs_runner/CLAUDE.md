# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

copairs_runner is a configurable Python script for running copairs analyses on cell painting data. It's part of a larger monorepo focused on morphological profiling and drug discovery through cellular imaging.

## Key Commands

### Running Analyses
```bash
# Set environment variables (if used in config)
export COPAIRS_DATA=. COPAIRS_OUTPUT=.

# Run analysis with a config file from the configs/ directory
uv run copairs_runner.py --config-name <config_name>

# Run with verbose logging
uv run copairs_runner.py --config-name <config_name> hydra.verbose=true

# Override configuration parameters
uv run copairs_runner.py --config-name <config_name> param.name=value

# Run the example analyses (downloads data if needed)
bash run_examples.sh
```

### Development Commands
```bash
# Lint code using uvx (following monorepo standards)
uvx ruff check copairs_runner.py

# Auto-fix linting issues
uvx ruff check copairs_runner.py --fix

# Format code
uvx ruff format copairs_runner.py

# Run tests (when implemented)
pytest tests/
```

## Architecture

### Core Components
1. **copairs_runner.py**: Main script with inline dependencies (PEP 723)
   - `CopairsRunner` class: Handles data loading, preprocessing, analysis, and visualization
   - Key methods:
     - `run()`: Main pipeline orchestrator
     - `load_data()`: Supports CSV/Parquet from local files, URLs, and S3
     - `preprocess_data()`: Applies configurable preprocessing pipeline
     - `run_average_precision()`: Calculates AP for compound activity
     - `run_mean_average_precision()`: Calculates mAP with significance testing
     - `plot_map_results()`: Creates scatter plots of mAP vs -log10(p-value)
     - `save_results()`: Saves results to CSV/Parquet files

2. **Configuration System**: YAML-based configuration with sections for:
   - `data`: Input paths, metadata patterns, and lazy loading options
   - `preprocessing`: Pipeline steps (filtering, aggregation, etc.)
   - `average_precision`/`mean_average_precision`: Analysis parameters
   - `output`: Result file paths
   - `plotting`: Visualization settings

### Preprocessing Pipeline
The runner supports these preprocessing steps (order determined by config):
1. `filter`: Apply pandas query expressions
2. `dropna`: Remove rows with NaN values in specified columns
3. `remove_nan_features`: Remove feature columns containing NaN
4. `split_multilabel`: Split pipe-separated values into lists
5. `filter_active`: Filter based on activity CSV with below_corrected_p column
6. `aggregate_replicates`: Aggregate by taking median of features
7. `merge_metadata`: Merge external CSV metadata
8. `filter_single_replicates`: Remove groups with < min_replicates members
9. `apply_assign_reference`: Apply copairs.matching.assign_reference_index

## Important Context

### Monorepo Standards
This project is part of a monorepo that uses:
- **uv** for package management (transitioning from Poetry)
- **ruff** for formatting and linting
- **pytest** for testing (>90% coverage target)
- **numpy** documentation style
- Conventional commits for commit messages

### Current State
- The script uses inline dependencies (PEP 723 format)
- Has a minimal pyproject.toml for ruff configuration
- No test suite exists yet
- Examples use LINCS Cell Painting data from GitHub
- Supports lazy loading for large parquet files using polars
- Configuration files demonstrate typical usage patterns

### Dependencies
Required packages (from inline script metadata):
- python >= 3.8
- pandas, numpy, copairs, omegaconf, pyarrow, matplotlib, seaborn, polars

### Data Loading Capabilities
- Supports local files, HTTP URLs, and S3 paths
- Automatic data download and caching for URLs
- Lazy loading for large parquet files with polars
- Paths resolved relative to current working directory (CWD)
- Environment variables must be set when used (e.g., ${oc.env:COPAIRS_DATA})

## Common Tasks

### Adding New Preprocessing Steps
1. Implement a new method `_preprocess_<step_name>` in `CopairsRunner` class
2. The method should accept `df` and `params` arguments
3. Add documentation for the new step in the `preprocess_data()` docstring
4. Use the step in your YAML config with `type: <step_name>`

### Creating New Analysis Configs
1. Copy an existing config from `configs/`
2. Modify data paths and preprocessing steps
3. Adjust analysis parameters as needed
4. Run with: `uv run copairs_runner.py --config-name your_config`

### Working with Large Datasets
For memory-efficient processing:
1. Use lazy filtering in the data config for parquet files:
   ```yaml
   data:
     path: "huge_dataset.parquet"
     use_lazy_filter: true
     filter_query: "Metadata_PlateType == 'TARGET2'"  # SQL syntax
     columns: ["Metadata_compound", "feature1", "feature2"]  # optional
   ```
   This filters BEFORE loading into memory using polars.

2. For standard filtering after loading, use preprocessing:
   ```yaml
   preprocessing:
     steps:
       - type: filter
         params:
           query: "Metadata_dose > 0.1"  # pandas query syntax
   ```

3. Enable `save_intermediate: true` in preprocessing for debugging

Note: Lazy filtering uses SQL syntax (polars), while preprocessing uses pandas query syntax

### Debugging
- Use `hydra.verbose=true` for detailed logging
- Check intermediate results with `save_intermediate: true` in preprocessing
- Examine output CSV files for analysis results
- Review preprocessing logs to understand data transformations

## Configuration Examples

### Minimal Activity Analysis
```yaml
data:
  path: "path/to/profiles.parquet"

average_precision:
  params:
    pos_sameby: ["Metadata_broad_sample"]
    pos_diffby: []
    neg_sameby: []
    neg_diffby: ["Metadata_broad_sample", "Metadata_Plate"]

mean_average_precision:
  params:
    sameby: ["Metadata_broad_sample"]
    null_size: 1000000
    threshold: 0.05
    seed: 0

output:
  path: "results/map_results.csv"
```

### Advanced Preprocessing Pipeline
```yaml
preprocessing:
  steps:
    - type: filter
      params:
        query: "Metadata_broad_sample != 'DMSO'"
    - type: aggregate_replicates
      params:
        groupby: ["Metadata_broad_sample", "Metadata_Plate"]
    - type: apply_assign_reference
      params:
        reference_query: "Metadata_broad_sample == 'DMSO'"
        not_reference_query: "Metadata_broad_sample != 'DMSO'"
```