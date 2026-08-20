# /// script
# requires-python = ">=3.11,<3.15"
# dependencies = [
#     "altair>=6,<7",
#     "anywidget>=0.9.18,<1",
#     "jump-portrait @ git+https://github.com/broadinstitute/monorepo.git@5b65c46243925949a0a49e0afcd6d49566d5bce7#subdirectory=libs/jump_portrait",
#     "marimo==0.23.16",
#     "numpy>=2.1.2,<3",
#     "pillow>=11,<13",
#     "pyarrow>=23,<26",
#     "traitlets>=5.14,<6",
# ]
# ///

"""Browse public JUMP images without downloading TIFFs."""

import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")

with app.setup:
    import base64
    from contextlib import chdir
    from functools import lru_cache
    from io import BytesIO
    from pathlib import Path
    from tempfile import TemporaryDirectory

    import altair as alt
    import anywidget
    import marimo as mo
    import numpy as np
    import pyarrow as pa
    import traitlets
    from PIL import Image

    from jump_portrait import (
        CHANNELS,
        RequestTrace,
        UnsupportedTIFFLayoutError,
        get_item_location_metadata,
        get_jump_image_site_from_metadata,
    )

    CHANNEL_COLORS = {
        "AGP": np.array([1.0, 0.50, 0.0]),
        "DNA": np.array([0.0, 0.0, 1.0]),
        "ER": np.array([0.0, 1.0, 0.0]),
        "Mito": np.array([1.0, 0.0, 0.0]),
        "RNA": np.array([1.0, 1.0, 0.0]),
    }
    LOCATION_FIELDS = ("Source", "Batch", "Plate", "Well", "Site")
    RECORD_FIELDS = tuple(f"Metadata_{field}" for field in LOCATION_FIELDS) + tuple(
        f"URL_Orig{channel}" for channel in CHANNELS
    )
    VERIFIED_LOCATION = ("source_8", "J3", "A1166127", "A01", 1)
    VERIFIED_INCHIKEY = "KBPLFHHGFOOTCA-UHFFFAOYSA-N"
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
        key=lambda row: (
            *(str(row[f"Metadata_{field}"]) for field in LOCATION_FIELDS[:-1]),
            int(row["Metadata_Site"]),
        ),
    )


@app.function
def record_key(record: dict[str, object]) -> tuple[tuple[str, str], ...]:
    """Make a selected metadata row hashable for the field cache."""
    return tuple((field, str(record[field])) for field in RECORD_FIELDS)


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
def normalize_channel(channel: object, percentile: float) -> np.ndarray:
    """Scale one channel to the shared display percentile."""
    values = np.asarray(channel, dtype=np.float32)
    upper = max(float(np.percentile(values, percentile)), 1.0)
    return np.clip(values / upper, 0.0, 1.0)


@app.function
def image_data_url(image: np.ndarray) -> str:
    """Encode a rendered image for the client-side viewer."""
    buffer = BytesIO()
    pixels = (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)
    Image.fromarray(pixels).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@app.function
def rendered_images(
    pixels: object,
    view: str,
    percentile: float,
) -> list[tuple[str, np.ndarray]]:
    """Return composite, single-channel, or small-multiple display arrays."""
    colorized = {
        channel: normalize_channel(pixels.sel(channel=channel), percentile)[..., None]
        * CHANNEL_COLORS[channel]
        for channel in CHANNELS
    }
    if view == "Composite":
        composite = np.clip(sum(colorized.values()), 0.0, 1.0)
        return [("Five-channel composite", composite)]
    if view == "Small multiples":
        return [(channel, colorized[channel]) for channel in CHANNELS]
    return [(view, colorized[view])]


