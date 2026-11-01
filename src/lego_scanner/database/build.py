"""Baut die lokale DuckDB-Datenbank aus den Rebrickable-CSVs.

Start: ``uv run python -m lego_scanner.database.build``
"""

import duckdb
from lego_scanner.paths import DB_PATH, RAW_DIR

"""Lädt die Rebrickable-CSVs aus RAW_DIR als Tabellen in die Datenbank."""
def load_tables(con):
    con.execute(f"CREATE OR REPLACE TABLE colors AS SELECT * FROM read_csv('{RAW_DIR/ 'colors.csv'}')")

"""Legt den Datenordner an und baut die Datenbank unter DB_PATH neu auf."""
def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(DB_PATH) as con:
        load_tables(con)

if __name__ == "__main__":
    main()