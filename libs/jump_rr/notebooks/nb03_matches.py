# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "polars",
#     "jump-rr",
#     "cupy",
#     "dask",
#     "numpy",
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
    import numpy as np
    import polars as pl
    import polars.selectors as cs
    from nb01_load_data import (
        JCP_COL,
        JCP_SHORT,
        REPLICABILITY_COLS,
        STD_OUTNAME,
        build_mappers,
        compute_consensus,
        load_profiles,
    )

    from jump_rr.consensus import add_sample_images, get_range
    from jump_rr.formatters import add_external_sites
    from jump_rr.index_selection import get_bottom_top_indices
    from jump_rr.mappers import get_compound_mappers, get_synonym_mapper
    from jump_rr.metadata import write_metadata
    from jump_rr.replicability import add_replicability

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
def generate_matches(
    dset: str, n_vals: int, output_dir: Path = DEFAULT_OUTPUT_DIR
) -> pl.DataFrame:
    """
    Generate match tables for a single JUMP dataset.

    Computes GPU-accelerated pairwise cosine similarity, selects top/bottom
    matches, enriches with metadata, and writes parquet outputs.
    """
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
    median_np = med.select(cs.by_dtype(pl.Float32)).to_numpy()

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

    jcp_ids = med[jcp_col].to_numpy().astype("<U15")

    # Build matches dataframe
    jcp_df = pl.DataFrame(
        {
            jcp_short: np.repeat(jcp_ids, n_vals * 2),
            match_jcp_col: jcp_ids[ys].astype("<U15"),
            dist_col: cosine_sim_computed[xs, ys],
        }
    )

    # Add images for queries and matches
    df_meta = df.select("^Metadata.*$")
    rng = get_range(dset)
    side_a = add_sample_images(
        jcp_df,
        df_meta,
        rng,
        img_col,
        left_col=jcp_short,
        right_col=jcp_col,
    )
    side_b = add_sample_images(
        jcp_df,
        df_meta,
        rng,
        match_img_col,
        left_col=match_jcp_col,
        right_col=jcp_col,
    )
    jcp_cols = (jcp_short, match_jcp_col)
    jcp_df = jcp_df.join(side_a.select(pl.col((*jcp_cols, img_col))), on=jcp_cols)
    jcp_df = jcp_df.join(side_b.select(pl.col((*jcp_cols, match_img_col))), on=jcp_cols)

    # Map names
    jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl = build_mappers(
        df, jcp_col, dset
    )

    jcp_df = jcp_df.with_columns(
        pl.col(jcp_short).replace(jcp_to_std).alias(std_outname),
        pl.col(match_jcp_col).replace(jcp_to_std).alias(match_col),
        pl.col(jcp_short)
        .replace(jcp_to_entrez)
        .replace(get_synonym_mapper())
        .alias("Synonyms"),
    )

    order = [
        std_outname,
        match_col,
        img_col,
        match_img_col,
        dist_col,
        "Synonyms",
        jcp_short,
        match_jcp_col,
    ]

    # Replicability for query and match
    jcp_df = add_replicability(
        jcp_df,
        left_on=jcp_short,
        right_on=jcp_col,
        cols_to_add=replicability_cols,
    )
    jcp_df = add_replicability(
        jcp_df,
        left_on=match_jcp_col,
        right_on=jcp_col,
        suffix=" Match",
        cols_to_add=replicability_cols,
    )

    # External links — matches use match_col/match_jcp_col, not STD_OUTNAME
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
    order.insert(5, ext_links_col)

    order = (
        *order,
        *[
            f"{v}{suffix}"
            for suffix in ("", " Match")
            for v in replicability_cols.values()
        ],
    )

    jcp_df = jcp_df.with_columns(
        pl.col(dist_col).cast(pl.Float64).round(3).alias(dist_col)
    )
    matches_translated = jcp_df.select(order)

    # Write outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    matches_translated.write_parquet(output_dir / f"{dset}.parquet", compression="zstd")
    write_metadata(dset, "matches", order)

    # Full cosine similarity matrix
    pl.DataFrame(
        data=cosine_sim_computed,
        schema=med.get_column(jcp_col).to_list(),
    ).write_parquet(output_dir / f"{dset}_cosinesim_full.parquet")

    elapsed = perf_counter() - t
    print(f"Matched pairwise {dset} in {elapsed:.1f} seconds")

    return matches_translated


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
    mo.md(f"**Done** — {len(_result)} rows written to `databases/{_dset}.parquet`")
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
