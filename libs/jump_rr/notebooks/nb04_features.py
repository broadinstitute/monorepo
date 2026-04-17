# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "duckdb>=1.1.3",
#     "dask",
#     "numpy",
#     "scipy",
#     "statsmodels",
#     "broad-babel>=0.1.27",
#     "pyarrow>=16.1.0",
# ]
# ///

"""Generate a table with the most important feature values for each perturbation."""

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")

with app.setup:
    import re
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from time import perf_counter

    import dask.array as da
    import duckdb
    import marimo as mo  # noqa: F401
    import numpy as np
    import pyarrow as pa
    from broad_babel.query import get_mapper as babel_get_mapper
    from nb01_load_data import (
        JCP_COL,
        JCP_SHORT,
        REPLICABILITY_COLS,
        STD_OUTNAME,
        _write_parquet,
        add_external_sites,
        add_replicability,
        add_sample_images,
        build_key_source_mapper,
        build_mappers,
        compute_consensus,
        get_range,
        get_synonym_mapper,
        load_profiles,
        write_metadata,
    )
    from scipy.stats import t
    from statsmodels.stats.multitest import multipletests

    np.seterr(divide="ignore")

    DATASETS_NVALS = {
        "crispr (30, 50)": ("crispr_interpretable", 30, 50),
        "orf (30, 50)": ("orf_interpretable", 30, 50),
        "compound (10, 50)": ("compound_interpretable", 10, 50),
    }
    FEAT_DECOMPOSITION = ("Compartment", "Feature", "Channel", "Suffix")
    NDECIMALS = 5
    UNRANKED_SENTINEL = 99999
    DEFAULT_OUTPUT_DIR = Path("./databases")


# --- significance ---


@app.function
def add_pert_type(
    profiles: duckdb.DuckDBPyRelation, dataset: str, poscons: bool = False
) -> duckdb.DuckDBPyRelation:
    """Add metadata with perturbation type from the JCP2022 identifier."""
    pert_type = "Metadata_pert_type"
    if pert_type not in profiles.columns:
        jcp_to_pert_type = babel_get_mapper(
            dataset,
            input_column="plate_type",
            output_columns="JCP2022,pert_type",
        )
        duckdb.execute(
            "CREATE OR REPLACE TEMP TABLE _pert_type_map AS "
            "SELECT UNNEST($1::VARCHAR[]) AS _key, UNNEST($2::VARCHAR[]) AS _val",
            [list(jcp_to_pert_type.keys()), list(jcp_to_pert_type.values())],
        )
        profiles = duckdb.sql(f"""
            SELECT profiles.*, COALESCE(m._val, 'null') AS "{pert_type}"
            FROM profiles
            LEFT JOIN _pert_type_map m
            ON CAST(profiles."Metadata_JCP2022" AS VARCHAR) = m._key
        """)
        duckdb.execute("DROP TABLE IF EXISTS _pert_type_map")

    profiles = duckdb.sql(f"""
        SELECT * FROM profiles WHERE "{pert_type}" != 'null'
    """)
    if not poscons:
        profiles = duckdb.sql(f"""
            SELECT * REPLACE (
                CASE WHEN "{pert_type}" != 'negcon' THEN 'trt' ELSE 'negcon' END
                AS "{pert_type}"
            ) FROM profiles
        """)
    return profiles


