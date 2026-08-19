# /// script
# requires-python = ">=3.11,<3.15"
# dependencies = [
#     "jump-portrait @ git+https://github.com/broadinstitute/monorepo.git@ce781ea6ebf67c782682c2cb4d95c89096372004#subdirectory=libs/jump_portrait",
#     "marimo>=0.23.0,<0.24.0",
#     "matplotlib>=3.8.2,<4.0.0",
#     "numpy>=2.1.2",
# ]
# ///

"""Explore one public JUMP imaging site through VirtualiZarr."""

import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium")

with app.setup:
    from contextlib import chdir
    from pathlib import Path
    from tempfile import TemporaryDirectory

    import marimo as mo
    import matplotlib.colors as mpl
    import numpy as np
    from matplotlib import pyplot as plt

    from jump_portrait import (
        CHANNELS,
        RequestTrace,
        get_item_location_metadata,
        get_jump_image_site,
    )

    CHANNEL_COLORS = {
        "AGP": "#FF7F00",
        "DNA": "#0000FF",
        "ER": "#00FF00",
        "Mito": "#FF0000",
        "RNA": "#FFFF00",
    }
    LOCATION_FIELDS = ("Source", "Batch", "Plate", "Well", "Site")
    VERIFIED_LOCATION = ("source_8", "J3", "A1166127", "A01", 1)
    INDEX_ORIGIN = (
        "https://d3dw4c1b79pj57.cloudfront.net/19373370/jump_index.parquet/content"
    )
    INDEX_SIZE = 145_197_890
    INDEX_HASH = (
        "sha256:f45ea1a5de091e43caf35358370abf843bd2be47b2810283fd76db472b5acc6a"
    )


@app.function
def metadata_records(metadata: object) -> list[dict[str, object]]:
    """Return site records in deterministic location order."""
    return sorted(
        metadata.to_pylist(),
        key=lambda row: tuple(
            str(row[f"Metadata_{field}"]) for field in LOCATION_FIELDS
        ),
    )


@app.function
def location_label(row: dict[str, object]) -> str:
    """Build a readable label for one indexed site."""
    return " | ".join(str(row[f"Metadata_{field}"]) for field in LOCATION_FIELDS)


@app.function
def location_options(records: list[dict[str, object]]) -> dict[str, int]:
    """Map unique location labels to deterministic row indices."""
    options: dict[str, int] = {}
    for index, row in enumerate(records):
        label = location_label(row)
        if label in options:
            label = f"{label} | row {index + 1}"
        options[label] = index
    return options


@app.function
def channel_url_rows(row: dict[str, object]) -> list[dict[str, str]]:
    """Return each displayed channel's original TIFF URL."""
    return [
        {"channel": channel, "original TIFF": str(row[f"URL_Orig{channel}"])}
        for channel in CHANNELS
    ]


@app.function
def trace_snapshot(trace: object, start: int = 0) -> dict[str, object]:
    """Summarize traced object-store requests from one offset."""
    requests = tuple(trace.requests[start:])
    methods = tuple(str(request.method) for request in requests)
    return {
        "requests": len(requests),
        "requested_bytes": sum(int(request.length or 0) for request in requests),
        "methods": methods,
        "full_gets": methods.count("get"),
    }


@app.function
def audit_artifacts(directory: str | Path) -> dict[str, tuple[str, ...]]:
    """List forbidden image-index, TIFF, and large local files."""
    root = Path(directory)
    files = tuple(path for path in root.rglob("*") if path.is_file())

    def relative(paths: tuple[Path, ...]) -> tuple[str, ...]:
        return tuple(sorted(str(path.relative_to(root)) for path in paths))

    return {
        "image_indexes": relative(
            tuple(
                path
                for path in files
                if path.name == "jump_index.parquet"
                or path.stat().st_size == INDEX_SIZE
            )
        ),
        "tiffs": relative(
            tuple(path for path in files if path.suffix.lower() in {".tif", ".tiff"})
        ),
        "large_files": relative(
            tuple(path for path in files if path.stat().st_size > 140_000_000)
        ),
    }


