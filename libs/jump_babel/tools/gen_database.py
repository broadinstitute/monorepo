#!/usr/bin/env jupyter
"""
Script to build a sqlite containing the final version of a database
"""
from functools import cache

import polars as pl
import pooch


# Make names consistent
def provide_mapper(
    df: pl.DataFrame, std_col: str, brd_col: str = None
) -> dict[str, str]:
    # validates mapping keys against a dataframe to rename columns consistently
    standard_col_mapper = {
        "Metadata_InChIKey": std_col,
        "Metadata_Symbol": std_col,
        "InChIKey": std_col,
        "gene": std_col,
        "broad_sample": brd_col,
    }
    return {k: v for k, v in standard_col_mapper.items() if k in df.columns}


def merge_on_null(left: str, right: str) -> pl.Expr:
    return (
        pl.struct((left, right))
        .map_elements(lambda cols: cols[right] or cols[left])
        .alias(left)
    )


# Files used
@cache
def get_table(table_name: str) -> pl.DataFrame:
    # Obtained from broad_portrait
    METADATA_LOCATION = (
        "https://github.com/jump-cellpainting/datasets/raw/"
        "baacb8be98cfa4b5a03b627b8cd005de9f5c2e70/metadata/"
        "{}.csv.gz"
    )
    METAFILE_HASH = {
        "compound": "a6e18f8728ab018bd03fe83e845b6c623027c3baf211e7b27fc0287400a33052",
        "well": "677d3c1386d967f10395e86117927b430dca33e4e35d9607efe3c5c47c186008",
        "crispr": "979f3c4e863662569cc36c46eaff679aece2c4466a3e6ba0fb45752b40d2bd43",
        "orf": "fbd644d8ccae4b02f623467b2bf8d9762cf8a224c169afa0561fedb61a697c18",
    }

    return pl.read_csv(
        pooch.retrieve(
            url=METADATA_LOCATION.format(table_name),
            known_hash=METAFILE_HASH[table_name],
        ),
        infer_schema_length=int(1e10),
    )


def get_target_plate_urls():
    target_1_urls = [
        (
            "https://github.com/jump-cellpainting/JUMP-Target/raw/"
            f"bd046851a28fb2257ef4c57c5ea4d496f1a08642/JUMP-Target-1_{x}_metadata.tsv"
        )
        for x in ("compound", "orf", "crispr")
    ]

    target_2_url = (
        "https://github.com/jump-cellpainting/JUMP-Target/raw/"
        "bd046851a28fb2257ef4c57c5ea4d496f1a08642/JUMP-Target-2_compound_metadata.tsv"
    )
    return (*target_1_urls, target_2_url)


## Target datasets
targets = [pl.read_csv(url, separator="\t") for url in get_target_plate_urls()]

jcp_col = "Metadata_JCP2022"
brd_col = "Metadata_broad_sample"
std_col = "standard_key"
pert_col = "Metadata_pert_type"


targets_combined = pl.concat(
    [
        target.rename(provide_mapper(target, std_col, brd_col)).select(
            std_col, brd_col, "pert_type", "control_type"
        )
        for target in targets
    ]
).unique()


# Consolidate controls into a single column
targets_combined_control = (
    targets_combined.with_columns(merge_on_null("pert_type", "control_type"))
    .drop("control_type")
    .unique()
)


def select_if_available(df, cols):
    # Select columns present in df
    return df.select(*set(df.columns).intersection(cols))


# ORF + CRISPR + COMPOUNDS
df_all = []
for dataset in ("orf", "crispr", "compound"):
    table = get_table(dataset).rename(provide_mapper(get_table(dataset), std_col))
    sel_table = select_if_available(table, (jcp_col, std_col, "Metadata_NCBI_Gene_ID"))
    if df_all is None:
        df_all = sel_table
    else:
        df_all.append(sel_table)
df_all = pl.concat(df_all, how="diagonal")

df_all_pert = df_all.join(
    get_table("orf").select(jcp_col, "Metadata_broad_sample", pert_col),
    on=jcp_col,
    how="outer",
)

# Combine target plates table to the normal one
all_target_pert = df_all_pert.join(targets_combined_control, on=std_col, how="outer")

# Combine pert_type and broad sample from both sources
# Note that this picks a single broad_sample per JCP
pert_target_all = all_target_pert.with_columns(
    merge_on_null(brd_col, f"{brd_col}_right"),
    merge_on_null(pert_col, "pert_type"),
).drop("pert_type", f"{brd_col}_right")

manual_mapper = {
    "JCP2022_085227": ("Aloxistatin", "poscon"),
    "JCP2022_037716": ("AMG900", "poscon"),
    "JCP2022_025848": ("Dexamethasone", "poscon"),
    "JCP2022_046054": ("FK-866", "poscon"),
    "JCP2022_035095": ("LY2109761", "poscon"),
    "JCP2022_064022": ("NVS-PAK1-1", "poscon"),
    "JCP2022_050797": ("Quinidine", "poscon"),
    "JCP2022_012818": ("TC-S-7004", "poscon"),
    "JCP2022_033924": ("DMSO", "negcon"),
    "JCP2022_999999": ("UNTREATED", pl.Null),
    "JCP2022_900001": ("BAD CONSTRUCT", pl.Null),
    "JCP2022_UNKNOWN": ("UNKNOWN", pl.Null),
}
jcp_std, jcp_pert = [{k: v[i] for k, v in manual_mapper.items()} for i in range(2)]

pert_target_all_manual = pert_target_all.with_columns(
    pl.struct((jcp_col, std_col))
    .map_elements(lambda cols: jcp_std.get(cols[jcp_col], cols[std_col]))
    .alias(std_col)
)

# Replace nulls with trt
pert_target_all_manual_trt = pert_target_all_manual.with_columns(
    pl.col(pert_col).fill_null("trt")
)

final_version = pert_target_all_manual_trt.select(
    pl.all().name.map(lambda col_name: col_name.replace("Metadata_", ""))
)

# {x: x.lstrip("Metadata_") for x in (jcp_col, brd_col, pert_col)}

# Save
db_name = "babel.db"
final_version.write_database(
    table_name="babel",
    connection=f"sqlite:{db_name}",
    if_exists="replace",
    engine="adbc",
)
