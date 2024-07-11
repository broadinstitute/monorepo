# Broad_Babel

Minimal name translator of [JUMP](https://jump-cellpainting.broadinstitute.org/) consortium.

## Installation

```bash
pip install broad-babel
```

## Broad sample to standard 
You can fetch a single value. Note that only ORF datasets have an associated broad_id by default.
```python
from broad_babel.query import broad_to_standard

broad_to_standard("ccsbBroad304_99994") 
# 'LacZ'
```
If you provide multiple strings it will return dictionary.

```python
broad_to_standard(("ccsbBroad304_09930", "ccsbBroad304_16164")) 

# {'ccsbBroad304_09930': 'SCIMP', 'ccsbBroad304_16164': 'NAP1L5'}
```

## Wildcard search
You can also use [sqlite](https://docs.python.org/3/library/sqlite3.html) bindings. For instance, to get all the samples that start as "poscon" you can use:

```python
from broad_babel.query import run_query
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

It is also possible to use fuzzy querying by changing the operator argument and adding "%" to out key. For example, to get the genes in the "orf" dataset whose name start with "RBP"(some of which are retinol-binding proteins) we can do:

```python
[x[:2] for x in run_query(
    "RBP%",
    input_column="standard_key",
    output_columns="standard_key,JCP2022,plate_type",
    operator="LIKE",
    ) if x[2]=="orf"]

# [('RBP7', 'JCP2022_904406'), ('RBPJ', 'JCP2022_906023'), ('RBP4', 'JCP2022_906415'),
# ('RBPMS', 'JCP2022_902435'), ('RBP2', 'JCP2022_914559'), ('RBP2', 'JCP2022_906413'),
# ('RBP3', 'JCP2022_906414'), ('RBP1', 'JCP2022_910341')]
```
Note that we also got RBPMS here, which is actually RNA-binding protein with multiple splicing, so use this with caution.

## Additional documentation
Metadata sources and additional documentation is available [here](./docs). 

Note that Babel only contains metadata of JUMP compounds and genes, and may not contain sample information from other projects (e.g., LINCS). A more comprehensive table to map "broad ids" to standard chemical ids (e.g., SMILES, InChiKey) can be found [here](https://repo-hub.broadinstitute.org/repurposing#download-data). 
