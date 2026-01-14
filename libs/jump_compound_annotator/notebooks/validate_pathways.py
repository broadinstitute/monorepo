#!/usr/bin/env python3
# Run with: pixi exec --spec duckdb -- python notebooks/validate_pathways.py
"""Validate pathway annotations for JUMP compounds using DuckDB."""

import zipfile
import tempfile
from pathlib import Path

import duckdb

OUTPUT_DIR = Path("outputs")


def main():
    con = duckdb.connect()

    # Extract BioKG files from zip
    with zipfile.ZipFile(OUTPUT_DIR / "biokg" / "biokg.zip") as zf:
        with tempfile.TemporaryDirectory() as tmpdir:
            zf.extract("biokg.links.tsv", tmpdir)
            zf.extract("biokg.metadata.pathway.tsv", tmpdir)
            biokg_links_path = Path(tmpdir) / "biokg.links.tsv"
            biokg_meta_path = Path(tmpdir) / "biokg.metadata.pathway.tsv"

            # Run all queries
            run_validation(con, biokg_links_path, biokg_meta_path)


def run_validation(con: duckdb.DuckDBPyConnection, biokg_links: Path, biokg_meta: Path):
    """Run validation queries."""

    print("=" * 60)
    print("Pathway Annotations Validation for JUMP Compounds")
    print("=" * 60)

    # 1. Load JUMP DrugBank mappings
    con.execute(f"""
        CREATE TEMP TABLE jump_drugbank AS
        SELECT DISTINCT drugbank
        FROM read_csv_auto('{OUTPUT_DIR}/pointers.csv')
        WHERE drugbank IS NOT NULL
    """)
    result = con.execute("SELECT COUNT(*) FROM jump_drugbank").fetchone()
    print(f"\nJUMP compounds with DrugBank IDs: {result[0]}")

    # 2. BioKG Analysis
    print("\n" + "-" * 40)
    print("BioKG Pathway Analysis")
    print("-" * 40)

    con.execute(f"""
        CREATE TEMP TABLE biokg_links AS
        SELECT column0 AS drug_id, column1 AS rel_type, column2 AS pathway_id
        FROM read_csv('{biokg_links}', sep='\t', header=false)
    """)

    con.execute("""
        CREATE TEMP TABLE biokg_drug_pathways AS
        SELECT * FROM biokg_links WHERE rel_type = 'DRUG_PATHWAY_ASSOCIATION'
    """)

    result = con.execute("SELECT COUNT(*) FROM biokg_drug_pathways").fetchone()
    print(f"Total drug-pathway associations: {result[0]}")

    result = con.execute("SELECT COUNT(DISTINCT drug_id) FROM biokg_drug_pathways").fetchone()
    print(f"Unique drugs with pathways: {result[0]}")

    result = con.execute("SELECT COUNT(DISTINCT pathway_id) FROM biokg_drug_pathways").fetchone()
    print(f"Unique pathways: {result[0]}")

    # JUMP overlap
    result = con.execute("""
        SELECT COUNT(DISTINCT b.drug_id)
        FROM biokg_drug_pathways b
        JOIN jump_drugbank j ON b.drug_id = j.drugbank
    """).fetchone()
    print(f"JUMP compounds with BioKG pathways: {result[0]}")

    result = con.execute("""
        SELECT COUNT(*)
        FROM biokg_drug_pathways b
        JOIN jump_drugbank j ON b.drug_id = j.drugbank
    """).fetchone()
    print(f"JUMP pathway associations: {result[0]}")

    result = con.execute("""
        SELECT COUNT(DISTINCT b.pathway_id)
        FROM biokg_drug_pathways b
        JOIN jump_drugbank j ON b.drug_id = j.drugbank
    """).fetchone()
    print(f"JUMP unique pathways: {result[0]}")

    # 3. PharmeBiNet Analysis
    print("\n" + "-" * 40)
    print("PharmeBiNet Pathway Analysis")
    print("-" * 40)

    con.execute(f"""
        CREATE TEMP TABLE pharmebinet_edges AS
        SELECT * FROM read_parquet('{OUTPUT_DIR}/pharmebinet/edges.parquet')
    """)

    con.execute(f"""
        CREATE TEMP TABLE pharmebinet_nodes AS
        SELECT * FROM read_parquet('{OUTPUT_DIR}/pharmebinet/nodes.parquet')
    """)

    con.execute("""
        CREATE TEMP TABLE pharmebinet_chem_pathway AS
        SELECT e.start_id, e.end_id, n.identifier AS drugbank_id
        FROM pharmebinet_edges e
        JOIN pharmebinet_nodes n ON e.start_id = n.node_id
        WHERE e.type = 'ASSOCIATES_CaPW'
    """)

    result = con.execute("SELECT COUNT(*) FROM pharmebinet_chem_pathway").fetchone()
    print(f"Total compound-pathway associations: {result[0]}")

    result = con.execute("SELECT COUNT(DISTINCT drugbank_id) FROM pharmebinet_chem_pathway").fetchone()
    print(f"Unique compounds with pathways: {result[0]}")

    result = con.execute("SELECT COUNT(DISTINCT end_id) FROM pharmebinet_chem_pathway").fetchone()
    print(f"Unique pathways: {result[0]}")

    # JUMP overlap
    result = con.execute("""
        SELECT COUNT(DISTINCT p.drugbank_id)
        FROM pharmebinet_chem_pathway p
        JOIN jump_drugbank j ON p.drugbank_id = j.drugbank
    """).fetchone()
    print(f"JUMP compounds with PharmeBiNet pathways: {result[0]}")

    result = con.execute("""
        SELECT COUNT(*)
        FROM pharmebinet_chem_pathway p
        JOIN jump_drugbank j ON p.drugbank_id = j.drugbank
    """).fetchone()
    print(f"JUMP pathway associations: {result[0]}")

    # 4. Combined Coverage
    print("\n" + "-" * 40)
    print("Combined Coverage Analysis")
    print("-" * 40)

    result = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT drug_id AS drugbank_id
            FROM biokg_drug_pathways b
            JOIN jump_drugbank j ON b.drug_id = j.drugbank
            UNION
            SELECT DISTINCT drugbank_id
            FROM pharmebinet_chem_pathway p
            JOIN jump_drugbank j ON p.drugbank_id = j.drugbank
        )
    """).fetchone()
    print(f"JUMP compounds with pathways (combined): {result[0]}")

    results = con.execute("""
        WITH biokg_jump AS (
            SELECT DISTINCT drug_id AS drugbank_id FROM biokg_drug_pathways b
            JOIN jump_drugbank j ON b.drug_id = j.drugbank
        ),
        pharmebinet_jump AS (
            SELECT DISTINCT drugbank_id FROM pharmebinet_chem_pathway p
            JOIN jump_drugbank j ON p.drugbank_id = j.drugbank
        )
        SELECT 'BioKG only' AS source, COUNT(*) AS count
        FROM biokg_jump WHERE drugbank_id NOT IN (SELECT drugbank_id FROM pharmebinet_jump)
        UNION ALL
        SELECT 'PharmeBiNet only', COUNT(*)
        FROM pharmebinet_jump WHERE drugbank_id NOT IN (SELECT drugbank_id FROM biokg_jump)
        UNION ALL
        SELECT 'Both', COUNT(*)
        FROM biokg_jump WHERE drugbank_id IN (SELECT drugbank_id FROM pharmebinet_jump)
    """).fetchall()
    for source, count in results:
        print(f"  {source}: {count}")

    # 5. Pathway Type Breakdown
    print("\n" + "-" * 40)
    print("BioKG Pathway Type Breakdown (JUMP compounds)")
    print("-" * 40)

    con.execute(f"""
        CREATE TEMP TABLE biokg_pathway_meta AS
        SELECT column0 AS pathway_id, column1 AS prop, column2 AS value
        FROM read_csv('{biokg_meta}', sep='\t', header=false)
        WHERE column1 = 'NAME'
    """)

    results = con.execute("""
        WITH jump_pathways AS (
            SELECT DISTINCT b.pathway_id
            FROM biokg_drug_pathways b
            JOIN jump_drugbank j ON b.drug_id = j.drugbank
        ),
        categorized AS (
            SELECT
                m.pathway_id,
                m.value AS pathway_name,
                CASE
                    WHEN m.pathway_id LIKE 'map%' THEN 'KEGG drug class'
                    WHEN m.value LIKE '%Action Pathway%' OR m.value LIKE '%Action' THEN 'SMPDB drug action'
                    WHEN m.value LIKE '%Metabolism%' THEN 'SMPDB metabolism'
                    WHEN m.value LIKE '%Biosynthesis%' THEN 'SMPDB biosynthesis'
                    ELSE 'Other'
                END AS category
            FROM biokg_pathway_meta m
            JOIN jump_pathways jp ON m.pathway_id = jp.pathway_id
        )
        SELECT category, COUNT(*) AS count
        FROM categorized
        GROUP BY category
        ORDER BY count DESC
    """).fetchall()
    for category, count in results:
        print(f"  {category}: {count}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
