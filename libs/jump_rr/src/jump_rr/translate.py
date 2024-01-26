#!/usr/bin/env jupyter
from broad_babel.query import run_query

external_formatter = (
    '{{"href": "https://www.ncbi.nlm.nih.gov/gene/{}", "label":"External"}}'
)


def get_mappers(
    ids: tuple[str],
    plate_type: str,
    input_col: str = "JCP2022",
    output_cols: list[str] = ["standard_key", "NCBI_Gene_ID"],
):
    """Generate translators based on an identifier using broad-babel."""

    mapper_values = run_query(
        query=ids,
        input_column=input_col,
        output_column=",".join((input_col, *output_cols)),
        predicate=f"AND plate_type = '{plate_type}'",
    )

    output_ids = {k: {} for k in output_cols}
    for input_id, *output_ids in mapper_values:
        for k, new_id in output_ids.items():
            output_ids[k][input_id] = external_formatter.format(new_id)
    return output_ids