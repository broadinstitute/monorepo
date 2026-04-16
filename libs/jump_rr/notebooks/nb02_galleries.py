# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "polars",
#     "jump-rr",
# ]
# ///

"""Generate an interface to browse all available JUMP images."""

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")

with app.setup:
    from pathlib import Path

    import polars as pl
    from nb01_load_data import (
        JCP_COL,
        REPLICABILITY_COLS,
        STD_OUTNAME,
        build_key_source_mapper,
        build_mappers,
    )

    from jump_rr.consensus import get_range
    from jump_rr.datasets import get_dataset
    from jump_rr.formatters import add_external_sites, format_value
    from jump_rr.metadata import write_metadata
    from jump_rr.replicability import add_replicability

    EXT_LINKS_COL = "Resources"
    DEFAULT_OUTPUT_DIR = Path("./databases")


@app.function
def generate_gallery(dset: str, output_dir: Path = DEFAULT_OUTPUT_DIR) -> pl.DataFrame:
    """
    Generate a browsable gallery for a single JUMP dataset.

    Loads profiles, maps names, generates image URLs, adds replicability
    and external links, writes parquet + metadata JSON.
    """
    jcp_col = JCP_COL
    std_outname = STD_OUTNAME
    ext_links_col = EXT_LINKS_COL
    replicability_cols = REPLICABILITY_COLS

    # Load
    df = pl.scan_parquet(get_dataset(dset, return_pooch=False))

    # Map names
    collected_df = df.select(jcp_col).unique().collect()
    jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl = build_mappers(
        collected_df, jcp_col, dset
    )

    # Generate image URLs and add standard names
    df = df.with_columns(
        *[
            pl.format(
                format_value("img", "phenaid", tuple("{}" for _ in range(8))),
                *[pl.col(f"Metadata_{x}") for x in ("Source", "Plate", "Well")],
                site,
                *[pl.col(f"Metadata_{x}") for x in ("Source", "Plate", "Well")],
                site,
            ).alias(f"Site {site}")
            for site in get_range(dset)
        ],
        pl.col(jcp_col).replace_strict(jcp_to_std, default="").alias(std_outname),
    )

    order = [
        std_outname,
        jcp_col,
        "^Site.*$",
        "Metadata_Source",
        "Metadata_Plate",
        "Metadata_Well",
    ]

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
    order.insert(1, ext_links_col)
    order = (*order, *replicability_cols.values())

    # Rename and select
    df = (
        df.select(pl.col(order))
        .collect()
        .rename(lambda c: c.removeprefix("Metadata_"))
        .rename({"JCP2022": "JCP2022"})
    )

    # Write
    output_dir.mkdir(parents=True, exist_ok=True)
    final_output = output_dir / f"{dset}_gallery.parquet"
    df.write_parquet(final_output, compression="zstd")
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
    mo.md(
        f"**Done** — {len(_result)} rows written to `databases/{gallery_dset.value}_gallery.parquet`"
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
