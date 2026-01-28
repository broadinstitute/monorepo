# Roadmap

Future enhancements for copairs_runner.

## Testing

- [ ] Integration test exercising the full pipeline with sample data

## Error Handling

- [ ] Better error messages with suggestions

  ```python
  # Current: KeyError: 'Metadata_compound'
  # Proposed:
  ValueError: Column 'Metadata_compound' not found.
  Available metadata columns: ['Metadata_Plate', 'Metadata_Well', 'Metadata_Site']

  Suggestions:
  1. Check column name spelling
  2. If using lazy loading, ensure column is in 'columns' list
  ```

- [ ] Graceful memory error handling

  ```python
  try:
      df = pd.read_parquet(path)
  except MemoryError:
      logger.error(f"Out of memory loading {path}")
      logger.error("Try: use_lazy_filter: true, or filter columns")
      sys.exit(1)
  ```

## Upstream Dependencies

- [ ] Exact p-value support (pending [copairs PR](https://github.com/cytomining/copairs/pull/114))
  - When merged, expose `exact_pvalue` parameter in `mean_average_precision.params`

## Completed

- Basic Hydra integration
- URLs and S3 path support
- Lazy loading for large parquet files
- Preprocessing pipeline
- Fixed 3-file output pattern
- Parquet output format option