@app.function
def statistics_from_profile(
    profile: duckdb.DuckDBPyRelation,
) -> tuple[da.Array, da.Array]:
    """Compute p-values and Cohen's d for every feature in a given profile."""
    # Get metrics for t-test via DuckDB
    df = profile  # noqa: F841
    plates_trt = duckdb.sql(  # noqa: F841
        "SELECT Metadata_JCP2022,list(DISTINCT Metadata_Plate) AS Metadata_plates"
        " FROM df WHERE Metadata_pert_type = 'trt'"
        " GROUP BY Metadata_JCP2022,Metadata_pert_type"
    )
    merged = duckdb.sql(  # noqa: F841
        "SELECT A.Metadata_JCP2022 AS"
        " Metadata_JCP2022,B.Metadata_pert_type as Metadata_pert_type,"
        "COLUMNS(c->c NOT LIKE 'Metadata%') FROM plates_trt A"
        " JOIN df B on (list_contains(A.Metadata_plates, B.Metadata_Plate)"
        " AND A.Metadata_JCP2022 = B.Metadata_JCP2022)"
        " OR (B.Metadata_pert_type = 'negcon'"
        " AND list_contains(A.Metadata_plates, B.Metadata_Plate))"
    )
    stats_str = ",".join(
        [
            metric
            + "(COLUMNS(c -> c NOT LIKE 'Metadata%')) AS "
            + metric.split("_")[0]
            + "_col"
            for metric in ("count", "avg", "var_samp")
        ]
    )
    metrics = duckdb.sql(
        f"SELECT Metadata_JCP2022,Metadata_pert_type,{stats_str}"
        " FROM merged GROUP BY Metadata_JCP2022,Metadata_pert_type"
        " ORDER BY Metadata_pert_type,Metadata_JCP2022"
    )

    # Compute t statistic from metrics
    stats = da.asarray(
        tuple(
            x for k, x in metrics.fetchnumpy().items() if not k.startswith("Meta")
        ),
        dtype=da.float64,
    )
    mt, trt = stats.shape
    mt = int(mt / 3)
    trt = int(trt / 2)
    n = slice(0, mt)
    m = slice(mt, mt * 2)
    v = slice(mt * 2, mt * 3)

    (n2, m2, v2), (n1, m1, v1) = [
        [stats[x, y] for x in (n, m, v)]
        for y in (slice(0, trt), slice(trt, trt * 2))
    ]

    df_ = n1 + n2 - 2
    sv = ((n1 - 1) * v1 + (n2 - 1) * v2) / df_
    diff = m1 - m2
    denom = da.sqrt(sv * (1 / n1 + 1 / n2))
    t_stat = diff / denom
    d_ = diff / da.sqrt(sv)

    # P-values
    cdf = t.cdf(t_stat, df_)
    sf = t.sf(t_stat, df_)
    p_value = np.minimum(sf, cdf) * 2

    # FDR correction
    with ThreadPoolExecutor() as ex:
        corrected_p_values = list(
            ex.map(lambda x: multipletests(x, method="fdr_bh")[1], p_value)
        )

    return da.asarray(corrected_p_values).T, da.asarray(d_).T


# --- index_selection ---


@app.function
def get_ranks_per_feature(mat: da.Array, n: int = 50) -> da.Array:
    """Return the top n indices per feature (column), ranked by largest value."""
    return da.argtopk(mat, n, axis=0)


@app.function
def get_ranks_per_perturbation(mat: da.Array, n: int = 10) -> da.Array:
    """Return the top n indices per compound (row), ranked by smallest value."""
    return da.argtopk(mat, -n, axis=1)


# --- parse_features ---


@app.function
def get_feature_groups(
    feature_fullnames: tuple[str],
    feature_names: tuple[str] = ("Compartment", "Feature", "Channel", "Suffix"),
) -> list[tuple]:
    """Group features in a consistent manner using a regex."""
    masks = "|".join(("Cells", "Nuclei", "Cytoplasm", "Image", "Object"))
    channels = "|".join(("DNA", "AGP", "RNA", "ER", "Mito", "Image"))
    chless_feats = "|".join(
        (
            "AreaShape",
            "Neighbors",
            "RadialDistribution",
            "Location",
            "Count",
            "Number",
            "Parent",
            "Children",
            "ObjectSkeleton",
            "Threshold",
        )
    )

    std = re.compile(rf"({masks})_(\S+)_(Orig)?({channels})(_.*)?")
    chless = re.compile(f"({masks})_?({chless_feats})_?([a-zA-Z]+)?(.*)?")

    results = [(std.findall(x) or chless.findall(x))[0] for x in feature_fullnames]
    results = [
        (
            (x[0], "".join(x[1:3]), "", x[3])
            if len(x) < 5
            else (*x[:2], "".join(x[2:4]), x[4])
        )
        for x in results
    ]
    return results, feature_names


# --- main pipeline ---


