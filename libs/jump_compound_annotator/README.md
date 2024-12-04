# JUMP DTI annotations

Find drug target interaction annotations for JUMP compounds from publicly
available databases.

## Get unichem ids

```bash
python -m jump.unichem pull outputs
```
You may have to run this command multiple times to retry failed compound
queries. Some HTTP requests may get connection errors.

Then run `collate` to get them in a unified file 
```bash
python -m jump.unichem collate outputs
```

## Get annotations from external databases

Pull data from public datasets, select gene and compound interactions, map
compounds to inchikeys using mychem and unichem

```python
from jump.collate import concat_annotations
concat_annotations("./outputs/", redownload=False)

from jump.collate_gene import concat_annotations
concat_annotations("./outputs/", redownload=False)

from jump.collate_compounds import concat_annotations
concat_annotations("./outputs/", redownload=False)

from jump.find_inchikeys import add_inchikeys
add_inchikeys("./outputs/", redownload=True)
```

## Export external ids to txt files

```bash
python -m jump.collect_external_ids ./outputs
```
