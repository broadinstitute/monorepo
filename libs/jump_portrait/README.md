
# Table of Contents



Tools to fetch and visualize images from the JUMP dataset.


## Workflow
### User

### Developer
Locate the images that correspond to a given gene

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
 - Plate: 
 - Batch: 
 - Well: 
 - Site: Foci or frame taken in a the well, generally these are 0-9.
[File/Path]name_[Illum/Orig][Channel] 
    
 - Illum: Illumination correction 
 - Orif: Original File
 Also, markers can be:
   - DNA: Dna channel, generally Hoecsht.
   - ER: Endoplasmatic Reticulum channel.
   - Mito: Mitochondrial channel.
   - RNA: RNA channel.
standard_key: Gene or compound queried

```
