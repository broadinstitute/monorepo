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
# {'BRD-K36461289-001-05-8': 'SCIMP', 'ccsbBroad304_16164': 'PIMZUZSSNYHVCU-KBLUICEQSA-N'}
```

## Export database as csv
```python
from broad_sample.query import export_csv

export_csv("./output.csv")
```

## Custom querying
The available fields are:
- perturbation: Dataset of origin for a given entry
- JCP2022: Identifier from the JUMP dataset
- standard_key: Gene Entrez id for gene-related perturbations, and InChIKey for compound perturbations
- broad_sample: Internal Broad ID
- pert_type: Type of perturbation, options are trt (treatment), HBB (), control, negcon (Negative Control) and poscon (Positive Control).
- control_type: Only applicable for entries when pert_type is "control". This value can be negcon, poscon_cp, poscon_diverse, poscon_orf and trt (treatment).


You can fetch any field using another (note that the output is a list of tuples)

```python
run_query(query="JCP2022_915119", input_column="JCP2022", output_column="broad_sample")
# [('ccsbBroad304_16164',)]
```

Note that there are some duplicates that arise from both between orf and crispr perturbations, but also within orf standard_keys.

```python
run_query("ccsbBroad304_00900", input_column = "broad_sample", output_column = "*")

# [('crispr', 'JCP2022_803621', 'KCNN1', 'ccsbBroad304_00900', 'trt', None),
#  ('orf', 'JCP2022_900842', 'KCNN1', 'ccsbBroad304_00900', 'trt', None),
#  ('Target1_orf', None, 'KCNN1', 'ccsbBroad304_00900', 'trt', None)]
```

It is also possible to use fuzzy querying by changing the operator argument and adding "%" to out key.

```python
    run_query(
        "BRD-K21728777%",
        input_column="broad_sample",
        output_column="*",
        operator="LIKE",
    )

# [('compound',
#   'JCP2022_037716',
#   'IVUGFMLRJOCGAS-UHFFFAOYSA-N',
#   'BRD-K21728777-001-02-3',
#   'control',
#   'poscon_cp'),
#  ('Target2_compound',
#   None,
#   'IVUGFMLRJOCGAS-UHFFFAOYSA-N',
#   'BRD-K21728777-001-02-3',
#   'control',
#   'poscon_cp')]
```

## Additional documentation
Metadata sources and additional documentation is available [here](./docs). 
