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
python -m jump.unichem pull collate
```

## Get annotations from external databases

invoke `concat_annotations` from `jump.collate`

```python
from jump.collate import concat_annotations
concat_annotations('./outputs')
```


## Export external ids to txt files

```bash
python -m jump.collect_external_ids ./outputs
```
