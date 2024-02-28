#!/usr/bin/env jupyter
"""
Functions to get JUMP-CP images from AWS's s3://cellpainting-gallery.

Based on github.com/jump-cellpainting/datasets/blob/baacb8be98cfa4b5a03b627b8cd005de9f5c2e70/sample_notebook.ipynb

The general workflow is a bit contrived but it works:
a) If you have an item of interest and want to see them:
- Use broad_babel to convert item name to jump id (get_item_location_metadata)
- Use JUMP identifier to fetch the metadata dataframe with image locations (TODO isolate this)
- Use this location dataframe to build a full path and fetch it from there

Current problems:
- More controls than individual samples
- Control info is murky, requires using broad_babel

"""
from functools import cache

import numpy as np
import polars as pl
import pooch
from broad_babel import query

from jump_portrait.s3 import build_s3_image_path, get_image_from_s3path, read_parquet_s3
from jump_portrait.utils import batch_processing, parallel


@cache
def get_table(table_name: str) -> pl.DataFrame:
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
        "plate": "745391d930627474ec6e3083df8b5c108db30408c0d670cdabb3b79f66eaff48",
    }
    return pl.read_csv(
        pooch.retrieve(
            url=METADATA_LOCATION.format(table_name),
            known_hash=METAFILE_HASH[table_name],
        )
    )


def format_cellpainting_s3() -> str:
    return (
        "s3://cellpainting-gallery/cpg0016-jump/"
        "{Metadata_Source}/workspace/load_data_csv/"
        "{Metadata_Batch}/{Metadata_Plate}/load_data_with_illum.parquet"
    )


def get_sample(n: int = 2, seed: int = 42):
    sample = (
        get_table("plate")
        .filter(pl.col("Metadata_PlateType") == "TARGET2")
        .filter(
            pl.int_range(0, pl.count()).shuffle(seed=seed).over("Metadata_Source") < n
        )
    )
    s3_path = format_cellpainting_s3().format(**sample.to_dicts()[0])

    parquet_meta = read_parquet_s3(s3_path)  # , use_pyarrow=True)
    return parquet_meta


def get_jump_image(
    source: str,
    batch: str,
    plate: str,
    well: str,
    channel: str,
    site: str = 1,
    correction: str = "Orig",
    apply_correction: bool = True,
    compressed: bool = False,
) -> np.ndarray:
    """Main function to fetch a JUMP image for AWS.
    Metadata for most files can be obtained from a set of data frames,
    or itemrated using `get_item_location_metadata` from this module.

    Parameters
    ----------
    source : str
        Which collaborator (data source) itemrated the images.
    batch : str
        Batch name.
    plate : str
        Plate name.
    well : str
        Well number (e.g., A01).
    channel : str
        Channel to fetch, the standard ones are DNA, Mito, ER and AGP.
    site : int
        Site identifier (also called foci), default is 1.
    correction : str
        Whether or not to use corrected data. It does not by default.
    apply_correction : bool
        When correction=="Illum" apply Illum correction on original image.
    compressed : bool
        Whether or not to return a compressed image. Default is False.

    Returns
    -------
    np.ndarray
        Selected image as a numpy array.

    Examples
    --------
    FIXME: Add docs.
    """

    # Compressed images are already corrected
    if compressed:
        correction = "Orig"
        apply_correction = False

    s3_location_frame_uri = format_cellpainting_s3().format(
        Metadata_Source=source, Metadata_Batch=batch, Metadata_Plate=plate
    )
    location_frame = read_parquet_s3(s3_location_frame_uri)  # , use_pyarrow=True)
    unique_site = location_frame.filter(
        (pl.col("Metadata_Well") == well) & (pl.col("Metadata_Site") == str(site))
    )

    assert len(unique_site) == 1, "More than one site found"

    first_row = unique_site.row(0, named=True)
    s3_image_path = build_s3_image_path(
        row=first_row, channel=channel, correction=correction, compressed=compressed
    )
    result = get_image_from_s3path(s3_image_path)

    if correction == "Illum" and apply_correction:
        original_image_path = build_s3_image_path(
            row=first_row, channel=channel, correction="Orig"
        )
        result = get_image_from_s3path(original_image_path) / result
    return result


def get_item_location_metadata(
        item_name: str, controls: bool = True, operator:str or None=None, **kwargs
) -> pl.DataFrame:
    """
    First search for datasets in which this item was present.
    Return tuple with its Metadata location in order source, batch, plate,
    well and site.
    """
    input_column = kwargs.get("input_column") or "standard_key"

    # Get plates
    jcp_ids = query.run_query(
        query=item_name,
        input_column=input_column,
        output_column="JCP2022,standard_key",
        operator = operator,
    )
    jcp_item = {x[0]: x[1] for x in jcp_ids}
    meta_wells = get_table("well")
    # found_rows = meta_wells[meta_wells["Metadata_JCP2022"].isin(jcp_item)].copy()
    found_rows = meta_wells.filter(pl.col("Metadata_JCP2022").is_in(jcp_item.keys()))
    found_rows = found_rows.with_columns(pl.lit(item_name).alias("standard_key"))

    if controls:  # Fetch controls from broad babel
        control_jcp_ids = [
            x
            for x in map(
                lambda x: x[0],
                query.run_query(
                    query="negcon", input_column="pert_type", output_column="JCP2022"
                ),
            )
            if x is not None
        ]

        controls_meta = meta_wells.filter(
            pl.col("Metadata_JCP2022").is_in(control_jcp_ids),
            pl.col("Metadata_Plate").is_in(found_rows["Metadata_Plate"]),
        )
        controls_meta = controls_meta.with_columns(
            pl.lit("control").alias("standard_key")
        )
        found_rows = found_rows.vstack(controls_meta)

    # Get full plate metadata with (contains no info reference about wells)
    plate_level_metadata = get_table("plate").filter(
        pl.col("Metadata_Plate").is_in(found_rows.select("Metadata_Plate").to_series())
    )
    well_level_metadata = plate_level_metadata.join(
        found_rows,
        on=("Metadata_Source", "Metadata_Plate"),
    )
    return well_level_metadata


