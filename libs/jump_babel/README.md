# Broad_Babel

Minimal name translator of [JUMP](https://jump-cellpainting.broadinstitute.org/) consortium.

## Installation

```bash
pip install broad-babel
```

## Broad sample to standard 
You can fetch a single value
```python
from broad_babel.query import broad_to_standard

broad_to_standard("BRD-K18895904-001-16-1") 
# -> 'KVWDHTXUZHCGIO-UHFFFAOYSA-N'
```
If you provide multiple strings it will return dictionary.

```python
broad_to_standard(("BRD-K36461289-001-05-8", "ccsbBroad304_16164")) 
# {'BRD-K36461289-001-05-8': 'SCIMP', 'ccsbBroad304_16164': 'PIMZUZSSNYHVCU-KBLUICEQSA-N'}
```

## Wildcard search
You can also use [sqlite](https://docs.python.org/3/library/sqlite3.html) bindings. For instance, to get all the samples that start as "poscon" you can use:

```python
run_query(query="poscon%", input_column="pert_type", output_columns="JCP2022,standard_key,plate_type,pert_type", operator="LIKE")

# [(None, 'LRRMQNGSYOUANY-OMCISZLKSA-N', 'compound', 'poscon_cp'),
#  (None, 'DHMTURDWPRKSOA-RUZDIDTESA-N', 'compound', 'poscon_diverse'),
#  ...
#  ('JCP2022_913605', 'CDK2', 'orf', 'poscon_orf'),
#  ('JCP2022_913622', 'CLK1', 'orf', 'poscon_cp')]
```

## Make mappers for quick renaming

This is very useful when you need to map from a long list of perturbation names. The following example shows how to map all the perturbations in the compound plate from JCP id to perturbation type.
```python
from broad_babel.query import get_mapper

mapper = get_mapper(query="compound", input_column="plate_type", output_columns="JCP2022,pert_type")
```


## Export database as csv
```python
from broad_babel.query import export_csv

export_csv("./output.csv")
```

## Custom querying
The available fields are:
- standard_key: Gene Entrez id for gene-related perturbations, and InChIKey for compound perturbations
- JCP2022: Identifier from the JUMP dataset
- plate_type: Dataset of origin for a given entry
- NCBI_Gene_ID: NCBI identifier, only applicable to ORF and CRISPR
- broad_sample: Internal Broad ID
- pert_type: Type of perturbation, options are trt (treatment), control, negcon (Negative Control), poscon_cp (Positive Control, Compound Probe), poscon_diverse, poscon_orf, and poscon (Positive Control).

You can fetch any field using another (note that the output is a list of tuples)

```python
run_query(query="JCP2022_915119", input_column="JCP2022", output_columns="broad_sample")
# [('ccsbBroad304_16164',)]
```

Note that there are some duplicates that arise from both between orf and crispr perturbations, but also within orf standard_keys.

```python
run_query("ccsbBroad304_00900", input_column = "broad_sample", output_columns = "*")

# [('crispr', 'JCP2022_803621', 'KCNN1', 'ccsbBroad304_00900', 'trt', None),
#  ('orf', 'JCP2022_900842', 'KCNN1', 'ccsbBroad304_00900', 'trt', None),
#  ('Target1_orf', None, 'KCNN1', 'ccsbBroad304_00900', 'trt', None)]
```

It is also possible to use fuzzy querying by changing the operator argument and adding "%" to out key.

```python
    run_query(
        "BRD-K21728777%",
        input_column="broad_sample",
        output_columns="*",
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
