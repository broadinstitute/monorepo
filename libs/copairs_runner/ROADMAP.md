# Roadmap

This document outlines potential future enhancements for copairs_runner. All items are medium priority.

## How This Document Was Created

This roadmap was generated through an AI-assisted process using Claude and Context7. The workflow involved: (1) reviewing the existing copairs_runner implementation to understand current Hydra usage patterns, (2) using Context7 to search and retrieve official Hydra documentation, (3) cross-referencing proposed features against actual Hydra documentation snippets to verify syntax and capabilities, and (4) organizing proposals based on technical feasibility and alignment with the project's single-file philosophy. While every effort was made to ensure accuracy by validating against official documentation, **caveat emptor** - implementations may still require adjustments based on specific Hydra versions and edge cases not covered in the documentation review.

## Testing
- [ ] Single comprehensive integration test that exercises the full pipeline with sample data

## Documentation
- [ ] More example configurations for common use cases (e.g., different compound libraries, plate types, assay variants)

## Hydra Advanced Features

### Dynamic Directory Naming
- [ ] Support for embedding configuration values in output directory paths
  ```yaml
  # Current behavior - all runs go to timestamped directories
  hydra:
    run:
      dir: outputs/${now:%Y-%m-%d_%H-%M-%S}
  
  # Proposed - include analysis parameters in path
  hydra:
    run:
      # If output.name = "activity" and dose parameter = 0.1
      # Creates: outputs/2024-01-15_10-30-45/activity_dose_0.1/
      dir: outputs/${now:%Y-%m-%d_%H-%M-%S}/${output.name}_dose_${dose:0}
  ```
  **Example use case**: Running the same analysis with different dose thresholds would create:
  - `outputs/2024-01-15_10-30-45/activity_dose_0.1/`
  - `outputs/2024-01-15_10-30-45/activity_dose_0.5/`
  - `outputs/2024-01-15_10-30-45/activity_dose_1.0/`

- [ ] Support for `override_dirname` in multirun scenarios
  ```yaml
  # Running: python copairs_runner.py --multirun dose=0.1,0.5,1.0
  
  hydra:
    sweep:
      dir: multirun/${now:%Y-%m-%d}/${now:%H-%M-%S}
      subdir: ${hydra.job.override_dirname}
  
  # Would create (based on actual Hydra behavior):
  # multirun/2024-01-15/10-30-45/dose=0.1/
  # multirun/2024-01-15/10-30-45/dose=0.5/
  # multirun/2024-01-15/10-30-45/dose=1.0/
  ```

- [ ] Ability to exclude verbose parameters from directory names
  ```yaml
  hydra:
    job:
      config:
        override_dirname:
          exclude_keys:
            - preprocessing.filter.params.query  # Don't include long SQL in dirname
            - input.path  # Don't include full paths
  
  # Running: python copairs_runner.py --multirun batch_size=32 learning_rate=0.01,0.1 seed=1,2
  # Without exclude_keys: batch_size=32,learning_rate=0.01,seed=1/
  # With exclude_keys: batch_size=32,learning_rate=0.01/seed=1/
  ```

### Configuration Inheritance
- [ ] Support for base configurations that can be extended
  ```yaml
  # configs/base/standard_preprocessing.yaml
  defaults:
    - _self_
  
  preprocessing:
    steps:
      - type: dropna
        params:
          subset: ["Metadata_compound"]
      - type: remove_nan_features
        params:
          threshold: 0.95
  
  average_precision:
    params:
      pos_sameby: ["Metadata_compound"]
      pos_diffby: []
      neg_sameby: []
      neg_diffby: ["Metadata_compound"]
  
  # configs/experiment_dose_response.yaml
  defaults:
    - base/standard_preprocessing  # Inherit all preprocessing steps
    - _self_
  
  # Add experiment-specific steps
  preprocessing:
    steps:
      - type: filter  # This gets ADDED to inherited steps
        params:
          query: "Metadata_dose > 0.1"
  
  # Override specific inherited values
  average_precision:
    params:
      pos_sameby: ["Metadata_compound", "Metadata_dose"]  # Override inherited value
  ```
  **Real-world example**: You have 10 experiments using the same preprocessing but different filters. Instead of copying the same 50 lines of preprocessing config, you inherit from a base and only specify what's different.

