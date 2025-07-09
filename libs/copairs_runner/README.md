# Copairs Runner

YAML-driven runner for [copairs](https://github.com/broadinstitute/copairs) morphological profiling analyses.

## Usage

```bash
uv run copairs_runner.py config.yaml
```

## Configuration

```yaml
# Required
data:
  path: "data.csv"  # or .parquet

average_precision:
  params:
    pos_sameby: ["Metadata_compound"]
    pos_diffby: []
    neg_sameby: []
    neg_diffby: ["Metadata_compound"]

output:
  path: "results.csv"

# Optional
preprocessing:
  - type: filter
    params:
      query: "Metadata_dose > 0.1"

mean_average_precision:
  params:
    sameby: ["Metadata_compound"]
    null_size: 1000000
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

- `configs/activity_analysis.yaml`: Phenotypic activity
- `configs/consistency_analysis.yaml`: Target consistency

Run both: `./run_examples.sh`

### Example Output

The runner generates scatter plots showing mean average precision (mAP) vs statistical significance:

**Phenotypic Activity Assessment:**
![Activity Plot](examples/example_activity_plot.png)

**Phenotypic Consistency (Target-based):**
![Consistency Plot](examples/example_consistency_plot.png)