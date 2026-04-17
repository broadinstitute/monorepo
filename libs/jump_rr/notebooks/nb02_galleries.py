# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "duckdb>=1.1.3",
# ]
# ///

"""Generate an interface to browse all available JUMP images."""

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")

with app.setup:
    from pathlib import Path

    import duckdb
    import marimo as mo  # noqa: F401
    from nb01_load_data import (
        JCP_COL,
        REPLICABILITY_COLS,
        STD_OUTNAME,
        _write_parquet,
        add_external_sites,
        add_replicability,
        build_key_source_mapper,
        build_mappers,
        format_value,
        get_dataset,
        get_range,
        write_metadata,
    )

    EXT_LINKS_COL = "Resources"
    DEFAULT_OUTPUT_DIR = Path("./databases")


@app.function
def generate_gallery(
    dset: str, output_dir: Path = DEFAULT_OUTPUT_DIR
) -> duckdb.DuckDBPyRelation:
    """Generate a browsable gallery for a single JUMP dataset."""
    jcp_col = JCP_COL
    std_outname = STD_OUTNAME
    ext_links_col = EXT_LINKS_COL
    replicability_cols = REPLICABILITY_COLS

    # Load
    url = get_dataset(dset, return_pooch=False)
    df = duckdb.sql(f"SELECT * FROM read_parquet('{url}')")

    # Map names
    unique_jcp = duckdb.sql(f'SELECT DISTINCT "{jcp_col}" FROM df')
    jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl = build_mappers(
        unique_jcp, jcp_col, dset
    )

    # Register jcp_to_std mapper for name lookup
    duckdb.execute(
        "CREATE OR REPLACE TEMP TABLE _gal_std_map AS "
        "SELECT UNNEST($1::VARCHAR[]) AS _key, UNNEST($2::VARCHAR[]) AS _val",
        [list(jcp_to_std.keys()), list(jcp_to_std.values())],
    )

    # Build site image columns using printf
    img_tpl = format_value("img", "phenaid")
    site_cols = []
    for site in get_range(dset):
        site_cols.append(
            f"printf('{img_tpl}',"
            f" Metadata_Source, Metadata_Plate, Metadata_Well, '{site}',"
            f" Metadata_Source, Metadata_Plate, Metadata_Well, '{site}'"
            f') AS "Site {site}"'
        )

    df = duckdb.sql(f"""
        SELECT df.*,
            {', '.join(site_cols)},
            COALESCE(_gal_std_map._val, '') AS "{std_outname}"
        FROM df
        LEFT JOIN _gal_std_map ON CAST(df."{jcp_col}" AS VARCHAR) = _gal_std_map._key
    """)
    duckdb.execute("DROP TABLE IF EXISTS _gal_std_map")

    # Replicability
    df = add_replicability(
        df,
        left_on=jcp_col,
        right_on=jcp_col,
        cols_to_add=replicability_cols,
    )

    # External links
    key_source_mapper = build_key_source_mapper(
        dset, jcp_col, jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl
    )
    df = add_external_sites(df, ext_links_col, key_source_mapper)

    # Select ordered columns and rename Metadata_ prefixes
    site_col_names = ", ".join(f'"Site {site}"' for site in get_range(dset))
    repl_col_names = ", ".join(f'"{col}"' for col in replicability_cols.values())

    df = duckdb.sql(f"""
        SELECT
            "{std_outname}",
            "{ext_links_col}",
            "{jcp_col}" AS "{jcp_col.removeprefix('Metadata_')}",
            {site_col_names},
            Metadata_Source AS Source,
            Metadata_Plate AS Plate,
            Metadata_Well AS Well,
            {repl_col_names}
        FROM df
    """)

    # Write
    output_dir.mkdir(parents=True, exist_ok=True)
    final_output = output_dir / f"{dset}_gallery.parquet"
    _write_parquet(df, final_output)
    write_metadata(dset, "gallery", df.columns)

    return df


# --- Interactive UI ---


@app.cell
def _(mo):
    mo.md("# Gallery Generator\nBuild browsable image galleries for JUMP datasets.")
    return ()


@app.cell
def _(mo):
    gallery_dset = mo.ui.dropdown(
        options=["orf", "crispr", "compound"],
        value="crispr",
        label="Dataset",
    )
    gallery_dset
    return (gallery_dset,)


@app.cell
def _(mo):
    gallery_run = mo.ui.run_button(label="Generate gallery")
    gallery_run
    return (gallery_run,)


@app.cell
def _(gallery_dset, gallery_run, mo):
    mo.stop(not gallery_run.value)
    _result = generate_gallery(gallery_dset.value)
    _count = duckdb.sql("SELECT COUNT(*) FROM _result").fetchone()[0]
    mo.md(
        f"**Done** — {_count} rows written to"
        f" `databases/{gallery_dset.value}_gallery.parquet`"
    )
    return ()


@app.cell
def _(mo):
    mo.stop(mo.app_meta().mode != "run")
    for _dset in ("orf", "crispr", "compound"):
        print(f"Generating gallery for {_dset}...")
        generate_gallery(_dset)
    print("All galleries complete.")
    return ()


if __name__ == "__main__":
    app.run()