def load_filter_well_metadata(well_level_metadata: pl.DataFrame) -> pl.DataFrame:
    """
    Filters a dataframe with well info. Loading and filtering happens in a threaded manner. Note that it does not check for whole row duplication.

    Parameters
    ----------
    well_level_metadata : pl.DataFrame
        Contains the data

    Load metadata from a dataframe containing these columns
    - Metadata_Source
    - Metadata_Batch
    - Metadata_Plate
    - Metadata_Well


    Returns
    -------
    pl.DataFrame
        DataFrame with location of item
    """
    core_cols = (
        "Metadata_Source",
        "Metadata_Batch",
        "Metadata_Plate",
        "Metadata_PlateType",
    )
    metadata_fields = well_level_metadata.unique(
        subset=(
            *core_cols,
            "Metadata_Well",
            "standard_key",
        )
    )
    groups = metadata_fields.group_by(core_cols).agg("Metadata_Well").to_dicts()

    s3_locations_uri = [format_cellpainting_s3().format(**x) for x in groups]

    # Get uris for the specific wells in the fetched plates
    iterable = list(
        zip(
            s3_locations_uri,
            map(lambda x: x["Metadata_Well"], groups),
        )
    )
    well_images_uri = parallel(iterable, get_well_image_uris)

    selected_uris = pl.concat(well_images_uri)

    return selected_uris


@batch_processing
def get_well_image_uris(s3_location_uri, wells: list[str]) -> pl.DataFrame:
    # Returns a dataframe indicating the image location of specific wells for a given parquet file.
    locations_df = read_parquet_s3(s3_location_uri)  # , use_pyarrow=True)
    return locations_df.filter(pl.col("Metadata_Well").is_in(wells))


def get_item_location_info(
    item_name: str, controls: bool = True, **kwargs
) -> pl.DataFrame:
    """Wrapper to obtain a dataframe with locations of an item. It removes duplicate rows.

    Parameters
    ----------
    item_name : str
        Item of interest to query
    controls: bool
        Wether or not to fetch controls in the same plates as samples
    **kwargs: dict
        Keyword arguments passed on to load_filter_metadata

    Returns
    -------
    pl.DataFrame
        DataFrame with location of item

    Examples
    --------
    FIXME: Add docs.

    """
    input_column = kwargs.get("input_column") or "standard_key"

    well_level_metadata = get_item_location_metadata(
        item_name, controls=controls, input_column=input_column
    )
    item_selected_meta = load_filter_well_metadata(well_level_metadata, **kwargs)
    joint = item_selected_meta.join(
        well_level_metadata.drop("Metadata_Well"),
        on=("Metadata_Source", "Metadata_Batch", "Metadata_Plate"),
    )
    return joint.unique()


def get_collage(
    gene: str, channel: str = "DNA", plate_type: str = "ORF", **kwargs
) -> np.ndarray:
    """Return a collage of images from a given gene. Returned matrices are arranged in two rows,
    top row are the perturbations and bottom rows are their plate-per-plate controls.

    Parameters
    ----------
    gene : str
        input gene in standard format
    channel : str
        Channel to plot. Default is "DNA".
    plate_type : str
        plate type, can be "ORF", "CRISPR" or "Compound". Default is "ORF".
    **kwargs :
        Arguments to pass to get_item_location_info

    Returns
    -------
    np.ndarray
        Concatenated array of dimensions (2,N) where N is the number of plates
        in which the gene is present.

    Examples
    --------
    FIXME: Add docs.

    """
    # Convenience variables
    transient_col = "fullpath"
    input_column = kwargs.get("input_column", "standard_key")
    group_by_fields = (
        "Metadata_Source",
        "Metadata_Batch",
        "Metadata_Plate",
        "Metadata_PlateType",
    )

    # Find location
    all_locations = get_item_location_info(gene)
    image_locations = {}
    for v in ("control", gene):
        subdf = all_locations.filter(pl.col(input_column) == v)
        subdf = subdf.select(reversed(subdf.columns)).with_columns(
            pl.concat_str(f"^.*Orig{channel}.*$").alias(transient_col)
        )
        image_locations[v] = subdf.group_by(group_by_fields).agg(pl.col(transient_col))

    # Merge gene and control dataframes
    combined = image_locations[gene].join(
        image_locations["control"],
        on=group_by_fields[:-2],
        suffix="_control",
    )

    combined = combined.filter(pl.col("Metadata_PlateType") == plate_type)

    # Sample items
    regex = "^fullpath.*$"
    samples = combined.with_columns(pl.all().map_elements(len)).select(
        pl.col(regex).map_elements(lambda x: np.random.randint(x))
    )

    base = combined.select(pl.col(regex)).to_numpy()

    # Fetch the sampled indices from our data frame
    x, y = samples.shape
    locations = [["" for _ in range(y)] for _ in range(x)]
    for i, gene_ctrl in enumerate(samples.to_numpy()):
        for j, x in enumerate(gene_ctrl):
            locations[i][j] = base[i, j][x]

    # Reformat and concatenate
    imgs = []
    for plate in locations:
        pair = []
        for fpath in plate:
            pair.append(get_image_from_s3path(fpath))
        imgs.append(pair)

    concat = np.concatenate([np.concatenate(x, axis=0) for x in imgs], axis=1)

    return concat
