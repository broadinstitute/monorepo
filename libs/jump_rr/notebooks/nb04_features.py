# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "polars",
#     "jump-rr",
#     "dask",
#     "duckdb",
#     "numpy",
# ]
# ///

"""Generate a table with the most important feature values for each perturbation."""

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")

with app.setup:
    from pathlib import Path
    from time import perf_counter

    import dask.array as da
    import duckdb
    import numpy as np
    import polars as pl
    from nb01_load_data import (
        JCP_COL,
        JCP_SHORT,
        REPLICABILITY_COLS,
        STD_OUTNAME,
        build_key_source_mapper,
        build_mappers,
        compute_consensus,
        load_profiles,
    )

    from jump_rr.consensus import add_sample_images, get_range
    from jump_rr.formatters import add_external_sites
    from jump_rr.index_selection import (
        get_ranks_per_feature,
        get_ranks_per_perturbation,
    )
    from jump_rr.mappers import get_synonym_mapper
    from jump_rr.metadata import write_metadata
    from jump_rr.parse_features import get_feature_groups
    from jump_rr.replicability import add_replicability
    from jump_rr.significance import add_pert_type, statistics_from_profile

    DATASETS_NVALS = {
        "crispr (30, 50)": ("crispr_interpretable", 30, 50),
        "orf (30, 50)": ("orf_interpretable", 30, 50),
        "compound (10, 50)": ("compound_interpretable", 10, 50),
    }
    FEAT_DECOMPOSITION = ("Compartment", "Feature", "Channel", "Suffix")
    NDECIMALS = 5
    UNRANKED_SENTINEL = 99999
    DEFAULT_OUTPUT_DIR = Path("./databases")


