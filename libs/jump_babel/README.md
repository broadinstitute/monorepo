# Broad_Babel

Minimal name translator of [JUMP](https://jump-cellpainting.broadinstitute.org/) consortium.

## Installation

```bash
pip install broad-babel
```

## Broad sample to standard 
You can fetch a single value
```python
from broad_sample.query import sample_to_standard

broad_to_standard("BRD-K18895904-001-16-1") 
# -> 'KVWDHTXUZHCGIO-UHFFFAOYSA-N'
```
If you provide multiple strings it will return dictionary.

```python
broad_to_standard(("BRD-K36461289-001-05-8", "ccsbBroad304_16164")) 
# -> {'BRD-K36461289-001-05-8': 'SCIMP', 'ccsbBroad304_16164': 'PIMZUZSSNYHVCU-KBLUICEQSA-N'}
```

## Export database as csv
```python
from broad_sample.query import export_csv

export_csv("./output.csv")
```

## Custom querying
The available fields are ("perturbation", "jump_id", "standard_key" and "broad_sample")

You can fetch any field using another (note that the output is a list of tuples)

```python
run_query(query="JCP2022_915119", input_column="jump_id", output_column="broad_sample")
```

Note that there are some duplicates that arise from both between orf and crispr perturbations, but also within orf standard_keys.

```python
run_query("ccsbBroad304_00900", input_column = "broad_sample", output_column = "*")
```

## Additional documentation
Metadata sources and additional documentation is available [here](./docs). 
