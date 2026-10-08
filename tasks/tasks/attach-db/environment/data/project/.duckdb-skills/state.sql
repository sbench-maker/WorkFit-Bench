-- Shared analyst setup for this project. Keep these definitions intact.
SET TimeZone = 'UTC';

CREATE OR REPLACE MACRO safe_ratio(numerator, denominator) AS
  CASE
    WHEN denominator = 0 THEN NULL
    ELSE numerator::DOUBLE / denominator
  END;

-- The historical customer reference already owns the filename-derived alias.
ATTACH IF NOT EXISTS '/root/data/project/reference/customer_history.duckdb' AS support_ops (READ_ONLY);
