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
Pass `index_origin` as either an image-index URL or a local Parquet path to use a managed mirror or frozen index.
Pass the matching Pooch-compatible checksum as `index_hash` for a remote origin.

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