@app.function
def generate_features(
    dset: str,
    n_feat_per_compound: int,
    n_compounds_per_feat: int,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> duckdb.DuckDBPyRelation:
    """Generate feature significance rankings for a single JUMP dataset."""
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
    _filtered = duckdb.sql(
        "SELECT * FROM precor WHERE Metadata_pert_type != 'negcon'"
    )
    med, _ = compute_consensus(_filtered, jcp_col)
    filtered_med = duckdb.sql(f'SELECT * FROM med ORDER BY "{jcp_col}"')

    # Extract numpy arrays
    feat_cols = [
        c for c in filtered_med.columns
        if not c.startswith("Metadata_") and c != jcp_col
    ]
    _col_list = ", ".join(f'"{c}"' for c in feat_cols)
    median_vals = np.array(
        duckdb.sql(f"SELECT {_col_list} FROM filtered_med").fetchall(),
        dtype=np.float64,
    )

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
    decomposed_rows, decomposed_names = get_feature_groups(
        tuple(feat_cols), FEAT_DECOMPOSITION
    )
    decomposed_arr = np.array(decomposed_rows)

    featstat_computed = da.around(featstat, NDECIMALS).compute()
    cohens_d_full = cohens_d.compute()
    cohens_d_computed = np.around(cohens_d_full, 3)

    # Extract JCP ids
    jcp_ids = np.array(
        [r[0] for r in duckdb.sql(f'SELECT "{jcp_col}" FROM filtered_med').fetchall()]
    )

    # Build dataframe via Arrow
    _feat_data = pa.table({
        **{name: decomposed_arr[ys, i] for i, name in enumerate(decomposed_names)},
        stat_col: featstat_computed[xs, ys].astype(np.float64),
        effect_col: cohens_d_computed[xs, ys].astype(np.float64),
        abs_effect_col: np.abs(cohens_d_computed[xs, ys]).astype(np.float64),
        val_col: np.around(median_vals[xs, ys].astype(np.float64), 3),
        jcp_short: jcp_ids[xs],
        rank_gene_col: rankg.astype(np.int64),
        rank_feat_col: rankf.astype(np.int64),
    })
    result = duckdb.sql("SELECT * FROM _feat_data")

    # Add images
    df_meta = duckdb.sql("SELECT COLUMNS('Metadata.*') FROM precor")
    result = add_sample_images(
        result, df_meta, get_range(dset_type), img_col,
        left_col=jcp_short, right_col=jcp_col,
    )

    # Map names
    jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl = build_mappers(
        precor, jcp_col, dset_type
    )

    for _name, _mapper in [
        ("_feat_std_map", jcp_to_std),
        ("_feat_entrez_map", jcp_to_entrez),
        ("_feat_syn_map", get_synonym_mapper()),
    ]:
        duckdb.execute(
            f"CREATE OR REPLACE TEMP TABLE {_name} AS "
            "SELECT UNNEST($1::VARCHAR[]) AS _key, UNNEST($2::VARCHAR[]) AS _val",
            [list(_mapper.keys()), list(str(v) for v in _mapper.values())],
        )

    result = duckdb.sql(f"""
        SELECT result.*,
            COALESCE(s._val, '') AS "{std_outname}",
            COALESCE(syn._val, COALESCE(ent._val, '')) AS "Synonyms"
        FROM result
        LEFT JOIN _feat_std_map s ON CAST(result."{jcp_short}" AS VARCHAR) = s._key
        LEFT JOIN _feat_entrez_map ent ON CAST(result."{jcp_short}" AS VARCHAR) = ent._key
        LEFT JOIN _feat_syn_map syn ON CAST(ent._val AS VARCHAR) = syn._key
    """)

    for _name in ("_feat_std_map", "_feat_entrez_map", "_feat_syn_map"):
        duckdb.execute(f"DROP TABLE IF EXISTS {_name}")

    # Replicability
    result = add_replicability(
        result, left_on=jcp_short, right_on=jcp_col,
        cols_to_add=replicability_cols,
    )

    # External links
    key_source_mapper = build_key_source_mapper(
        dset_type, jcp_short, jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl
    )
    result = add_external_sites(result, ext_links_col, key_source_mapper)

    # Build final column order
    decomp_cols = ", ".join(f'"{c}"' for c in decomposed_names)
    repl_cols = ", ".join(f'"{c}"' for c in replicability_cols.values())

    sorted_df = duckdb.sql(f"""
        SELECT
            {decomp_cols},
            "{stat_col}",
            "{effect_col}",
            "{abs_effect_col}",
            "{std_outname}",
            "{img_col}",
            {repl_cols},
            "{val_col}",
            "{rank_gene_col}",
            "{rank_feat_col}",
            "{jcp_short}",
            "{ext_links_col}",
            "Synonyms"
        FROM result
    """)

    # Write outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_parquet(sorted_df, output_dir / f"{dset}_features.parquet")
    write_metadata(dset_type, "feature", sorted_df.columns)

    # Full matrices
    jcp_col_data = [
        r[0] for r in duckdb.sql(f'SELECT "{jcp_col}" FROM filtered_med').fetchall()
    ]
    for data, suffix in [
        (featstat_computed, "significance_full"),
        (cohens_d_full, "cohens_d_full"),
    ]:
        arrays = {name: data[:, i].astype(np.float64) for i, name in enumerate(feat_cols)}
        arrays[jcp_col] = pa.array(jcp_col_data)
        _matrix = pa.table(arrays)
        _write_parquet(
            duckdb.sql("SELECT * FROM _matrix"),
            output_dir / f"{dset_type}_{suffix}.parquet",
        )

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
    _count = duckdb.sql("SELECT COUNT(*) FROM _result").fetchone()[0]
    mo.md(
        f"**Done** — {_count} rows written to `databases/{_dset}_features.parquet`"
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