@app.cell
def _():
    class _PanZoomGallery(anywidget.AnyWidget):
        _esm = r"""
        function render({ model, el }) {
          const root = document.createElement("div");
          root.className = "panzoom-root";
          const grid = document.createElement("div");
          grid.className = "panzoom-grid";
          root.append(grid);
          el.replaceChildren(root);

          let viewports = [];
          let images = [];
          let resets = [];
          let scale = 1;
          let x = 0;
          let y = 0;
          let dragging = false;
          let lastX = 0;
          let lastY = 0;

          function clampPosition() {
            const viewport = viewports[0];
            if (!viewport) return;
            x = Math.min(0, Math.max(viewport.clientWidth * (1 - scale), x));
            y = Math.min(0, Math.max(viewport.clientHeight * (1 - scale), y));
          }

          function draw() {
            clampPosition();
            const transform = `translate(${x}px, ${y}px) scale(${scale})`;
            const cursor = scale > 1 ? (dragging ? "grabbing" : "grab") : "zoom-in";
            images.forEach((image) => { image.style.transform = transform; });
            resets.forEach((reset) => { reset.textContent = `${scale.toFixed(1)}x`; });
            viewports.forEach((viewport) => { viewport.style.cursor = cursor; });
          }

          function resetView() {
            scale = 1;
            x = 0;
            y = 0;
            draw();
          }

          function rebuild() {
            const srcs = model.get("srcs");
            const labels = model.get("labels");
            const context = model.get("context");
            grid.replaceChildren();
            grid.style.setProperty("--columns", model.get("columns"));
            grid.style.setProperty("--aspect", model.get("aspect"));
            root.classList.toggle("single", srcs.length === 1);
            viewports = [];
            images = [];
            resets = [];

            srcs.forEach((src, index) => {
              const tile = document.createElement("div");
              tile.className = "panzoom-tile";
              const viewport = document.createElement("div");
              viewport.className = "panzoom-viewport";
              viewport.tabIndex = 0;
              const image = document.createElement("img");
              image.className = "panzoom-image";
              image.src = src;
              image.alt = `${labels[index]} for ${context}`;
              image.draggable = false;
              const reset = document.createElement("button");
              reset.className = "panzoom-reset";
              reset.type = "button";
              reset.title = "Reset zoom and position";
              const label = document.createElement("div");
              label.className = "panzoom-label";
              label.textContent = labels[index];
              viewport.setAttribute(
                "aria-label",
                `${image.alt}. Wheel to zoom, drag to pan, double-click to reset.`
              );
              viewport.addEventListener("wheel", zoom, { passive: false });
              viewport.addEventListener("pointerdown", startPan);
              viewport.addEventListener("pointermove", pan);
              viewport.addEventListener("pointerup", stopPan);
              viewport.addEventListener("pointercancel", stopPan);
              viewport.addEventListener("dblclick", resetView);
              reset.addEventListener("click", resetView);
              viewport.append(image, reset);
              tile.append(viewport, label);
              grid.append(tile);
              viewports.push(viewport);
              images.push(image);
              resets.push(reset);
            });
            resetView();
          }

          function zoom(event) {
            event.preventDefault();
            const rect = event.currentTarget.getBoundingClientRect();
            const pointX = event.clientX - rect.left;
            const pointY = event.clientY - rect.top;
            const next = Math.min(8, Math.max(1, scale * Math.exp(-event.deltaY * 0.0015)));
            if (next === 1) {
              resetView();
              return;
            }
            const ratio = next / scale;
            x = pointX - (pointX - x) * ratio;
            y = pointY - (pointY - y) * ratio;
            scale = next;
            draw();
          }

          function startPan(event) {
            if (scale === 1) return;
            dragging = true;
            lastX = event.clientX;
            lastY = event.clientY;
            event.currentTarget.setPointerCapture(event.pointerId);
            draw();
          }

          function pan(event) {
            if (!dragging) return;
            x += event.clientX - lastX;
            y += event.clientY - lastY;
            lastX = event.clientX;
            lastY = event.clientY;
            draw();
          }

          function stopPan() {
            dragging = false;
            draw();
          }

          ["srcs", "labels", "columns", "aspect", "context"].forEach((name) => {
            model.on(`change:${name}`, rebuild);
          });
          rebuild();

          return () => {
            ["srcs", "labels", "columns", "aspect", "context"].forEach((name) => {
              model.off(`change:${name}`, rebuild);
            });
          };
        }

        export default { render };
        """
        _css = r"""
        .panzoom-root {
          width: 100%;
          margin: 0 auto;
        }
        .panzoom-root.single {
          max-width: 920px;
        }
        .panzoom-grid {
          display: grid;
          grid-template-columns: repeat(var(--columns), minmax(0, 1fr));
          gap: 8px;
        }
        .panzoom-viewport {
          position: relative;
          width: 100%;
          aspect-ratio: var(--aspect);
          overflow: hidden;
          border-radius: 4px;
          background: #f3f4f6;
          touch-action: none;
          user-select: none;
        }
        .panzoom-image {
          display: block;
          width: 100%;
          height: 100%;
          object-fit: contain;
          transform-origin: 0 0;
          will-change: transform;
          pointer-events: none;
        }
        .panzoom-label {
          padding-top: 4px;
          color: #64748b;
          text-align: center;
        }
        .panzoom-reset {
          position: absolute;
          top: 8px;
          right: 8px;
          min-width: 44px;
          padding: 3px 8px;
          border: 1px solid rgb(255 255 255 / 70%);
          border-radius: 999px;
          color: #111827;
          background: rgb(255 255 255 / 85%);
          font: 12px ui-monospace, monospace;
          cursor: pointer;
        }
        .panzoom-reset:hover {
          background: white;
        }
        @media (prefers-color-scheme: dark) {
          .panzoom-viewport {
            background: #111827;
          }
          .panzoom-reset {
            border-color: rgb(17 24 39 / 70%);
            color: #f9fafb;
            background: rgb(17 24 39 / 85%);
          }
          .panzoom-reset:hover {
            background: #111827;
          }
        }
        """

        srcs = traitlets.List(traitlets.Unicode()).tag(sync=True)
        labels = traitlets.List(traitlets.Unicode()).tag(sync=True)
        columns = traitlets.Int(1).tag(sync=True)
        aspect = traitlets.Float(2.0).tag(sync=True)
        context = traitlets.Unicode().tag(sync=True)

    pan_zoom_gallery = _PanZoomGallery
    return (pan_zoom_gallery,)


