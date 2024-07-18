# Table of Contents

Fetch, visualize and.or download images from the JUMP dataset.

## Workflow

### Workflow 1: Download all images for a given item and their controls

```python
item_name = "MYT1"  # Item or Compound of interest - (GC)OI
# channels = ["bf"]  # Standard channels are ER, AGP, Mito DNA and RNA
channels = ["DNA"]  # Standard channels are ER, AGP, Mito DNA and RNA
corrections = ["Orig"]  # Can also be "Illum"
controls = True  # Fetch controls in plates alongside (GC)OI?

download_item_images(item_name, channels, corrections=corrections, controls=controls)
```

### Workflow 2: get images from explicit metadata

Fetch one image for a given item and a control
```python
from jump_portrait.fetch import get_jump_image, get_sample
from jump_portrait.save import download_item_images

sample = get_sample()

source, batch, plate, well, site, *rest = sample.row(0)
channel = "DNA"
correction = None # or "Illum"

img = get_jump_image(source, batch, plate, well, channel, site, correction)
```


Workflow 3: Fetch bright field channel
Note that this is hacky and may not work for all sources.
```python
from jump_portrait.fetch import get_jump_image, get_sample
from jump_portrait.save import download_item_images

sample = get_sample()

channel = "bf"
correction = None

source, batch, plate, well, site, *rest = sample.row(0)
img = get_jump_image(source, batch, plate, well, channel, site, correction)
```

### Developer
First, we Locate the images produced to a given perturbation.

```python 
from jump_portrait.fetch import get_item_location_info

gene = "MYT1"

location_df = get_item_location_info(gene)
Returns a polars dataframe whose columns contain the metadata 
alongside path and file locations

#┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
#│ Metadata_ ┆ Metadata_ ┆ Metadata_ ┆ Metadata_ ┆ … ┆ PathName_ ┆ Metadata_ ┆ Metadata_ ┆ standard │
#│ Source    ┆ Batch     ┆ Plate     ┆ Well      ┆   ┆ OrigRNA   ┆ PlateType ┆ JCP2022   ┆ _key     │
#│ ---       ┆ ---       ┆ ---       ┆ ---       ┆   ┆ ---       ┆ ---       ┆ ---       ┆ ---      │
#│ str       ┆ str       ┆ str       ┆ str       ┆   ┆ str       ┆ str       ┆ str       ┆ str      │
#╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
#│ source_13 ┆ 20220914_ ┆ CP-CC9-R1 ┆ B05       ┆ … ┆ s3://cell ┆ CRISPR    ┆ JCP2022_8 ┆ MYT1     │
#│           ┆ Run1      ┆ -20       ┆           ┆   ┆ painting- ┆           ┆ 04400     ┆          │
#│           ┆           ┆           ┆           ┆   ┆ gallery/c ┆           ┆           ┆          │
#│           ┆           ┆           ┆           ┆   ┆ pg001…    ┆           ┆           ┆          │
#│ source_13 ┆ 20220914_ ┆ CP-CC9-R1 ┆ B05       ┆ … ┆ s3://cell ┆ CRISPR    ┆ JCP2022_8 ┆ MYT1     │
#│           ┆ Run1      ┆ -20       ┆           ┆   ┆ painting- ┆           ┆ 04400     ┆          │
#│           ┆           ┆           ┆           ┆   ┆ gallery/c ┆           ┆           ┆          │
#│           ┆           ┆           ┆           ┆   ┆ pg001…    ┆           ┆           ┆          │
#│ source_13 ┆ 20220914_ ┆ CP-CC9-R1 ┆ B05       ┆ … ┆ s3://cell ┆ CRISPR    ┆ JCP2022_8 ┆ MYT1     │
#│           ┆ Run1      ┆ -20       ┆           ┆   ┆ painting- ┆           ┆ 04400     ┆          │
#│           ┆           ┆           ┆           ┆   ┆ gallery/c ┆           ┆           ┆          │
#│           ┆           ┆           ┆           ┆   ┆ pg001…    ┆           ┆           ┆          │
#│ source_13 ┆ 20220914_ ┆ CP-CC9-R1 ┆ B05       ┆ … ┆ s3://cell ┆ CRISPR    ┆ JCP2022_8 ┆ MYT1     │
#│           ┆ Run1      ┆ -20       ┆           ┆   ┆ painting- ┆           ┆ 04400     ┆          │
#│           ┆           ┆           ┆           ┆   ┆ gallery/c ┆           ┆           ┆          │
#│           ┆           ┆           ┆           ┆   ┆ pg001…    ┆           ┆           ┆          │
#│ source_13 ┆ 20220914_ ┆ CP-CC9-R1 ┆ B05       ┆ … ┆ s3://cell ┆ CRISPR    ┆ JCP2022_8 ┆ MYT1     │
#│           ┆ Run1      ┆ -20       ┆           ┆   ┆ painting- ┆           ┆ 04400     ┆          │
#│           ┆           ┆           ┆           ┆   ┆ gallery/c ┆           ┆           ┆          │
#│           ┆           ┆           ┆           ┆   ┆ pg001…    ┆           ┆           ┆          │
#└───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
```

The columns of these dataframes are:
```
Metadata_[Source/Batch/Plate/Well/Site]:
 - Source: Source in the range 0-14.
 - Plate: Plate containing a multitude of wells. It is a string.
 - Batch: Collection of plates imaged at around the same time. It is a string.
 - Well: Physical location wherein the experiment was performed and imaged. It is a string with format [SNN] where S={A-P} and NN={00-24}.
 - Site: Foci or frame taken in a the well, these are 0-9 for the ORF and CRISPR datasets and 1-6 for the compounds dataset.
[File/Path]name_[Illum/Orig][Channel] 
    
 - Illum: Illumination correction 
 - Orig: Original File
 Also, markers can be:
   - DNA: Dna channel, generally Hoecsht.
   - ER: Endoplasmatic Reticulum channel.
   - Mito: Mitochondrial channel.
   - RNA: RNA channel.
standard_key: Gene or compound queried

```

We can then feed this information to `jump_portrait.fetch.get_jump_image` to fetch the available images.
