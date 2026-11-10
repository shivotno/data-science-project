""" Baut die lokale DuckDB-Datenbank aus den Rebrickable-CSVs.

Start: ``uv run python -m lego_scanner.database.build``
"""

import duckdb

from lego_scanner.paths import DB_PATH, RAW_DIR

""" Zu ladende Rebrickable-Tabellen und Spalten mit festgelegtem Typ. Wo nichts steht, erkennt DuckDB den Typ selbst. """
TABLES = {
    "colors": {"rgb": "VARCHAR"},
    "parts": {"part_num": "VARCHAR"},
    "inventory_parts": {"part_num": "VARCHAR"},
    "sets": {"set_num": "VARCHAR"},
    "inventories": {"set_num": "VARCHAR"},
    "themes": {},
    "part_categories": {},
}


""" Fremdschlüssel-Prüfungen """
FOREIGN_KEY_CHECKS = {
    "Teile ohne gültige Kategorie": """
        SELECT count(*)
        FROM parts p
        LEFT JOIN part_categories pc ON p.part_cat_id = pc.id
        WHERE pc.id IS NULL
    """,
    "Stückliste mit unbekanntem Teil": """
        SELECT count(*)
        FROM inventory_parts ip
        LEFT JOIN parts p ON ip.part_num = p.part_num
        WHERE p.part_num IS NULL
    """,
    "Stückliste mit unbekannter Farbe": """
        SELECT count(*)
        FROM inventory_parts ip
        LEFT JOIN colors c ON ip.color_id = c.id
        WHERE c.id IS NULL
    """,
}

def load_tables(con):
    """Lädt die Rebrickable-CSVs aus RAW_DIR als Tabellen in die Datenbank."""
    for name, types in TABLES.items():
        path = RAW_DIR / f"{name}.csv"
        options = f", types = {types}" if types else ""
        sql = f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_csv('{path}'{options})"
        print(sql)
        con.execute(sql)


def create_views(con):
    """Legt die View set_parts an.

    set_parts verbindet sets, inventories und inventory_parts zu einer
    Stückliste: welches Teil in welcher Farbe wie oft in welchem Set steckt.

    - Pro Set wird das Inventar mit der kleinsten Versionsnummer verwendet.
    - Ersatzteile (is_spare) werden weggelassen.
    - Inventare ohne passendes Set, z. B. von Minifiguren, fallen weg.
    """
    con.execute("""
        CREATE OR REPLACE VIEW set_parts AS
        WITH first_versions AS (
            SELECT set_num, min(version) AS version
            FROM inventories
            GROUP BY set_num
        )
        SELECT
            s.set_num,
            s.name AS set_name,
            s.year,
            ip.part_num,
            ip.color_id,
            ip.quantity
        FROM first_versions fv
        JOIN inventories i      ON i.set_num = fv.set_num AND i.version = fv.version
        JOIN sets s             ON s.set_num = i.set_num
        JOIN inventory_parts ip ON ip.inventory_id = i.id
        WHERE NOT ip.is_spare
    """)


def check_integrity(con):
    """Prüft die geladenen Daten und bricht bei Fehlern ab."""
    for name in TABLES:
        count = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"{name}: {count} Zeilen")
        if count == 0:
            raise RuntimeError(f"Tabelle {name} ist leer.")

    count = con.execute("SELECT count(*) FROM set_parts").fetchone()[0]
    print(f"set_parts: {count} Zeilen")
    if count == 0:
        raise RuntimeError("View set_parts ist leer.")

    for description, sql in FOREIGN_KEY_CHECKS.items():
        count = con.execute(sql).fetchone()[0]
        if count > 0:
            raise RuntimeError(f"{description}: {count}")

    print("Integritätschecks bestanden.")


def main():
    """Legt den Datenordner an und baut die Datenbank unter DB_PATH neu auf."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(DB_PATH) as con:
        load_tables(con)
        create_views(con)
        check_integrity(con)


if __name__ == "__main__":
    main()