@app.function
def generate_features(
    dset: str,
    n_feat_per_compound: int,
    n_compounds_per_feat: int,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> pl.DataFrame:
    """
    Generate feature significance rankings for a single JUMP dataset.

    Computes t-test statistics, Cohen's d, selects top features per perturbation
    and top perturbations per feature, writes parquet outputs.
    """
    jcp_col = JCP_COL
    jcp_short = JCP_SHORT
    std_outname = STD_OUTNAME
    replicability_cols = REPLICABILITY_COLS
    ext_links_col = "Resources"
    img_col = f"{std_outname} example image"
    val_col = "Median"
    stat_col = "Feature significance"
    rank_feat_col = "Feature Rank"
    rank_gene_col = "Perturbation Rank"
    effect_col = "Cohen's d"
    abs_effect_col = "|Cohen's d|"

    t0 = perf_counter()
    dset_type = dset.removesuffix("_interpretable")

    # Load and prepare
    precor = load_profiles(dset)
    precor = add_pert_type(precor, dataset=dset_type)
    featstat, cohens_d = statistics_from_profile(precor)

    # Consensus (excluding negcons)
    med, _ = compute_consensus(
        precor.filter(pl.col("Metadata_pert_type") != "negcon"),
        jcp_col,
    )
    filtered_med = med.sort(by=jcp_col)
    median_vals = filtered_med.select(pl.exclude("^Metadata.*$")).to_numpy()

    # Per-compound: top features by lowest p-value
    lowest_x = get_ranks_per_perturbation(featstat, n_feat_per_compound)
    index_lowest_rank_x = da.vstack(  # noqa: F841 (referenced by DuckDB SQL below)
        (
            da.indices((len(lowest_x), n_feat_per_compound)).reshape((2, -1)),
            lowest_x.flatten(),
        ),
    ).compute()

    # Per-feature: top compounds by largest |Cohen's d|
    lowest_y = get_ranks_per_feature(da.abs(cohens_d), n_compounds_per_feat)
    index_lowest_rank_y = da.vstack(  # noqa: F841 (referenced by DuckDB SQL below)
        (
            da.indices((lowest_y.shape[1], n_compounds_per_feat)).reshape((2, -1)),
            lowest_y.T.flatten(),
        ),
    ).compute()

    # Unify ranks via DuckDB
    with duckdb.connect() as con:
        tbl = con.execute(
            "SELECT x,y,"
            "any_value(rankf) AS rankf,"
            "any_value(rankg) AS rankg"
            " FROM (SELECT * FROM"
            " (SELECT column0 as x,column1 as rankf,column2 as y"
            " FROM index_lowest_rank_x)"
            " UNION ALL BY NAME"
            " (SELECT column0 AS y,column1 AS rankg, column2 AS x"
            " FROM index_lowest_rank_y))"
            " GROUP By x,y"
            " ORDER BY y,x,rankf"
        )
        items = tbl.fetchnumpy()
    xs = items["x"]
    ys = items["y"]
    rankf = items["rankf"].filled(UNRANKED_SENTINEL)
    rankg = items["rankg"].filled(UNRANKED_SENTINEL)

    # Decompose feature names
    decomposed_feats = get_feature_groups(
        tuple(filtered_med.select(pl.exclude("^Metadata.*$")).columns),
        FEAT_DECOMPOSITION,
    )
    featstat_computed = da.around(featstat, NDECIMALS).compute()
    cohens_d_full = cohens_d.compute()
    cohens_d_computed = np.around(cohens_d_full, 3)

    # Build dataframe
    df = pl.DataFrame(
        {
            **{
                k: v
                for k, v in zip(
                    decomposed_feats.columns, decomposed_feats.to_numpy()[ys].T
                )
            },
            stat_col: featstat_computed[xs, ys],
            effect_col: cohens_d_computed[xs, ys],
            abs_effect_col: abs(cohens_d_computed[xs, ys]),
            val_col: np.around(median_vals[xs, ys].astype(np.float64), 3),
            jcp_short: filtered_med[jcp_col][xs],
            rank_gene_col: rankg,
            rank_feat_col: rankf,
        }
    )

    # Add images
    df_meta = precor.select("^Metadata.*$")
    df = add_sample_images(
        df,
        df_meta,
        get_range(dset_type),
        img_col,
        left_col=jcp_short,
        right_col=jcp_col,
    )

    # Map names
    jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl = build_mappers(
        precor, jcp_col, dset_type
    )

    order = [
        *decomposed_feats.columns,
        stat_col,
        effect_col,
        abs_effect_col,
        std_outname,
        img_col,
        val_col,
        rank_gene_col,
        rank_feat_col,
        jcp_short,
        "Synonyms",
    ]

    # Replicability
    df = add_replicability(
        df,
        left_on=jcp_short,
        right_on=jcp_col,
        cols_to_add=replicability_cols,
    )
    for col in replicability_cols.values():
        order.insert(-6, col)

    # Aliases and external links
    jcp_translated = df.with_columns(
        pl.col(jcp_short).replace(jcp_to_std).alias(std_outname),
        pl.col(jcp_short)
        .replace(jcp_to_entrez)
        .replace(get_synonym_mapper())
        .alias("Synonyms"),
    )

    key_source_mapper = build_key_source_mapper(
        dset_type, jcp_short, jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl
    )
    w_external_sites = add_external_sites(
        jcp_translated, ext_links_col, key_source_mapper
    )
    order.insert(-1, ext_links_col)

    sorted_df = w_external_sites.select(order)

    # Write outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    sorted_df.write_parquet(output_dir / f"{dset}_features.parquet", compression="zstd")
    write_metadata(dset_type, "feature", sorted_df.columns)

    # Full matrices
    feature_cols = filtered_med.select(pl.exclude("^Metadata.*$")).columns
    jcp_col_data = filtered_med.get_column(jcp_col)
    for data, suffix in [
        (featstat_computed, "significance_full"),
        (cohens_d_full, "cohens_d_full"),
    ]:
        matrix_df = pl.DataFrame(data=data, schema=feature_cols).with_columns(
            jcp_col_data
        )
        matrix_df.write_parquet(output_dir / f"{dset_type}_{suffix}.parquet")

    elapsed = perf_counter() - t0
    print(f"{dset} features processed in {elapsed:.2f}s")

    return sorted_df


# --- Interactive UI ---


@app.cell
def _(mo):
    mo.md(
        "# Feature Significance Ranking\n"
        "Identify the most significant morphological features per perturbation."
    )
    return ()


@app.cell
def _(mo):
    feat_selector = mo.ui.dropdown(
        options=list(DATASETS_NVALS.keys()),
        value="crispr (30, 50)",
        label="Dataset (features/compound, compounds/feature)",
    )
    feat_selector
    return (feat_selector,)


@app.cell
def _(mo):
    feat_run = mo.ui.run_button(label="Compute features")
    feat_run
    return (feat_run,)


@app.cell
def _(feat_run, feat_selector, mo):
    mo.stop(not feat_run.value)
    _dset, _n_feat, _n_comp = DATASETS_NVALS[feat_selector.value]
    _result = generate_features(_dset, _n_feat, _n_comp)
    mo.md(
        f"**Done** — {len(_result)} rows written to `databases/{_dset}_features.parquet`"
    )
    return ()


@app.cell
def _(mo):
    mo.stop(mo.app_meta().mode != "run")
    for _dset, _n_feat, _n_comp in (
        ("crispr_interpretable", 30, 50),
        ("orf_interpretable", 30, 50),
        ("compound_interpretable", 10, 50),
    ):
        print(f"Computing features for {_dset}...")
        generate_features(_dset, _n_feat, _n_comp)
    print("All features complete.")
    return ()


if __name__ == "__main__":
    app.run()
