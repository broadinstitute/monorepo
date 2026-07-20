# Contributing to copairs_runner

## Preprocessing Steps

The preprocessing pipeline intentionally provides a minimal DSL to avoid recreating pandas/SQL in YAML. Before adding new steps, consider whether users should handle the transformation externally.

**Important context**: Copairs analysis typically happens at the end of a morphological profiling pipeline. By this stage, your data should already be:

- Quality-controlled and normalized
- Aggregated to appropriate levels
- Filtered for relevant samples
- Properly annotated with metadata

If you find yourself needing extensive preprocessing here, it likely indicates issues with your upstream pipeline.

### Alternatives to New Steps

1. **Lazy filtering** - For large parquet files, use polars' SQL syntax before loading:

   ```yaml
   data:
     use_lazy_filter: true
     filter_query: "Metadata_PlateType == 'TARGET2'"
   ```

2. **External preprocessing** - Complex transformations belong in Python/SQL scripts, not YAML configs

3. **Composition** - Combine existing steps rather than creating specialized ones

### When to Add a Step

Add a step only if it:

- Integrates with copairs-specific functionality (e.g., `apply_assign_reference`)
- Handles last-mile transformations specific to copairs analysis
- Requires runner context (resolved paths, metadata patterns)
- Has been requested by multiple users

Remember: needing complex preprocessing at this stage often indicates upstream processing gaps.

### Implementation

```python
def _preprocess_<step_name>(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """One-line description."""
    # Implementation
    logger.info(f"Log what happened")
    return df
```

Update the `preprocess_data()` docstring with parameters and add a usage example.

### Design Constraints

- Keep implementations under ~10 lines
- Single responsibility per step
- Clear parameter validation
- Informative error messages

The goal is providing just enough convenience without creating a parallel data manipulation framework. Most preprocessing should happen before data reaches this runner.
