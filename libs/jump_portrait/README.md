# JUMP-portrait

Utilities for interacting with the JUMP-Cell Painting Gallery dataset on AWS S3.
We facilitate querying the JUMP-CP dataset index, retrieving metadata for specific perturbations, and loading microscopy images directly into memory or downloading them to local storage.

## Main Functions

### Metadata Retrieval

#### `get_item_location_metadata`
Search for a specific gene or compound by name or JCP ID to retrieve its location metadata (Source, Batch, Plate, Well, Site) and corresponding S3 URIs.

```python
from jump_portrait.fetch import get_item_location_metadata

# Search for a gene by standard key
metadata = get_item_location_metadata("MYT1")

# Search for a compound by JCP ID
metadata = get_item_location_metadata("JCP2022_000001", input_column="JCP2022")
```

By default, metadata lookup scans the immutable CloudFront Parquet object at `https://d3dw4c1b79pj57.cloudfront.net/19373370/jump_index.parquet/content`.
The object is 145,197,890 bytes and has SHA-256 `f45ea1a5de091e43caf35358370abf843bd2be47b2810283fd76db472b5acc6a`.
DuckDB uses HTTP byte-range requests for the Parquet metadata and row groups needed by the query and does not create a local `jump_index.parquet` copy.
A partial remote scan does not verify the full-object SHA-256 because it does not read every byte.
Pass an explicit local `Path` through `index_origin` for offline use, or call `get_index_file()` when a complete cached and checksum-verified index is required.

### Image Retrieval

#### `get_jump_image`
Fetch a single image directly as a NumPy array using specific coordinate identifiers.

```python
from jump_portrait.fetch import get_jump_image

img = get_jump_image(
    source="source_4",
    batch="2021_04_26_Batch1",
    plate="BR00121565",
    well="A01",
    channel="DNA",
    site=1
)
```

#### `get_jump_image_site`

On Python 3.11 or newer, `get_jump_image_site` exposes one complete site as a lazy `xarray.DataArray` backed by VirtualiZarr references.
The dimensions are `(channel, y, x)`, and the channel coordinate is ordered as `AGP`, `DNA`, `ER`, `Mito`, and `RNA`.
Construction reads TIFF metadata with byte-range requests, while indexing reads only the TIFF chunks needed for the selected pixels.
It does not download or create local TIFF files.
The bounded path supports the uncompressed, single-page strip layout used by source_8 and raises `UnsupportedTIFFLayoutError` with the source and cause for other layouts.

The optional trace provides public evidence for the TIFF URLs, logical and virtual-reference byte counts, selected indexer, and transferred bytes.

```python notest
from jump_portrait import RequestTrace, get_jump_image_site

trace = RequestTrace()
site = get_jump_image_site(
    source="source_8",
    batch="J3",
    plate="A1166127",
    well="A01",
    site=1,
    trace=trace,
)

trace.clear()
indexer = {"y": slice(0, 256), "x": slice(0, 256)}
crop = site.isel(**indexer).values
evidence = {
    "source_urls": site.attrs["source_urls"],
    "logical_array_bytes": site.nbytes,
    "virtual_reference_bytes": site.attrs["virtual_reference_bytes"],
    "selected_indexer": indexer,
    "request_summary": trace.summary(),
    "request_methods": sorted({request.method for request in trace.requests}),
    "requested_image_bytes": trace.total_bytes,
}
```

Each `trace.requests` record exposes the object path, byte start, length and end, timestamp, duration, method, and range style.
A bounded read should contain `get_range` or `get_ranges` methods and no full-object `get` method.
`trace.total_bytes` is the sum of requested range lengths, not a wire-level transfer counter.
By default, `get_jump_image_site` Range-scans the remote image index and creates no local index copy.
Pass `index_origin` as a local Parquet path for offline use.
Pass `index_hash` explicitly only when a complete cached and checksum-verified remote index is required; this opt-in path downloads the full object.

The [standalone VirtualiZarr vignette](notebooks/virtualizarr_image_vignette.py) queries public JUMP metadata, opens one Source_8 site lazily, displays the five Cell Painting channels, and reports its range-request evidence.
It carries its own dependencies and exact public `jump_portrait` pin, so the single downloaded file can be launched with:

```bash
uv run marimo edit --sandbox virtualizarr_image_vignette.py
```

#### `get_jump_image_batch`
Load multiple images into memory in parallel based on a metadata table.

```python
from jump_portrait.fetch import get_item_location_metadata, get_jump_image_batch

# Get metadata for a perturbation
metadata = get_item_location_metadata("MYT1")

# Load all DNA and Mito images for this perturbation into memory
meta_dicts, images = get_jump_image_batch(
    metadata, 
    channels=["DNA", "Mito"],
    site=[1, 2]
)
```

### File Operations

#### `download_jump_image_batch`
Download a batch of images from S3 to a local directory in a structured or flattened format.

```python
from jump_portrait.fetch import get_item_location_metadata, download_jump_image_batch

metadata = get_item_location_metadata("CLETVKMYAXARPO-UHFFFAOYSA-N")

# Download images to a local folder
download_jump_image_batch(
    metadata, 
    output_dir="./data/images", 
    channels=["DNA", "RNA"]
)
```

## S3 Utilities

The `jump_portrait.s3` module provides lower-level utilities for interacting with the Cell Painting Gallery:

- **`get_image_from_s3uri(uri)`**: Retrieves an image from a specific S3 URI and returns it as a NumPy array.
  Supports `.tif`, `.tiff`, `.png`, and `.npy` formats.
- **`s3client(use_credentials=False)`**: Creates a `boto3` client configured for the gallery.
  By default, it uses unsigned requests (no AWS account required for public data).
- **`download_s3uri(meta, output_dir)`**: Downloads a specific file from the gallery based on metadata components.
