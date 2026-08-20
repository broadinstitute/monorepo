# /// script
# requires-python = ">=3.11,<3.15"
# dependencies = [
#     "altair>=6,<7",
#     "anywidget>=0.9.18,<1",
#     "broad-babel>=0.1.31",
#     "duckdb>=1.4.4,<2",
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
    from time import perf_counter

    import altair as alt
    import anywidget
    import duckdb
    import marimo as mo
    import numpy as np
    import pyarrow as pa
    import traitlets
    from broad_babel.data import get_table
    from PIL import Image

    from jump_portrait import (
        CHANNELS,
        RequestTrace,
        UnsupportedTIFFLayoutError,
        get_item_location_metadata,
        get_jump_image_site,
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
    VERIFIED_NEGATIVE_CONTROLS = {
        # Canonical Metadata_pert_type=negcon rows from perturbation_control.csv
        # at jump-cellpainting/datasets commit 016e865fa0691244e0860943e41c7d6a88ed2580.
        "JCP2022_033924": "DMSO",
        "JCP2022_800001": "no-guide",
        "JCP2022_800002": "non-targeting",
        "JCP2022_915128": "BFP",
        "JCP2022_915129": "HcRed",
        "JCP2022_915130": "LUCIFERASE",
        "JCP2022_915131": "LacZ",
    }


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
    return tuple(
        (field, str(record[field]))
        for field in RECORD_FIELDS
        if record.get(field) is not None
    )


@app.function
def well_coordinates(well: str) -> tuple[int, int]:
    """Return zero-based row and column coordinates for a plate well label."""
    normalized = well.strip().upper()
    split = next(
        (index for index, character in enumerate(normalized) if character.isdigit()),
        len(normalized),
    )
    letters, digits = normalized[:split], normalized[split:]
    if not letters or not letters.isalpha() or not digits or not digits.isdigit():
        raise ValueError(f"Invalid plate-well coordinate: {well!r}")
    row = 0
    for letter in letters:
        row = row * 26 + ord(letter) - ord("A") + 1
    row -= 1
    column = int(digits) - 1
    if column < 0:
        raise ValueError(f"Invalid plate-well coordinate: {well!r}")
    return row, column


@app.function
def plate_row_label(index: int) -> str:
    """Convert a zero-based plate row index to A, ..., Z, AA, ...."""
    if index < 0:
        raise ValueError(f"Plate row index must be non-negative: {index}")
    label = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        label = chr(ord("A") + remainder) + label
    return label


@app.function
def row_major_wells(wells: object) -> list[str]:
    """Return unique well labels in deterministic row-major order."""
    return sorted({str(well) for well in wells}, key=well_coordinates)


@app.function
def nearest_well(current: str, candidates: object) -> str | None:
    """Choose the nearest well by Manhattan distance, then row-major order."""
    ordered = row_major_wells(candidates)
    if not ordered:
        return None
    current_row, current_column = well_coordinates(current)
    return min(
        ordered,
        key=lambda well: (
            abs(well_coordinates(well)[0] - current_row)
            + abs(well_coordinates(well)[1] - current_column),
            well_coordinates(well),
        ),
    )


@app.function
def adjacent_well(current: str, wells: object, offset: int) -> str | None:
    """Return a previous or next populated well without wrapping row edges."""
    ordered = row_major_wells(wells)
    if current not in ordered:
        return None
    index = ordered.index(current) + offset
    return ordered[index] if 0 <= index < len(ordered) else None


@app.function
def closest_site(sites: object, preferred: int) -> int:
    """Keep a site number when available, otherwise use its nearest neighbor."""
    available = sorted({int(site) for site in sites})
    if not available:
        raise ValueError("A populated well must have at least one site")
    return min(available, key=lambda site: (abs(site - preferred), site))


@app.function
def chart_selected_well(selection: object) -> str | None:
    """Extract the last selected well from a marimo Altair selection."""
    if selection is None or selection.num_rows == 0:
        return None
    return str(selection["well"][-1].as_py())


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
          // Preserve geometry while anywidget replaces its stylesheet on reruns.
          root.style.width = "100%";
          root.style.margin = "0 auto";
          const grid = document.createElement("div");
          grid.className = "panzoom-grid";
          grid.style.display = "grid";
          grid.style.gap = "8px";
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
            root.style.maxWidth = srcs.length === 1 ? "920px" : "";
            grid.style.gridTemplateColumns =
              `repeat(${model.get("columns")}, minmax(0, 1fr))`;
            viewports = [];
            images = [];
            resets = [];

            srcs.forEach((src, index) => {
              const tile = document.createElement("div");
              tile.className = "panzoom-tile";
              const viewport = document.createElement("div");
              viewport.className = "panzoom-viewport";
              viewport.style.position = "relative";
              viewport.style.width = "100%";
              viewport.style.aspectRatio = model.get("aspect");
              viewport.style.overflow = "hidden";
              viewport.tabIndex = 0;
              const image = document.createElement("img");
              image.className = "panzoom-image";
              image.style.display = "block";
              image.style.width = "100%";
              image.style.height = "100%";
              image.style.objectFit = "contain";
              image.src = src;
              image.alt = `${labels[index]} for ${context}`;
              image.draggable = false;
              const reset = document.createElement("button");
              reset.className = "panzoom-reset";
              reset.style.position = "absolute";
              reset.style.top = "8px";
              reset.style.right = "8px";
              reset.type = "button";
              reset.title = "Reset zoom and position";
              const label = document.createElement("div");
              label.className = "panzoom-label";
              label.style.paddingTop = "4px";
              label.style.textAlign = "center";
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
    def load_plate_context(
        source: str,
        batch: str,
        plate: str,
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        start = perf_counter()
        well_metadata_path = get_table("well")
        with duckdb.connect() as connection:
            connection.execute("SET enable_external_file_cache=false")
            connection.execute(
                "CALL enable_logging('HTTP', storage_config={'buffer_size': 0})"
            )
            table = connection.execute(
                """
                WITH plate_sites AS (
                    SELECT
                        Metadata_Source,
                        Metadata_Batch,
                        Metadata_Plate,
                        Metadata_Well,
                        Metadata_Site
                    FROM read_parquet(?)
                    WHERE Metadata_Source = ?
                      AND Metadata_Batch = ?
                      AND Metadata_Plate = ?
                ),
                plate_wells AS (
                    SELECT
                        Metadata_Source,
                        Metadata_Plate,
                        Metadata_Well,
                        Metadata_JCP2022
                    FROM read_csv_auto(?)
                    WHERE Metadata_Source = ?
                      AND Metadata_Plate = ?
                )
                SELECT
                    sites.Metadata_Source,
                    sites.Metadata_Batch,
                    sites.Metadata_Plate,
                    sites.Metadata_Well,
                    sites.Metadata_Site,
                    wells.Metadata_JCP2022
                FROM plate_sites AS sites
                LEFT JOIN plate_wells AS wells
                    USING (Metadata_Source, Metadata_Plate, Metadata_Well)
                ORDER BY sites.Metadata_Well, sites.Metadata_Site
                """,
                [
                    INDEX_ORIGIN,
                    source,
                    batch,
                    plate,
                    well_metadata_path,
                    source,
                    plate,
                ],
            ).to_arrow_table()
            logs = connection.execute(
                """
                SELECT
                    request.type,
                    map_extract_value(request.headers, 'Range'),
                    map_extract_value(response.headers, 'Content-Length')
                FROM duckdb_logs_parsed('HTTP')
                """
            ).fetchall()

        records = table.to_pylist()
        for record in records:
            identifier = str(record.get("Metadata_JCP2022") or "")
            control_name = VERIFIED_NEGATIVE_CONTROLS.get(identifier)
            record["Metadata_ControlType"] = (
                "negcon" if control_name is not None else None
            )
            record["Metadata_ControlName"] = control_name

        get_lengths = [
            int(length)
            for method, _byte_range, length in logs
            if method == "GET" and length is not None
        ]
        trace = {
            "requests": len(logs),
            "range_gets": sum(
                method == "GET" and byte_range is not None
                for method, byte_range, _length in logs
            ),
            "requested_bytes": sum(get_lengths),
            "full_gets": sum(
                method == "GET" and byte_range is None
                for method, byte_range, _length in logs
            ),
            "elapsed_seconds": perf_counter() - start,
            "index_size": INDEX_SIZE,
        }
        return records, trace

    return (load_plate_context,)


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
            if all(record.get(f"URL_Orig{channel}") for channel in CHANNELS):
                image = get_jump_image_site_from_metadata(record, trace=trace)
            else:
                image = get_jump_image_site(
                    source=record["Metadata_Source"],
                    batch=record["Metadata_Batch"],
                    plate=record["Metadata_Plate"],
                    well=record["Metadata_Well"],
                    site=int(record["Metadata_Site"]),
                    trace=trace,
                )
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


@app.cell
def _():
    get_selected_location, set_selected_location = mo.state(("", "", "", ""))
    get_preferred_site, set_preferred_site = mo.state(VERIFIED_LOCATION[4])
    get_unsupported_wells, set_unsupported_wells = mo.state(frozenset())
    return (
        get_preferred_site,
        get_selected_location,
        get_unsupported_wells,
        set_preferred_site,
        set_selected_location,
        set_unsupported_wells,
    )


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Browse original JUMP images

    Search a gene, InChIKey, or JCP2022 identifier and inspect one field at a
    time. A sole matching well opens automatically. **Explore plate** adds
    same-plate metadata and navigation without prefetching pixels. The default
    view is a five-channel Cell Painting composite.
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
    inchi_records = (
        metadata_records(inchi_metadata) if inchi_metadata is not None else []
    )
    if inchi_records:
        assert any(row["Metadata_Source"] == "source_8" for row in inchi_records)
    return inchi_records, records


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
    query_wells = row_major_wells(row["Metadata_Well"] for row in plate_records)
    automatic_well = query_wells[0] if len(query_wells) == 1 else None
    return automatic_well, plate_records, query_wells, selected_plate


@app.cell
def _(is_script_mode, selected_plate):
    explore_plate_control = mo.ui.button(
        value=is_script_mode,
        on_click=lambda _value: True,
        label="Explore plate",
        tooltip=(
            f"Load well and site metadata for {' / '.join(selected_plate)} only; "
            "no image pixels are prefetched."
        ),
    )
    return (explore_plate_control,)


@app.cell
def _(explore_plate_control, is_script_mode, load_plate_context, selected_plate):
    explore_enabled = is_script_mode or bool(explore_plate_control.value)
    if explore_enabled:
        plate_cache_before = load_plate_context.cache_info()
        plate_context_records, plate_context_trace = load_plate_context(*selected_plate)
        plate_cache_after = load_plate_context.cache_info()
        plate_cache_hit = plate_cache_after.hits > plate_cache_before.hits
    else:
        plate_context_records = []
        plate_context_trace = {
            "requests": 0,
            "range_gets": 0,
            "requested_bytes": 0,
            "full_gets": 0,
            "elapsed_seconds": 0.0,
            "index_size": INDEX_SIZE,
        }
        plate_cache_hit = False
    return (
        explore_enabled,
        plate_cache_hit,
        plate_context_records,
        plate_context_trace,
    )


@app.cell
def _(
    automatic_well,
    explore_enabled,
    get_selected_location,
    plate_context_records,
    query_wells,
    selected_plate,
):
    populated_wells = row_major_wells(
        row["Metadata_Well"] for row in plate_context_records
    )
    selectable_wells = populated_wells if explore_enabled else query_wells
    selected_location = get_selected_location()
    state_well = (
        str(selected_location[3])
        if tuple(selected_location[:3]) == selected_plate
        and str(selected_location[3]) in selectable_wells
        else None
    )
    selected_well = state_well or automatic_well
    return populated_wells, selectable_wells, selected_well


@app.cell
def _(
    automatic_well,
    inchi_records,
    is_script_mode,
    load_plate_context,
    plate_context_records,
    plate_context_trace,
    selected_plate,
):
    if is_script_mode:
        assert selected_plate == VERIFIED_LOCATION[:3]
        assert automatic_well == VERIFIED_LOCATION[3]
        assert len({row["Metadata_Well"] for row in plate_context_records}) == 384
        assert len(plate_context_records) == 3_456
        assert int(plate_context_trace["full_gets"]) == 0
        assert int(plate_context_trace["requested_bytes"]) < INDEX_SIZE
        _negative_wells = {
            str(row["Metadata_Well"])
            for row in plate_context_records
            if row["Metadata_ControlType"] == "negcon"
        }
        assert nearest_well("A01", _negative_wells) == "A05"
        assert adjacent_well("A24", ["A24", "B01"], 1) == "B01"
        assert adjacent_well("B01", ["A24", "B01"], -1) == "A24"
        assert closest_site([1, 3], 2) == 1
        assert well_coordinates("Y48") == (24, 47)
        assert plate_row_label(26) == "AA"

        _multi_hit_plates: dict[tuple[str, str, str], set[str]] = {}
        for _record in inchi_records:
            _plate_key = tuple(
                str(_record[f"Metadata_{field}"])
                for field in ("Source", "Batch", "Plate")
            )
            _multi_hit_plates.setdefault(_plate_key, set()).add(
                str(_record["Metadata_Well"])
            )
        assert any(len(_wells) > 1 for _wells in _multi_hit_plates.values())

        _cache_before = load_plate_context.cache_info()
        load_plate_context(*selected_plate)
        _cache_after = load_plate_context.cache_info()
        assert _cache_after.hits == _cache_before.hits + 1

        _no_control_records, _no_control_trace = load_plate_context(
            "source_10",
            "2021_06_28_U2OS_48_hr_run9",
            "Dest210628-162003",
        )
        assert _no_control_records
        assert not any(
            _row["Metadata_ControlType"] == "negcon" for _row in _no_control_records
        )
        assert int(_no_control_trace["full_gets"]) == 0
    return


@app.cell(hide_code=True)
def _(  # noqa: C901
    explore_enabled,
    explore_plate_control,
    get_unsupported_wells,
    plate_cache_hit,
    plate_context_records,
    plate_context_trace,
    populated_wells,
    query_wells,
    selectable_wells,
    selected_plate,
    selected_well,
    set_selected_location,
):
    context_by_well: dict[str, dict[str, object]] = {}
    for record in plate_context_records:
        context_by_well.setdefault(str(record["Metadata_Well"]), record)
    unsupported_wells = {
        location[3]
        for location in get_unsupported_wells()
        if tuple(location[:3]) == selected_plate
    }

    known_wells = populated_wells if explore_enabled else query_wells
    known_coordinates = [well_coordinates(well) for well in known_wells]
    row_count = max(
        16, max((row for row, _column in known_coordinates), default=15) + 1
    )
    column_count = max(
        24,
        max((column for _row, column in known_coordinates), default=23) + 1,
    )
    row_labels = [plate_row_label(index) for index in range(row_count)]
    plate_rows = []
    for row in row_labels:
        for column in range(1, column_count + 1):
            well = f"{row}{column:02d}"
            context = context_by_well.get(well, {})
            _control_name = context.get("Metadata_ControlName")
            if well in unsupported_wells:
                category = "Unsupported"
            elif well in query_wells:
                category = "Query"
            elif _control_name is not None:
                category = "Negative control"
            elif well in populated_wells:
                category = "Other populated"
            else:
                category = "Not loaded" if not explore_enabled else "No indexed field"
            plate_rows.append(
                {
                    "row": row,
                    "column": column,
                    "well": well,
                    "category": category,
                    "current": well == selected_well,
                    "control": _control_name or "",
                    "JCP2022": context.get("Metadata_JCP2022") or "",
                }
            )

    category_order = [
        "Query",
        "Negative control",
        "Other populated",
        "Unsupported",
        "Not loaded",
        "No indexed field",
    ]
    category_colors = [
        "#2563eb",
        "#7c3aed",
        "#94a3b8",
        "#dc2626",
        "#e2e8f0",
        "#f1f5f9",
    ]
    plate_frame = pa.Table.from_pylist(plate_rows)
    chart = (
        alt.Chart(plate_frame)
        .mark_rect(cornerRadius=2)
        .encode(
            x=alt.X("column:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("row:O", title=None, sort=row_labels),
            color=alt.Color(
                "category:N",
                title=None,
                scale=alt.Scale(domain=category_order, range=category_colors),
                legend=None,
            ),
            stroke=alt.condition(
                "datum.current",
                alt.value("#111827"),
                alt.value("#ffffff"),
            ),
            strokeWidth=alt.condition(
                "datum.current",
                alt.value(3),
                alt.value(1),
            ),
            tooltip=[
                alt.Tooltip("well:N", title="Well"),
                alt.Tooltip("category:N", title="Status"),
                alt.Tooltip("control:N", title="Control"),
                alt.Tooltip("JCP2022:N", title="JCP2022"),
            ],
        )
        .properties(width="container", height=190)
    )

    def select_chart_well(selection: object) -> None:
        well = chart_selected_well(selection)
        if well in selectable_wells:
            set_selected_location((*selected_plate, well))

    plate_map = mo.ui.altair_chart(
        chart,
        chart_selection="point",
        legend_selection=False,
        label="Plate map",
        on_change=select_chart_well,
    )

    def navigation_button(
        label: str,
        target: str | None,
        tooltip: str,
    ) -> object:
        return mo.ui.button(
            value=0,
            on_click=lambda value: int(value) + 1,
            on_change=(
                (lambda _value: set_selected_location((*selected_plate, target)))
                if target is not None
                else None
            ),
            label=label,
            tooltip=tooltip,
            disabled=target is None or target == selected_well,
        )

    query_target = (
        selected_well
        if selected_well in query_wells
        else (query_wells[0] if query_wells else None)
    )
    negative_wells = row_major_wells(
        well
        for well, context in context_by_well.items()
        if context.get("Metadata_ControlType") == "negcon"
    )
    negative_target = (
        nearest_well(selected_well, negative_wells)
        if selected_well is not None and explore_enabled
        else None
    )
    previous_target = (
        adjacent_well(selected_well, populated_wells, -1)
        if selected_well is not None and explore_enabled
        else None
    )
    next_target = (
        adjacent_well(selected_well, populated_wells, 1)
        if selected_well is not None and explore_enabled
        else None
    )
    negative_label = (
        f"Nearest {context_by_well[negative_target]['Metadata_ControlName']} "
        f"{negative_target}"
        if negative_target is not None
        else "No verified negative control"
    )
    navigation = mo.hstack(
        [
            navigation_button(
                f"Query well {query_target or ''}".strip(),
                query_target,
                "Return to a query-matching well.",
            ),
            navigation_button(
                negative_label,
                negative_target,
                "Nearest by Manhattan plate distance, then row-major order.",
            ),
            navigation_button(
                f"Previous {previous_target or ''}".strip(),
                previous_target,
                "Previous populated well in row-major order.",
            ),
            navigation_button(
                f"Next {next_target or ''}".strip(),
                next_target,
                "Next populated well in row-major order.",
            ),
        ],
        justify="start",
        gap=0.5,
        wrap=True,
    )
    if explore_enabled:
        metadata_status = (
            f"{len(populated_wells):,} populated wells - "
            f"{int(plate_context_trace['range_gets']):,} metadata ranges - "
            f"{format_bytes(int(plate_context_trace['requested_bytes']))} - "
            f"{float(plate_context_trace['elapsed_seconds']):.2f} s - "
            f"{int(plate_context_trace['full_gets'])} full-index GETs - "
            f"plate cache {'hit' if plate_cache_hit else 'miss'} - "
            "0 prefetched image pixel reads"
        )
    else:
        metadata_status = (
            f"{len(query_wells):,} query wells only - 0 plate metadata requests - "
            "0 prefetched image pixel reads"
        )
    plate_layout = mo.hstack(
        [
            plate_map,
            mo.vstack(
                [
                    mo.md(
                        f"### Plate context\n\n**Plate:** `{' / '.join(selected_plate)}`\n\n"
                        f"**Current well:** `{selected_well or 'Choose a query well'}`"
                    ),
                    explore_plate_control,
                    mo.md(
                        "**Legend:** blue Query; black outline Current; purple "
                        "verified negative control; gray Other populated; red "
                        "Unsupported; pale wells not loaded or unindexed."
                    ),
                ]
            ),
        ],
        widths=[4, 2],
        align="center",
    )
    mo.vstack(
        [
            plate_layout,
            navigation,
            mo.callout(mo.md(metadata_status), kind="info"),
        ]
    )
    return metadata_status, plate_map


@app.cell
def _(plate_context_records, plate_records, selected_well):
    mo.stop(
        selected_well is None,
        mo.callout(
            mo.md("Choose one of the query wells to open a field."), kind="info"
        ),
    )
    well_records = [
        row for row in plate_records if str(row["Metadata_Well"]) == selected_well
    ]
    if not well_records:
        well_records = [
            row
            for row in plate_context_records
            if str(row["Metadata_Well"]) == selected_well
        ]
    mo.stop(
        not well_records,
        mo.callout(mo.md(f"`{selected_well}` has no indexed fields."), kind="warn"),
    )
    return (well_records,)


@app.cell(hide_code=True)
def _(
    get_preferred_site,
    item_name,
    selected_well,
    set_preferred_site,
    well_records,
):
    sites = sorted(int(row["Metadata_Site"]) for row in well_records)
    selected_site_default = closest_site(sites, get_preferred_site())
    site_control = mo.ui.number(
        start=min(sites),
        stop=max(sites),
        step=1,
        value=selected_site_default,
        label="Site - type a number or use the previous/next arrows",
        on_change=lambda value: set_preferred_site(int(value)),
    )
    identifier = str(well_records[0].get("Metadata_JCP2022") or "unknown")
    _control_name = VERIFIED_NEGATIVE_CONTROLS.get(identifier)
    identity = (
        f"{_control_name} negative control (`{identifier}`)"
        if _control_name is not None
        else (
            f"query `{item_name}` (`{identifier}`)"
            if any(row.get("standard_key") == item_name for row in well_records)
            else f"perturbation `{identifier}`"
        )
    )
    mo.hstack(
        [
            mo.md(
                f"### `{selected_well}`\n\n"
                f"**Identity:** {identity}\n\n"
                f"Available sites: {', '.join(str(site) for site in sites)}"
            ),
            site_control,
        ],
        widths=[3, 2],
        align="center",
    )
    return identity, site_control, sites


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
def _(
    audit_directory,
    full_frame_control,
    load_field,
    selected_plate,
    selected_row,
    selected_well,
    set_unsupported_wells,
):
    key = record_key(selected_row)
    row_limit = None if full_frame_control.value else 512
    cache_before = load_field.cache_info()
    try:
        field_result = load_field(key, str(audit_directory), row_limit)
        load_error = None
    except UnsupportedTIFFLayoutError as error:
        field_result = None
        load_error = str(error)
        set_unsupported_wells(
            lambda locations: locations | {(*selected_plate, selected_well)}
        )
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
    original_read = (
        f"{int(pixel_trace['requests'])} ranges / "
        f"{format_bytes(int(pixel_trace['requested_bytes']))}"
    )
    status = (
        f"0 new pixel ranges - cache hit; original read {original_read} - "
        f"actual envelope rows 0:{height} of {full_height}, columns 0:{width} - "
        f"{int(pixel_trace['full_gets'])} full-object GETs - "
        f"{cache_after.currsize}/8 fields cached"
        if cache_hit
        else (
            f"{original_read} - actual envelope rows 0:{height} of {full_height}, "
            f"columns 0:{width} - {int(pixel_trace['full_gets'])} full-object GETs - "
            f"cache miss ({cache_after.currsize}/8 fields)"
        )
    )
    mo.vstack(
        [
            image_surface,
            mo.md(
                "Wheel to zoom, drag to pan, or double-click to reset. "
                "Small multiples stay synchronized."
            ),
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
        {
            "channel": channel,
            "original TIFF": image_attrs["source_urls"][channel],
        }
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
    assert image_attrs["image_index_origin"] in {None, INDEX_ORIGIN}
    _chunk_shape = tuple(image_attrs["virtual_chunk_shape"])
    _logical_shape = tuple(image_attrs["logical_shape"])
    assert _chunk_shape[0] == 1
    assert 0 < _chunk_shape[1] <= _logical_shape[1]
    assert _chunk_shape[2] == _logical_shape[2]
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
