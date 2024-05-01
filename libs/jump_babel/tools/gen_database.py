#!/usr/bin/env jupyter
"""
Script to build a sqlite containing the final version of a database
"""
import polars as pl
from broad_babel.data import get_table

# %% Colnames

jcp_col = "Metadata_JCP2022"
brd_col = "Metadata_broad_sample"
std_col = "standard_key"
pert_col = "Metadata_pert_type"
plate_col = "Metadata_plate_type"

plates_order = ("compound", "orf", "crispr", "compound")


def select_if_available(df: pl.DataFrame, cols: tuple[str]):
    # Select columns present in df
    return df.select(*set(df.columns).intersection(cols))


# %% Make names consistent
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


def get_target_plate_urls():
    target_1_urls = [
        (
            "https://github.com/jump-cellpainting/JUMP-Target/raw/"
            f"bd046851a28fb2257ef4c57c5ea4d496f1a08642/JUMP-Target-1_{x}_metadata.tsv"
        )
        for x in plates_order[:3]
    ]

    target_2_url = (
        "https://github.com/jump-cellpainting/JUMP-Target/raw/"
        "bd046851a28fb2257ef4c57c5ea4d496f1a08642/JUMP-Target-2_compound_metadata.tsv"
    )
    return (*target_1_urls, target_2_url)


# %% Add file

targets = [pl.read_csv(url, separator="\t") for url in get_target_plate_urls()]
for i, plate_type in enumerate(plates_order):
    targets[i] = targets[i].with_columns(pl.lit(plate_type).alias(plate_col))

# %%


# Add column names

targets_combined = pl.concat(
    [
        target.rename(provide_mapper(target, std_col, brd_col)).select(
            std_col,
            brd_col,
            "pert_type",
            "control_type",
            plate_col,
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


# ORF + CRISPR + COMPOUNDS
df_all = []
for dataset in plates_order[:3]:
    table = get_table(dataset).rename(provide_mapper(get_table(dataset), std_col))
    sel_table = (
        select_if_available(table, (jcp_col, std_col, "Metadata_NCBI_Gene_ID"))
        .with_columns(pl.lit(dataset).alias(plate_col))
        .cast(pl.Utf8)
    )
    if df_all is None:
        df_all = sel_table
    else:
        df_all.append(sel_table)
df_all = pl.concat(df_all, how="diagonal")

df_all_pert = df_all.join(
    get_table("orf").select(jcp_col, "Metadata_broad_sample", pert_col),
    # .with_columns(pl.lit("orf").alias(plate_col)),
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
    merge_on_null(plate_col, f"{plate_col}_right"),
).drop("pert_type", f"{brd_col}_right", f"{plate_col}_right")

# We keep this list here because it is manually-curated, and not everything
# was contained in the original datasets. The positive controls
# have not always been clearly defined.
manual_mapper = {
    "JCP2022_012818": "poscon",  # "TC-S-7004",
    "JCP2022_025848": "poscon",  # "Dexamethasone",
    "JCP2022_033924": "negcon",  # "DMSO",
    "JCP2022_035095": "poscon",  # "LY2109761",
    "JCP2022_037716": "poscon",  # "AMG900",
    "JCP2022_046054": "poscon",  # "FK-866",
    "JCP2022_050797": "poscon",  # "Quinidine",
    "JCP2022_064022": "poscon",  # "NVS-PAK1-1",
    "JCP2022_085227": "poscon",  # "Aloxistatin",
    "JCP2022_900001": "null",  # "BAD CONSTRUCT",
    "JCP2022_999999": "null",  # "UNTREATED",
    "JCP2022_UNKNOWN": "null",  # "UNKNOWN",
}
jcp_pert = {k: v for k, v in manual_mapper.items()}

# %%

# Replace nulls with trt
pert_target_all_trt = pert_target_all.with_columns(pl.col(pert_col).fill_null("trt"))

# Add manual annotations
pert_target_all_manual = pert_target_all_trt.with_columns(
    pl.struct((pert_col, jcp_col)).map_elements(
        lambda cols: jcp_pert.get(cols[jcp_col], cols[pert_col])
    )
)

# Remove "Metadata" prefixes
final_version = pert_target_all_manual.select(
    pl.all().name.map(lambda col_name: col_name.replace("Metadata_", ""))
)

# Save
db_name = "babel.db"
final_version.write_database(
    table_name="babel",
    connection=f"sqlite:{db_name}",
    if_exists="replace",
    engine="adbc",
)
