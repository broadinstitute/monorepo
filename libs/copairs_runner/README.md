# Copairs Runner

YAML-driven runner for [copairs](https://github.com/broadinstitute/copairs).

## Usage

```bash
uv run copairs_runner.py config.yaml
```

## Configuration

```yaml
# Required sections
data:
  path: "data.csv"  # or .parquet, URLs, S3 paths
  
  # For large parquet files - filter BEFORE loading into memory:
  # use_lazy_filter: true
  # filter_query: "Metadata_PlateType == 'TARGET2'"  # SQL syntax
  # columns: ["Metadata_col1", "feature_1", "feature_2"]  # optional

# Optional sections
preprocessing:
  steps:
    # Standard filtering - happens AFTER data is loaded:
    - type: filter
      params:
        query: "Metadata_dose > 0.1"  # pandas query syntax

average_precision:
  params:
    pos_sameby: ["Metadata_compound"]
    pos_diffby: []
    neg_sameby: []
    neg_diffby: ["Metadata_compound"]

output:
  path: "results.csv"

mean_average_precision:
  params:
    sameby: ["Metadata_compound"]
    null_size: 10000  # Typically 10000-100000
    threshold: 0.05
    seed: 0

plotting:
  enabled: true
  path: "plot.png"
```

## Preprocessing Steps

- `filter`: Filter rows with pandas query
- `dropna`: Remove rows with NaN
- `aggregate_replicates`: Median aggregation by group
- `merge_metadata`: Join external CSV
- `split_multilabel`: Split pipe-separated values
- See `copairs_runner.py` docstring for complete list

## Examples

- `configs/example_activity_lincs.yaml`: Phenotypic activity
- `configs/example_consistency_lincs.yaml`: Target consistency

Run all examples: `./run_examples.sh`

### Example Output

The runner generates scatter plots showing mean average precision (mAP) vs statistical significance:

**Phenotypic Activity Assessment:**
![Activity Plot](examples/example_activity_plot.png)

**Phenotypic Consistency (Target-based):**
![Consistency Plot](examples/example_consistency_plot.png)
