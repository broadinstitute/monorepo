"""
JCP ids in {crispr, orf, compound} dataset but not on well dataset.
Update the crispr,orf and compound dataframes to remove text and save them into the folder.
"""

"""
JCP ids in {crispr, orf, compound} dataset but not on well dataset.
Update the crispr,orf and compound dataframes to remove text and save them into the folder.
"""
import gzip
from pathlib import Path

import polars as pl
import pooch

out_path = Path("/home/amunoz/projects/datasets/metadata")


def get_table(table_name: str) -> pl.DataFrame:
    # Obtained from broad_portrait
    METADATA_LOCATION = (
        "https://github.com/jump-cellpainting/datasets/raw/"
        "af42e44b7f7e0097c5cdd4a8f4635f19fbf3298e/metadata/"
        "{}.csv.gz"
    )
    METAFILE_HASH = {
        "compound": "c15758a444e19c8c694fbcd1c45453038f4a6c8d2616c578cc02a121535bbba7",
        "well": "677d3c1386d967f10395e86117927b430dca33e4e35d9607efe3c5c47c186008",
        "crispr": "979f3c4e863662569cc36c46eaff679aece2c4466a3e6ba0fb45752b40d2bd43",
        "orf": "fbd644d8ccae4b02f623467b2bf8d9762cf8a224c169afa0561fedb61a697c18",
        "plate": "745391d930627474ec6e3083df8b5c108db30408c0d670cdabb3b79f66eaff48",
    }

    return pl.read_csv(
        pooch.retrieve(
            url=METADATA_LOCATION.format(table_name),
            known_hash=METAFILE_HASH[table_name],
        ),
        infer_schema_length=16000,
    )


well_jcp = set(get_table("well")["Metadata_JCP2022"])
datasets = ("compound", "crispr", "orf")
d = {}
for dataset in datasets:
    dataset_jcp = get_table(dataset)["Metadata_JCP2022"]
    n_original = len(dataset_jcp)
    d[dataset] = set(dataset_jcp).intersection(well_jcp)
    print(f"Dataset {dataset} contains {n_original-len(d[dataset])} fewer entries")
"""
Dataset compound contains 957 fewer entries
Dataset crispr contains 0 fewer entries
Dataset orf contains 10 fewer entries
"""
# %% Save dataset
for name, dset in d.items():
    with gzip.open(out_path / f"{name}.csv.gz", "wb") as f:
        original_table = get_table(name)
        new_table = original_table.filter(pl.col("Metadata_JCP2022").is_in(dset))
        print(new_table.head())
        new_table.write_csv(f)
