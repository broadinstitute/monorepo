# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "duckdb>=1.1.3",
#     "cupy",
#     "dask",
#     "numpy",
#     "pyarrow>=16.1.0",
# ]
# ///

"""Generate a table with the most correlated and anticorrelated perturbation pairs."""

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")

with app.setup:
    from pathlib import Path
    from time import perf_counter

    import cupy as cp
    import dask.array as da
    import duckdb
    import marimo as mo  # noqa: F401
    import numpy as np
    import pyarrow as pa
    from nb01_load_data import (
        JCP_COL,
        JCP_SHORT,
        REPLICABILITY_COLS,
        STD_OUTNAME,
        _write_parquet,
        add_external_sites,
        add_replicability,
        add_sample_images,
        build_mappers,
        compute_consensus,
        get_compound_mappers,
        get_range,
        get_synonym_mapper,
        load_profiles,
        write_metadata,
    )

    DATASETS_NVALS = {
        "crispr (25)": ("crispr", 25),
        "orf (25)": ("orf", 25),
        "compound (10)": ("compound", 10),
    }
    DEFAULT_OUTPUT_DIR = Path("./databases")


@app.function
def pairwise_cosine_sim(x: da.Array, y: da.Array) -> da.Array:
    """Compute pairwise cosine similarity between two sets of vectors."""
    x_norm = x / da.linalg.norm(x, axis=1)[:, da.newaxis]
    y_norm = y / da.linalg.norm(y, axis=1)[:, da.newaxis]
    return da.matmul(x_norm, y_norm.T)


@app.function
def get_bottom_top_indices(
    mat: da.Array, n: int, skip_first: bool = False
) -> tuple[np.ndarray, np.ndarray]:
    """Get the top n and bottom n indices from a matrix for each row."""
    top = da.argtopk(mat, n + skip_first)[:, skip_first:]
    bottom = da.argtopk(mat, -n)
    xs = (
        da.matmul(da.arange(len(mat))[:, da.newaxis], da.ones((1, n * 2), dtype=int))
        .flatten()
        .compute()
    )
    ys = da.hstack((top, bottom)).flatten().compute()
    return xs, ys


