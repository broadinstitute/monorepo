# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

copairs_runner is a configurable Python script for running copairs analyses on cell painting data. It's part of a larger monorepo focused on morphological profiling and drug discovery through cellular imaging.

**For usage, configuration, and examples, see [README.md](README.md).**

## Development Context

### Key Development Commands
```bash
# Lint and format (monorepo standard)
uvx ruff check src/copairs_runner/copairs_runner.py --fix
uvx ruff format src/copairs_runner/copairs_runner.py

# Run tests (when implemented)
pytest tests/

# Test changes
export COPAIRS_DATA=. COPAIRS_OUTPUT=.
bash run_examples.sh
```

## Architecture Decisions

### Package Design
- **src/copairs_runner/copairs_runner.py** maintains single-file logic with inline dependencies (PEP 723)
- Now packaged for easy installation via `uv add`
- Supports both standalone script execution and installed package usage
- Hydra-based configuration for flexibility without code changes

### Key Design Patterns
1. **Fixed Output Pattern**: Always saves 3 files per analysis (ap_scores, map_results, map_plot)
2. **Dictionary-based Results**: `save_results()` takes a dict for easy extension
3. **Preprocessing Pipeline**: Each step is a method `_preprocess_{type}` for consistency
4. **Path Resolution**: Handles local files, URLs, and S3 uniformly via `resolve_path()`
5. **Nested Subdirectory Pattern**: For dependent workflows (e.g., LINCS), each analysis uses its own subdirectory within a shared parent to prevent Hydra runtime file overwrites while maintaining predictable relative paths

## Monorepo Context

This project follows monorepo standards:
- **uv** for package management (not Poetry)
- **ruff** for formatting/linting (run via `uvx`)
- **pytest** for testing (target >90% coverage)
- **numpy** documentation style
- Conventional commits

### Current Limitations
- No test suite yet (priority for future work)
- Single-file design may need refactoring if complexity grows
- Fixed 3-file output pattern (by design for simplicity)

## Implementation Guidelines

### Adding New Preprocessing Steps
```python
def _preprocess_<step_name>(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """One-line description.
    
    Must follow this exact signature. Access params via dict lookup.
    Log the operation with: logger.info(f"Message: {result}")
    """
    # Implementation
    return df
```

Then update the docstring in `preprocess_data()` to document the new step.

### Important Implementation Details

1. **Lazy Loading vs Preprocessing**:
   - `input.filter_query` uses SQL syntax (polars) - happens BEFORE loading
   - `preprocessing.filter` uses pandas query syntax - happens AFTER loading
   - This distinction is critical for large datasets

2. **Error Handling**:
   - Config validation happens in `_validate_config()` 
   - Missing required params raise `ValueError` with clear messages
   - Use `params.get("key", default)` for optional parameters

3. **Logging Patterns**:
   - Always log row counts after filtering operations
   - Log first 5 columns when loading data for verification
   - Use `logger.info()` not print()

### Testing Approach (when implemented)
- Unit test each preprocessing step independently
- Integration test full pipeline with small test data
- Test config validation edge cases
- Mock external data sources (URLs, S3)

## Key Gotchas

1. **Environment Variables**: Must be set before running if configs use `${oc.env:VAR}`
2. **Memory Usage**: Use lazy loading for large parquet files to avoid OOM
3. **Path Resolution**: All paths are relative to where you run the script, not the config file location
4. **Shared Directory Structure**: When creating dependent analyses (where one reads another's output), always use nested subdirectories (e.g., `shared/activity/` and `shared/consistency/`) to prevent Hydra runtime files from being overwritten between runs