-- Generate perturbation ranking table from t-statistic and significance matrices.
-- Run with: duckdb < src/tools/generate_perturbation_ranking.sql
--
-- Requires databases/compound_tstat_full.parquet and
-- databases/compound_significance_full.parquet (produced by calculate_features.py).

COPY (
    WITH long AS (
        UNPIVOT 'databases/compound_tstat_full.parquet'
        ON COLUMNS(* EXCLUDE Metadata_JCP2022)
        INTO NAME feature VALUE t_statistic
    ),
    sig_long AS (
        UNPIVOT 'databases/compound_significance_full.parquet'
        ON COLUMNS(* EXCLUDE Metadata_JCP2022)
        INTO NAME feature VALUE p_value
    ),
    combined AS (
        SELECT l.Metadata_JCP2022, l.feature, l.t_statistic, s.p_value
        FROM long l
        JOIN sig_long s
          ON l.Metadata_JCP2022 = s.Metadata_JCP2022
         AND l.feature = s.feature
        WHERE s.p_value < 0.05
    ),
    ranked AS (
        SELECT *,
               row_number() OVER (
                   PARTITION BY feature
                   ORDER BY abs(t_statistic) DESC, Metadata_JCP2022
               ) as perturbation_rank
        FROM combined
    )
    SELECT
        split_part(feature, '_', 1) as Compartment,
        feature as Feature,
        Metadata_JCP2022 as JCP2022,
        round(t_statistic, 3) as "Effect size (t)",
        round(p_value, 5) as "Feature significance",
        perturbation_rank as "Perturbation Rank"
    FROM ranked
    WHERE perturbation_rank <= 50
) TO 'databases/compound_perturbation_ranking.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
