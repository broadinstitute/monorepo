#!/usr/bin/env jupyter
from broad_babel.query import run_query
from jump_rr.formatters import format_val


def get_mappers(
    ids: tuple[str],
    plate_type: str,
    input_col: str = "JCP2022",
    output_cols: list[str] = ["standard_key", "NCBI_Gene_ID"],
    format_output: bool = True,
):
    """Generate translators based on an identifier using broad-babel."""

    mapper_values = run_query(
        query=ids,
        input_column=input_col,
        output_column=",".join((input_col, *output_cols)),
        predicate=f"AND plate_type = '{plate_type}'",
    )

    mappers = {k: {} for k in output_cols}
    for input_id, *output_ids in mapper_values:
        for k, new_id in zip(mappers.keys(), output_ids):
            if format_output:
                new_id = (
                    format_val("external", new_id) if k == "NCBI_Gene_ID" else new_id
                )
            mappers[k][input_id] = new_id
    return mappers.values()