### Other Enhancements
- [ ] Custom OmegaConf resolvers for complex path resolution
  ```python
  # In copairs_runner.py:
  def resolve_data_path(path: str, *, _parent_) -> str:
      """Custom resolver to find data files with fallbacks"""
      # Check multiple locations in order
      for base in [os.getcwd(), os.environ.get("COPAIRS_DATA", ""), "~/copairs_data"]:
          full_path = os.path.join(base, path)
          if os.path.exists(full_path):
              return full_path
      raise ValueError(f"Data file not found: {path}")
  
  OmegaConf.register_new_resolver("data_path", resolve_data_path)
  
  # Then in config:
  input:
    path: "${data_path:plates/2024/plate001.parquet}"
  ```

- [ ] Structured configs for better validation and IDE support
  ```python
  # Instead of dict-based configs that can have typos
  from dataclasses import dataclass
  from typing import Optional, List
  
  @dataclass
  class PreprocessingFilter:
      query: str
      validate: bool = True  # Would validate query syntax
  
  # This would catch typos at config load time, not runtime
  # IDE would autocomplete field names
  ```

- [ ] Native multirun support for parameter sweeps
  ```bash
  # Current - must run multiple times manually
  python copairs_runner.py preprocessing.filter.params.query="dose > 0.1"
  python copairs_runner.py preprocessing.filter.params.query="dose > 0.5"
  python copairs_runner.py preprocessing.filter.params.query="dose > 1.0"
  
  # Proposed - single command
  python copairs_runner.py --multirun \
    preprocessing.filter.params.query='dose > 0.1','dose > 0.5','dose > 1.0' \
    mean_average_precision.params.null_size=10000,50000,100000
  # Would run 3 x 3 = 9 combinations automatically
  ```

- [ ] Better integration with Hydra's working directory utilities
  ```python
  # Current - paths can be confusing
  # Proposed - always resolve paths correctly regardless of working directory
  from hydra.utils import to_absolute_path, get_original_cwd
  
  # In config:
  preprocessing:
    steps:
      - type: merge_metadata
        params:
          # This would work whether hydra.job.chdir is true or false
          path: "${hydra:runtime.cwd}/metadata/compounds.csv"
  ```

## Error Handling & Robustness
- [ ] Graceful handling of memory errors for large datasets
  ```python
  # Current - crashes with OOM
  # Proposed - catch and provide helpful message
  try:
      df = pd.read_parquet(path)
  except MemoryError:
      logger.error(f"Out of memory loading {path} ({size_mb}MB)")
      logger.error("Try: 1) Use lazy loading (use_lazy_filter: true)")
      logger.error("     2) Filter columns (columns: [...])")
      logger.error("     3) Use a machine with more RAM")
      sys.exit(1)
  ```

- [ ] Resume capability for interrupted runs
  ```yaml
  # If analysis is interrupted after AP but before mAP
  # Currently: must restart from beginning
  # Proposed: detect existing outputs and resume
  
  output:
    resume: true  # Skip completed steps
  
  # Log output:
  # [INFO] Found existing activity_ap_scores.csv, skipping average_precision step
  # [INFO] Resuming from mean_average_precision step
  ```

- [ ] Validation of output files before marking complete
  ```python
  # Ensure outputs are valid before considering step complete
  # - CSV files have expected columns
  # - No empty files
  # - PNG files are valid images
  ```

- [ ] Better error messages with suggested fixes
  ```python
  # Current: KeyError: 'Metadata_compound'
  # Proposed:
  ValueError: Column 'Metadata_compound' not found in data.
  Available metadata columns: ['Metadata_Plate', 'Metadata_Well', 'Metadata_Site']
  
  Suggestions:
  1. Check your column name spelling
  2. If using lazy loading, ensure column is in 'columns' list
  3. Run with --cfg job to see full configuration
  ```

## Completed
- ✅ Basic Hydra integration
- ✅ Support for URLs and S3 paths
- ✅ Lazy loading for large parquet files
- ✅ Comprehensive preprocessing pipeline
- ✅ Fixed output pattern (3 files per analysis)

## Design Principles

When implementing new features:
1. Maintain single-file simplicity where possible
2. Follow monorepo standards (uv, ruff, pytest)
3. Preserve backward compatibility
4. Document all new preprocessing steps
5. Add examples for new features

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on implementing items from this roadmap.