@app.function
def format_bytes(value: int) -> str:
    """Format an integer byte count."""
    if value < 1024:
        return f"{value} B"
    scaled = float(value)
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        scaled /= 1024
        if scaled < 1024 or unit == "TiB":
            return f"{scaled:.2f} {unit}"
    raise AssertionError("unreachable")


@app.function
def request_summary(snapshot: dict[str, object]) -> str:
    """Format compact, auditable request evidence."""
    methods = tuple(str(method) for method in snapshot["methods"])
    return (
        f"requests={int(snapshot['requests'])}, "
        f"requested={format_bytes(int(snapshot['requested_bytes']))}, "
        f"methods={', '.join(sorted(set(methods))) or 'none'}, "
        f"full-object get={int(snapshot['full_gets'])}"
    )


@app.function
def render_channels(
    pixels: object,
    label: str,
    intensity_percentile: float,
) -> object:
    """Render the five labeled Cell Painting channels."""
    figure, axes = plt.subplots(2, 3, figsize=(7.8, 5.2))
    flat_axes = axes.ravel()
    for axis, channel in zip(flat_axes, CHANNELS, strict=False):
        image = np.asarray(pixels.sel(channel=channel))
        upper = max(float(np.percentile(image, intensity_percentile)), 1.0)
        color_map = mpl.LinearSegmentedColormap.from_list(
            channel,
            ("#000000", CHANNEL_COLORS[channel]),
        )
        axis.imshow(image, vmin=0, vmax=upper, cmap=color_map)
        axis.axis("off")
        axis.text(
            0.05,
            0.95,
            channel,
            horizontalalignment="left",
            verticalalignment="top",
            fontsize=18,
            color="black",
            bbox={
                "facecolor": "white",
                "alpha": 0.8,
                "edgecolor": "none",
                "boxstyle": "round,pad=0.3",
            },
            transform=axis.transAxes,
        )

    flat_axes[-1].text(
        0.5,
        0.5,
        label,
        horizontalalignment="center",
        verticalalignment="center",
        fontsize=18,
        color="black",
        transform=flat_axes[-1].transAxes,
    )
    flat_axes[-1].axis("off")
    figure.tight_layout()
    return figure


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Open original JUMP images without downloading TIFFs

    Query a gene, InChIKey, or JCP2022 identifier, choose one returned site,
    and display its five original Cell Painting channels.

    The image stays virtual until a pixel window is selected. The evidence
    panel reports the TIFF range requests and confirms that the controlled
    working directory contains no image index or TIFF copy. The validated
    compatibility boundary is Source_8's uncompressed strip TIFF layout.
    """)
    return


@app.cell
def _():
    is_script_mode = mo.app_meta().mode == "script"
    return (is_script_mode,)


@app.cell(hide_code=True)
def _():
    query_form = (
        mo.md(
            """
            **Find a perturbation**

            Query type: {input_column}

            Identifier: {item_name}
            """
        )
        .batch(
            input_column=mo.ui.dropdown(
                options={
                    "Gene or InChIKey": "standard_key",
                    "JCP2022 ID": "JCP2022",
                },
                value="JCP2022 ID",
                label="",
            ),
            item_name=mo.ui.text(
                value="JCP2022_043547",
                placeholder="RAB30 or JCP2022_043547",
                label="",
                full_width=True,
            ),
        )
        .form(submit_button_label="Find images")
    )
    mo.vstack(
        [
            query_form,
            mo.md(
                "Try gene `RAB30`, an InChIKey, or the verified Source_8 "
                "example `JCP2022_043547`."
            ),
        ]
    )
    return (query_form,)


@app.cell
def _(is_script_mode, query_form):
    query_value = (
        {"input_column": "JCP2022", "item_name": "JCP2022_043547"}
        if is_script_mode
        else query_form.value
    )
    mo.stop(
        query_value is None,
        mo.callout(mo.md("Submit an identifier to find image sites."), kind="info"),
    )
    item_name = str(query_value["item_name"]).strip()
    mo.stop(
        not item_name,
        mo.callout(mo.md("Enter an identifier before searching."), kind="warn"),
    )
    input_column = str(query_value["input_column"])
    return input_column, item_name


@app.cell
def _(input_column, item_name):
    metadata = get_item_location_metadata(item_name, input_column=input_column)
    records = metadata_records(metadata)
    mo.stop(
        not records,
        mo.callout(
            mo.md(f"No image sites were returned for `{item_name}`."), kind="warn"
        ),
    )
    return (records,)


@app.cell(hide_code=True)
def _(records):
    options = location_options(records)
    default_index = next(
        (
            index
            for index, row in enumerate(records)
            if tuple(row[f"Metadata_{field}"] for field in LOCATION_FIELDS)
            == VERIFIED_LOCATION
        ),
        next(
            (
                index
                for index, row in enumerate(records)
                if row["Metadata_Source"] == "source_8"
            ),
            0,
        ),
    )
    default_label = next(
        label for label, index in options.items() if index == default_index
    )
    location_form = (
        mo.md(
            """
            **Choose a source, batch, plate, well, and site**

            {location}
            """
        )
        .batch(
            location=mo.ui.dropdown(
                options=options,
                value=default_label,
                searchable=True,
                label="",
                full_width=True,
            )
        )
        .form(submit_button_label="Open virtual site")
    )
    mo.vstack(
        [
            mo.md(f"Found **{len(records):,}** site-level image records."),
            location_form,
        ]
    )
    return default_index, location_form


@app.cell
def _(default_index, is_script_mode, location_form, records):
    location_value = (
        {"location": default_index} if is_script_mode else location_form.value
    )
    mo.stop(
        location_value is None,
        mo.callout(mo.md("Choose a site to continue."), kind="info"),
    )
    selected_row = records[int(location_value["location"])]
    mo.vstack(
        [
            mo.md("### Selected original images"),
            mo.ui.table(
                channel_url_rows(selected_row), pagination=False, selection=None
            ),
        ]
    )
    return (selected_row,)


@app.cell
def _(selected_row):
    source, batch, plate, well, site = (
        selected_row[f"Metadata_{field}"] for field in LOCATION_FIELDS
    )
    audit_workspace = TemporaryDirectory(prefix="jump-portrait-audit-")
    audit_directory = Path(audit_workspace.name)
    trace = RequestTrace()
    with chdir(audit_directory):
        virtual_site = get_jump_image_site(
            str(source),
            str(batch),
            str(plate),
            str(well),
            site=int(site),
            trace=trace,
        )
    construction_trace = trace_snapshot(trace)
    mo.callout(
        mo.md(
            "The five-channel site is open as a lazy labeled array. Only the "
            "selected pixel window is materialized below."
        ),
        kind="success",
    )
    return (
        audit_directory,
        audit_workspace,
        construction_trace,
        selected_row,
        trace,
        virtual_site,
    )


@app.cell(hide_code=True)
def _(item_name, selected_row, virtual_site):
    dimensions = tuple(str(dimension) for dimension in virtual_site.dims)
    mo.stop(
        dimensions != ("channel", "y", "x"),
        mo.callout(
            mo.md(f"Expected `(channel, y, x)`; received `{dimensions}`."),
            kind="danger",
        ),
    )
    height = int(virtual_site.sizes["y"])
    width = int(virtual_site.sizes["x"])
    y_range = mo.ui.range_slider(
        start=0,
        stop=height,
        step=1,
        value=[0, min(512, height)],
        label="Pixel rows",
        show_value=True,
        full_width=True,
    )
    x_range = mo.ui.range_slider(
        start=0,
        stop=width,
        step=1,
        value=[0, min(512, width)],
        label="Pixel columns",
        show_value=True,
        full_width=True,
    )
    intensity_percentile = mo.ui.slider(
        start=90.0,
        stop=100.0,
        step=0.1,
        value=99.5,
        label="Intensity percentile",
        show_value=True,
        full_width=True,
    )
    location = "/".join(
        str(selected_row[f"Metadata_{field}"]) for field in LOCATION_FIELDS
    )
    display_label = f"{item_name}\n\n{location}"
    mo.vstack(
        [
            mo.md(f"### {location}"),
            mo.md(
                "Choose the window to materialize. The default reads a 512 x "
                "512 corner crop and uses the 99.5th percentile for display."
            ),
            y_range,
            x_range,
            intensity_percentile,
        ]
    )
    return display_label, intensity_percentile, x_range, y_range


@app.cell
def _(
    audit_directory,
    audit_workspace,
    construction_trace,
    display_label,
    intensity_percentile,
    trace,
    virtual_site,
    x_range,
    y_range,
):
    audit_workspace
    y_start, y_stop = (int(value) for value in y_range.value)
    x_start, x_stop = (int(value) for value in x_range.value)
    mo.stop(
        y_start >= y_stop or x_start >= x_stop,
        mo.callout(
            mo.md("Pixel ranges must have positive width and height."), kind="warn"
        ),
    )
    with chdir(audit_directory):
        pixels = virtual_site.isel(
            y=slice(y_start, y_stop),
            x=slice(x_start, x_stop),
        ).compute()
    selected_trace = trace_snapshot(trace, start=int(construction_trace["requests"]))
    artifacts = audit_artifacts(audit_directory)
    figure = render_channels(
        pixels,
        display_label,
        float(intensity_percentile.value),
    )
    figure
    return artifacts, pixels, selected_trace


@app.cell
def _(
    artifacts,
    construction_trace,
    is_script_mode,
    pixels,
    selected_row,
    selected_trace,
    virtual_site,
    x_range,
    y_range,
):
    assert tuple(virtual_site.dims) == ("channel", "y", "x")
    assert virtual_site.coords["channel"].values.tolist() == list(CHANNELS)
    assert virtual_site.dtype == np.dtype("uint16")
    assert tuple(pixels.dims) == ("channel", "y", "x")
    assert int(construction_trace["full_gets"]) == 0
    assert int(selected_trace["full_gets"]) == 0
    assert not artifacts["image_indexes"]
    assert not artifacts["tiffs"]
    assert not artifacts["large_files"]
    if is_script_mode:
        assert selected_row["Metadata_Source"] == "source_8"

    evidence = [
        {
            "evidence": "logical array",
            "value": (
                f"shape={tuple(virtual_site.shape)}, dtype={virtual_site.dtype}, "
                f"size={format_bytes(int(virtual_site.nbytes))}"
            ),
        },
        {
            "evidence": "virtual references",
            "value": (
                f"count={virtual_site.attrs['virtual_reference_count']}, "
                f"size={format_bytes(int(virtual_site.attrs['virtual_reference_bytes']))}"
            ),
        },
        {
            "evidence": "selected read",
            "value": (
                f"channel=all, y={tuple(y_range.value)}, x={tuple(x_range.value)}, "
                f"shape={tuple(pixels.shape)}, size={format_bytes(int(pixels.nbytes))}"
            ),
        },
        {
            "evidence": "virtual construction requests",
            "value": request_summary(construction_trace),
        },
        {
            "evidence": "selected pixel requests",
            "value": request_summary(selected_trace),
        },
        {
            "evidence": "local index or TIFF copies",
            "value": "index=0, TIFF=0, files above 140 MB=0",
        },
    ]
    index_identity = [
        {"property": "immutable mirror", "value": INDEX_ORIGIN},
        {"property": "source record", "value": "Zenodo 19373370"},
        {"property": "expected object", "value": f"{INDEX_SIZE:,} bytes"},
        {"property": "content identity", "value": INDEX_HASH},
        {
            "property": "checksum boundary",
            "value": "Range scans do not read enough bytes to verify the full SHA-256.",
        },
    ]
    mo.vstack(
        [
            mo.md("## What was read"),
            mo.callout(
                mo.md(
                    "Verified: labeled uint16 channels, bounded TIFF requests, "
                    "no full-object TIFF GET, and no local index or TIFF copy."
                ),
                kind="success",
            ),
            mo.ui.table(evidence, pagination=False, selection=None),
            mo.accordion(
                {
                    "Image index identity": mo.ui.table(
                        index_identity,
                        pagination=False,
                        selection=None,
                    ),
                    "Original TIFF URLs": mo.ui.table(
                        channel_url_rows(selected_row),
                        pagination=False,
                        selection=None,
                    ),
                }
            ),
            mo.md(
                "Virtualization replaces local TIFF copies with small references "
                "and reads only selected TIFF ranges. Exact pixel compatibility "
                "is claimed only for Source_8's validated layout."
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