@app.cell
def _():
    @lru_cache(maxsize=8)
    def load_field(
        key: tuple[tuple[str, str], ...],
        audit_directory: str,
        row_limit: int | None,
    ) -> tuple[object, dict[str, object], dict[str, object], dict[str, object]]:
        record = dict(key)
        trace = RequestTrace()
        with chdir(audit_directory):
            image = get_jump_image_site_from_metadata(record, trace=trace)
        construction = trace_snapshot(trace)
        pixel_start = len(trace.requests)
        y_stop = min(row_limit or int(image.sizes["y"]), int(image.sizes["y"]))
        with chdir(audit_directory):
            pixels = image.isel(y=slice(0, y_stop)).compute()
        selected_read = trace_snapshot(trace, start=pixel_start)
        attrs = dict(image.attrs)
        attrs["logical_shape"] = tuple(int(length) for length in image.shape)
        attrs["logical_dtype"] = str(image.dtype)
        return pixels, attrs, construction, selected_read

    return (load_field,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Browse original JUMP images

    Search a gene, InChIKey, or JCP2022 identifier, choose a plate and well,
    and inspect one field at a time. The default is a five-channel Cell Painting
    composite. Pixels stay remote until the selected field is opened.
    """)
    return


@app.cell
def _():
    is_script_mode = mo.app_meta().mode == "script"
    audit_workspace = TemporaryDirectory(prefix="jump-portrait-browser-")
    audit_directory = Path(audit_workspace.name)
    return audit_directory, audit_workspace, is_script_mode


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
                placeholder="RAB30, an InChIKey, or JCP2022_043547",
                label="",
                full_width=True,
            ),
        )
        .form(submit_button_label="Find images")
    )
    mo.vstack(
        [
            query_form,
            mo.md(f"Validated examples: `JCP2022_043547` and `{VERIFIED_INCHIKEY}`."),
        ]
    )
    return (query_form,)


@app.cell
def _(query_form, is_script_mode):
    query_value = (
        {"input_column": "JCP2022", "item_name": "JCP2022_043547"}
        if is_script_mode
        else query_form.value
    )
    mo.stop(
        query_value is None,
        mo.callout(mo.md("Submit an identifier to find image fields."), kind="info"),
    )
    item_name = str(query_value["item_name"]).strip()
    mo.stop(
        not item_name,
        mo.callout(mo.md("Enter an identifier before searching."), kind="warn"),
    )
    input_column = str(query_value["input_column"])
    return input_column, item_name


@app.cell
def _(audit_directory, input_column, is_script_mode, item_name):
    with chdir(audit_directory):
        metadata = get_item_location_metadata(item_name, input_column=input_column)
        inchi_metadata = (
            get_item_location_metadata(VERIFIED_INCHIKEY) if is_script_mode else None
        )
    records = metadata_records(metadata)
    mo.stop(
        not records,
        mo.callout(
            mo.md(f"No image fields were returned for `{item_name}`."), kind="warn"
        ),
    )
    if inchi_metadata is not None:
        inchi_records = metadata_records(inchi_metadata)
        assert any(row["Metadata_Source"] == "source_8" for row in inchi_records)
    return (records,)


@app.cell(hide_code=True)
def _(records):
    plates = sorted(
        {
            (
                str(row["Metadata_Source"]),
                str(row["Metadata_Batch"]),
                str(row["Metadata_Plate"]),
            )
            for row in records
        }
    )
    plate_options = {
        " / ".join(location): index for index, location in enumerate(plates)
    }
    default_plate_index = next(
        (
            index
            for index, location in enumerate(plates)
            if location == VERIFIED_LOCATION[:3]
        ),
        next(
            (
                index
                for index, location in enumerate(plates)
                if location[0] == "source_8"
            ),
            0,
        ),
    )
    default_plate_label = next(
        label for label, index in plate_options.items() if index == default_plate_index
    )
    plate_control = mo.ui.dropdown(
        options=plate_options,
        value=default_plate_label,
        searchable=True,
        label="Source / batch / plate",
        full_width=True,
    )
    sources = {str(row["Metadata_Source"]) for row in records}
    batches = {
        (str(row["Metadata_Source"]), str(row["Metadata_Batch"])) for row in records
    }
    wells = {
        (
            str(row["Metadata_Source"]),
            str(row["Metadata_Batch"]),
            str(row["Metadata_Plate"]),
            str(row["Metadata_Well"]),
        )
        for row in records
    }
    source_8_fields = sum(row["Metadata_Source"] == "source_8" for row in records)
    mo.vstack(
        [
            mo.md(
                f"**{len(records):,} fields** across **{len(wells):,} wells**, "
                f"**{len(plates):,} plates**, **{len(batches):,} batches**, and "
                f"**{len(sources):,} sources**. Source_8 fields with exact "
                f"pixel validation: **{source_8_fields:,}**."
            ),
            plate_control,
        ]
    )
    return plate_control, plates


@app.cell
def _(plate_control, plates, records):
    selected_plate = plates[int(plate_control.value)]
    plate_records = [
        row
        for row in records
        if tuple(
            str(row[f"Metadata_{field}"]) for field in ("Source", "Batch", "Plate")
        )
        == selected_plate
    ]
    available_wells = sorted({str(row["Metadata_Well"]) for row in plate_records})
    default_well = (
        VERIFIED_LOCATION[3]
        if selected_plate == VERIFIED_LOCATION[:3]
        else available_wells[0]
    )
    return available_wells, default_well, plate_records, selected_plate


@app.cell(hide_code=True)
def _(available_wells, default_well, plate_records, selected_plate):
    field_counts: dict[str, int] = {}
    for row in plate_records:
        well = str(row["Metadata_Well"])
        field_counts[well] = field_counts.get(well, 0) + 1
    plate_frame = pa.Table.from_pylist(
        [
            {
                "row": row,
                "column": column,
                "well": f"{row}{column:02d}",
                "fields": field_counts.get(f"{row}{column:02d}", 0),
            }
            for row in "ABCDEFGHIJKLMNOP"
            for column in range(1, 25)
        ]
    )
    chart = (
        alt.Chart(plate_frame)
        .mark_rect(cornerRadius=3, stroke="white")
        .encode(
            x=alt.X("column:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(
                "row:O",
                title=None,
                sort=list("ABCDEFGHIJKLMNOP"),
            ),
            color=alt.Color(
                "fields:Q",
                title="Fields",
                scale=alt.Scale(domain=[0, max(field_counts.values())]),
            ),
            tooltip=["well:N", "fields:Q"],
        )
        .properties(width=720, height=360)
    )
    plate_map = mo.ui.altair_chart(
        chart,
        chart_selection="point",
        label="Click a well",
    )
    mo.hstack(
        [
            plate_map,
            mo.vstack(
                [
                    mo.md(
                        "### Choose a well\n\n"
                        "Blue wells contain the query. Click one to list its "
                        "available sites."
                    ),
                    mo.md(
                        f"**Plate:** `{' / '.join(selected_plate)}`\n\n"
                        f"**Default well:** `{default_well}`\n\n"
                        f"**Wells with fields:** {len(available_wells):,}"
                    ),
                ]
            ),
        ],
        widths=[3, 1],
        align="center",
    )
    return (plate_map,)


@app.cell
def _(available_wells, default_well, is_script_mode, plate_map, plate_records):
    selection = plate_map.value
    selected_well = (
        default_well
        if is_script_mode or selection.num_rows == 0
        else str(selection["well"][-1].as_py())
    )
    mo.stop(
        selected_well not in available_wells,
        mo.callout(
            mo.md(f"`{selected_well}` has no fields for this query."), kind="info"
        ),
    )
    well_records = [
        row for row in plate_records if str(row["Metadata_Well"]) == selected_well
    ]
    return selected_well, well_records


@app.cell(hide_code=True)
def _(selected_well, well_records):
    sites = sorted(int(row["Metadata_Site"]) for row in well_records)
    site_control = mo.ui.number(
        start=min(sites),
        stop=max(sites),
        step=1,
        value=sites[0],
        label="Site - type a number or use the previous/next arrows",
    )
    mo.hstack(
        [
            mo.md(
                f"### `{selected_well}`\n\n"
                f"Available sites: {', '.join(str(site) for site in sites)}"
            ),
            site_control,
        ],
        widths=[3, 2],
        align="center",
    )
    return site_control, sites


@app.cell
def _(site_control, sites, well_records):
    selected_site = int(site_control.value)
    mo.stop(
        selected_site not in sites,
        mo.callout(
            mo.md(f"Site `{selected_site}` is not available in this well."),
            kind="warn",
        ),
    )
    selected_row = next(
        row for row in well_records if int(row["Metadata_Site"]) == selected_site
    )
    return selected_row, selected_site


@app.cell(hide_code=True)
def _():
    view_control = mo.ui.dropdown(
        options=["Composite", *CHANNELS, "Small multiples"],
        value="Composite",
        label="View",
    )
    contrast_control = mo.ui.slider(
        start=95.0,
        stop=100.0,
        step=0.1,
        value=99.5,
        label="Shared contrast percentile - reset to 99.5",
        show_value=True,
        full_width=True,
    )
    full_frame_control = mo.ui.switch(
        value=False,
        label="Full square (2x pixel bytes)",
    )
    mo.hstack(
        [view_control, full_frame_control, contrast_control],
        widths=[1, 1, 3],
        align="center",
    )
    return contrast_control, full_frame_control, view_control


@app.cell
def _(audit_directory, full_frame_control, load_field, selected_row):
    key = record_key(selected_row)
    row_limit = None if full_frame_control.value else 512
    cache_before = load_field.cache_info()
    try:
        field_result = load_field(key, str(audit_directory), row_limit)
        load_error = None
    except UnsupportedTIFFLayoutError as error:
        field_result = None
        load_error = str(error)
    cache_after = load_field.cache_info()
    cache_hit = cache_after.hits > cache_before.hits
    return cache_after, cache_hit, field_result, load_error


@app.cell
def _(field_result, load_error):
    mo.stop(
        load_error is not None,
        mo.callout(
            mo.md(
                f"**This field cannot be opened lazily.**\n\n{load_error}\n\n"
                "No eager fallback was attempted. Choose another field."
            ),
            kind="warn",
        ),
    )
    assert field_result is not None
    pixels, image_attrs, construction_trace, pixel_trace = field_result
    return construction_trace, image_attrs, pixel_trace, pixels


@app.cell(hide_code=True)
def _(
    cache_after,
    cache_hit,
    contrast_control,
    image_attrs,
    pixel_trace,
    pixels,
    selected_plate,
    selected_site,
    selected_well,
    pan_zoom_gallery,
    view_control,
):
    view = str(view_control.value)
    percentile = float(contrast_control.value)
    images = rendered_images(pixels, view, percentile)
    height, width = (int(pixels.sizes[axis]) for axis in ("y", "x"))
    image_surface = mo.ui.anywidget(
        pan_zoom_gallery(
            srcs=[image_data_url(image) for _, image in images],
            labels=[label for label, _ in images],
            columns=3 if len(images) > 1 else 1,
            aspect=width / height,
            context=f"{selected_well} site {selected_site}",
        )
    )
    full_height = int(image_attrs["logical_shape"][1])
    status = (
        f"{int(pixel_trace['requests'])} pixel ranges - "
        f"{format_bytes(int(pixel_trace['requested_bytes']))} - "
        f"actual envelope rows 0:{height} of {full_height}, columns 0:{width} - "
        f"{int(pixel_trace['full_gets'])} full-object GETs - "
        f"cache {'hit' if cache_hit else 'miss'} "
        f"({cache_after.currsize}/8 fields)"
    )
    location = " / ".join([*selected_plate, selected_well, f"site {selected_site}"])
    mo.vstack(
        [
            mo.md(
                f"## {location}\n\n"
                f"**{view} at percentile {percentile:.1f} - "
                f"{width} x {height} pixels**\n\n"
                "Wheel to zoom, drag to pan, or double-click to reset. "
                "Small multiples stay synchronized."
            ),
            image_surface,
            mo.callout(mo.md(status), kind="info"),
        ],
        align="center",
    )
    return height, percentile, status, view, width


@app.cell(hide_code=True)
def _(
    audit_directory,
    construction_trace,
    image_attrs,
    pixel_trace,
    pixels,
    selected_row,
    status,
):
    artifacts = audit_artifacts(audit_directory)
    channel_urls = [
        {"channel": channel, "original TIFF": selected_row[f"URL_Orig{channel}"]}
        for channel in CHANNELS
    ]
    request_rows = [
        {
            "phase": "virtual construction",
            "requests": construction_trace["requests"],
            "requested": format_bytes(int(construction_trace["requested_bytes"])),
            "methods": ", ".join(sorted(set(construction_trace["methods"]))),
            "full GETs": construction_trace["full_gets"],
        },
        {
            "phase": "selected pixels",
            "requests": pixel_trace["requests"],
            "requested": format_bytes(int(pixel_trace["requested_bytes"])),
            "methods": ", ".join(sorted(set(pixel_trace["methods"]))),
            "full GETs": pixel_trace["full_gets"],
        },
    ]
    compatibility = [
        {
            "scope": "Source_8",
            "evidence": "exact eager/lazy equality, all five channels",
            "claim": "validated uncompressed strip layout",
        },
        {
            "scope": "Sources 2, 5, 7, 10, 13",
            "evidence": "one-field layout probe only",
            "claim": "no source-wide pixel claim",
        },
        {
            "scope": "Sources 3, 4, 9, 11",
            "evidence": "probe rejected LZW compression",
            "claim": "unsupported; no eager fallback",
        },
        {
            "scope": "Source_6",
            "evidence": "probe rejected a partial final strip",
            "claim": "unsupported; no eager fallback",
        },
    ]
    index_identity = [
        {"property": "immutable mirror", "value": INDEX_ORIGIN},
        {"property": "source record", "value": "Zenodo 19373370"},
        {"property": "expected object", "value": f"{INDEX_SIZE:,} bytes"},
        {"property": "content identity", "value": INDEX_HASH},
        {
            "property": "checksum boundary",
            "value": "Range scans do not read enough bytes to verify full SHA-256.",
        },
    ]
    implementation = [
        {
            "property": "logical array",
            "value": (
                f"shape={image_attrs['logical_shape']}, "
                f"dtype={image_attrs['logical_dtype']}"
            ),
        },
        {
            "property": "virtual chunks",
            "value": str(image_attrs["virtual_chunk_shape"]),
        },
        {
            "property": "virtual references",
            "value": (
                f"count={image_attrs['virtual_reference_count']}, "
                f"size={format_bytes(int(image_attrs['virtual_reference_bytes']))}"
            ),
        },
        {"property": "selected read", "value": status},
        {
            "property": "local artifacts",
            "value": "image index=0, TIFF=0, files above 140 MB=0",
        },
    ]
    assert tuple(pixels.dims) == ("channel", "y", "x")
    assert pixels.coords["channel"].values.tolist() == list(CHANNELS)
    assert str(pixels.dtype) == "uint16"
    assert int(construction_trace["full_gets"]) == 0
    assert int(pixel_trace["full_gets"]) == 0
    assert not artifacts["image_indexes"]
    assert not artifacts["tiffs"]
    assert not artifacts["large_files"]
    assert image_attrs["image_index_origin"] is None
    assert tuple(image_attrs["virtual_chunk_shape"]) == (1, 128, 1024)
    assert len(rendered_images(pixels, "Composite", 99.5)) == 1
    assert len(rendered_images(pixels, "DNA", 99.5)) == 1
    assert len(rendered_images(pixels, "Small multiples", 99.5)) == 5
    mo.accordion(
        {
            "Read evidence": mo.vstack(
                [
                    mo.ui.table(request_rows, pagination=False, selection=None),
                    mo.ui.table(implementation, pagination=False, selection=None),
                ]
            ),
            "Image index and original TIFF URLs": mo.vstack(
                [
                    mo.ui.table(index_identity, pagination=False, selection=None),
                    mo.ui.table(channel_urls, pagination=False, selection=None),
                ]
            ),
            "Compatibility boundary": mo.ui.table(
                compatibility,
                pagination=False,
                selection=None,
            ),
        }
    )
    return


if __name__ == "__main__":
    app.run()