@app.function
def generate_matches(
    dset: str, n_vals: int, output_dir: Path = DEFAULT_OUTPUT_DIR
) -> duckdb.DuckDBPyRelation:
    """Generate match tables for a single JUMP dataset."""
    assert cp.cuda.get_current_stream().done, "GPU not available"

    jcp_col = JCP_COL
    jcp_short = JCP_SHORT
    std_outname = STD_OUTNAME
    replicability_cols = REPLICABILITY_COLS
    match_col = "Match"
    match_jcp_col = f"Match {jcp_short}"
    img_col = f"{std_outname} example image"
    match_img_col = f"{match_col} example image"
    dist_col = "Perturbation-Match Similarity"
    ext_links_col = f"{match_col} resources"

    # Load and compute consensus
    df = load_profiles(dset)
    med, _ = compute_consensus(df, jcp_col)

    # Extract numpy arrays for numerical computation
    feat_cols = [c for c in med.columns if not c.startswith("Metadata_") and c != jcp_col]
    _col_list = ", ".join(f'"{c}"' for c in feat_cols)
    median_np = np.array(
        duckdb.sql(f"SELECT {_col_list} FROM med").fetchall(),
        dtype=np.float64,
    )

    t = perf_counter()
    vals = da.array(median_np)
    if dset != "compound":
        vals = vals.map_blocks(cp.asarray)

    # Cosine similarity
    cosine_sim = pairwise_cosine_sim(vals, vals)
    if dset != "compound":
        cosine_sim = cosine_sim.map_blocks(cp.asnumpy)

    cosine_sim_computed = cosine_sim.compute()
    xs, ys = get_bottom_top_indices(cosine_sim, n_vals, skip_first=True)

    jcp_ids = np.array(
        [r[0] for r in duckdb.sql(f'SELECT "{jcp_col}" FROM med').fetchall()],
        dtype="<U15",
    )

    # Build matches relation from numpy arrays
    _jcp_data = pa.table({
        jcp_short: np.repeat(jcp_ids, n_vals * 2),
        match_jcp_col: jcp_ids[ys].astype("<U15"),
        dist_col: cosine_sim_computed[xs, ys].astype(np.float64),
    })
    jcp_df = duckdb.sql("SELECT * FROM _jcp_data")

    # Add images for queries and matches
    df_meta = duckdb.sql("SELECT COLUMNS('Metadata.*') FROM df")
    rng = get_range(dset)

    _side_a = add_sample_images(
        jcp_df, df_meta, rng, img_col,
        left_col=jcp_short, right_col=jcp_col,
    )
    _side_b = add_sample_images(
        jcp_df, df_meta, rng, match_img_col,
        left_col=match_jcp_col, right_col=jcp_col,
    )

    jcp_df = duckdb.sql(f"""
        SELECT jcp_df.*, _side_a."{img_col}"
        FROM jcp_df
        JOIN (
            SELECT "{jcp_short}", "{match_jcp_col}", "{img_col}" FROM _side_a
        ) AS _side_a
        ON jcp_df."{jcp_short}" = _side_a."{jcp_short}"
        AND jcp_df."{match_jcp_col}" = _side_a."{match_jcp_col}"
    """)
    jcp_df = duckdb.sql(f"""
        SELECT jcp_df.*, _side_b."{match_img_col}"
        FROM jcp_df
        JOIN (
            SELECT "{jcp_short}", "{match_jcp_col}", "{match_img_col}" FROM _side_b
        ) AS _side_b
        ON jcp_df."{jcp_short}" = _side_b."{jcp_short}"
        AND jcp_df."{match_jcp_col}" = _side_b."{match_jcp_col}"
    """)

    # Map names
    jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl = build_mappers(
        df, jcp_col, dset
    )

    # Register mappers for name translation
    for _name, _mapper in [
        ("_match_std_map", jcp_to_std),
        ("_match_entrez_map", jcp_to_entrez),
        ("_match_syn_map", get_synonym_mapper()),
    ]:
        duckdb.execute(
            f"CREATE OR REPLACE TEMP TABLE {_name} AS "
            "SELECT UNNEST($1::VARCHAR[]) AS _key, UNNEST($2::VARCHAR[]) AS _val",
            [list(_mapper.keys()), list(str(v) for v in _mapper.values())],
        )

    _mapped_arrow = duckdb.sql(f"""
        SELECT jcp_df.*,
            COALESCE(s1._val, '') AS "{std_outname}",
            COALESCE(s2._val, '') AS "{match_col}",
            COALESCE(syn._val, COALESCE(ent._val, '')) AS "Synonyms"
        FROM jcp_df
        LEFT JOIN _match_std_map s1 ON CAST(jcp_df."{jcp_short}" AS VARCHAR) = s1._key
        LEFT JOIN _match_std_map s2 ON CAST(jcp_df."{match_jcp_col}" AS VARCHAR) = s2._key
        LEFT JOIN _match_entrez_map ent ON CAST(jcp_df."{jcp_short}" AS VARCHAR) = ent._key
        LEFT JOIN _match_syn_map syn ON CAST(ent._val AS VARCHAR) = syn._key
    """).arrow()
    for _name in ("_match_std_map", "_match_entrez_map", "_match_syn_map"):
        duckdb.execute(f"DROP TABLE IF EXISTS {_name}")
    jcp_df = duckdb.sql("SELECT * FROM _mapped_arrow")

    # Replicability for query and match
    jcp_df = add_replicability(
        jcp_df, left_on=jcp_short, right_on=jcp_col,
        cols_to_add=replicability_cols,
    )
    jcp_df = add_replicability(
        jcp_df, left_on=match_jcp_col, right_on=jcp_col,
        suffix=" Match", cols_to_add=replicability_cols,
    )

    # External links for matches
    if dset != "compound":
        key_source_mapper = [
            ("entrez", match_jcp_col, jcp_to_entrez),
            ("omim", match_col, std_to_omim),
            (
                "genecards",
                match_col,
                dict(zip(jcp_to_std.values(), jcp_to_std.values())),
            ),
            ("ensembl", match_col, std_to_ensembl),
        ]
    else:
        key_source_mapper = [(k, jcp_short, v) for k, v in get_compound_mappers()]

    jcp_df = add_external_sites(jcp_df, ext_links_col, key_source_mapper)

    # Build final column order
    repl_cols = ", ".join(
        f'"{v}{suffix}"'
        for suffix in ("", " Match")
        for v in replicability_cols.values()
    )

    jcp_df = duckdb.sql(f"""
        SELECT
            "{std_outname}",
            "{match_col}",
            "{img_col}",
            "{match_img_col}",
            ROUND(CAST("{dist_col}" AS DOUBLE), 3) AS "{dist_col}",
            "{ext_links_col}",
            "Synonyms",
            "{jcp_short}",
            "{match_jcp_col}",
            {repl_cols}
        FROM jcp_df
    """)

    # Write outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_parquet(jcp_df, output_dir / f"{dset}.parquet")
    write_metadata(dset, "matches", jcp_df.columns)

    # Full cosine similarity matrix
    jcp_list = [r[0] for r in duckdb.sql(f'SELECT "{jcp_col}" FROM med').fetchall()]
    _cos_tbl = pa.table({
        name: cosine_sim_computed[:, i].astype(np.float64)
        for i, name in enumerate(jcp_list)
    })
    _write_parquet(
        duckdb.sql("SELECT * FROM _cos_tbl"),
        output_dir / f"{dset}_cosinesim_full.parquet",
    )

    elapsed = perf_counter() - t
    print(f"Matched pairwise {dset} in {elapsed:.1f} seconds")

    return jcp_df


# --- Interactive UI ---


@app.cell
def _(mo):
    mo.md(
        "# Pairwise Similarity Matches\n"
        "Compute GPU-accelerated cosine similarity between perturbation profiles."
    )
    return ()


@app.cell
def _(mo):
    match_selector = mo.ui.dropdown(
        options=list(DATASETS_NVALS.keys()),
        value="crispr (25)",
        label="Dataset (top-N matches)",
    )
    match_selector
    return (match_selector,)


@app.cell
def _(mo):
    match_run = mo.ui.run_button(label="Compute similarity")
    mo.md("**Warning:** This requires a GPU and significant RAM.")
    match_run
    return (match_run,)


@app.cell
def _(match_run, match_selector, mo):
    mo.stop(not match_run.value)
    _dset, _n_vals = DATASETS_NVALS[match_selector.value]
    _result = generate_matches(_dset, _n_vals)
    _count = duckdb.sql("SELECT COUNT(*) FROM _result").fetchone()[0]
    mo.md(f"**Done** — {_count} rows written to `databases/{_dset}.parquet`")
    return ()


@app.cell
def _(mo):
    mo.stop(mo.app_meta().mode != "run")
    for _dset, _n_vals in (("crispr", 25), ("orf", 25), ("compound", 10)):
        print(f"Computing matches for {_dset}...")
        generate_matches(_dset, _n_vals)
    print("All matches complete.")
    return ()


if __name__ == "__main__":
    app.run()
