"""Abfragen auf der DuckDB-Datenbank.

``find_sets_for_parts`` bekommt eine Liste von Teilen und liefert die Sets,
in denen sie vorkommen, sortiert nach der Anzahl übereinstimmender Teile.

Start: ``uv run python -m lego_scanner.database.queries 3001 3003``
"""

import sys

import duckdb

from lego_scanner.paths import DB_PATH


def resolve_color(con: duckdb.DuckDBPyConnection, color: int | str) -> int:
    """Gibt die ``colors.id`` zu einer Farbe zurück.

    Erlaubt ist der Name (``"Red"``, ``"light_bluish_gray"``) oder die ID.
    Leerzeichen und Bindestriche zählen wie Unterstriche, damit die Namen aus
    den Sortierdaten passen.
    """
    if isinstance(color, int):
        return color

    row = con.execute(
        """
        SELECT id
        FROM colors
        WHERE lower(replace(replace(name, ' ', '_'), '-', '_')) = lower(replace(replace(?, ' ', '_'), '-', '_'))
        ORDER BY num_parts DESC
        LIMIT 1
        """,
        [color],
    ).fetchone()
    if row is None:
        raise ValueError(f"Unbekannte Farbe: {color!r}")
    return row[0]


def find_sets_for_parts(
    parts,
    limit: int | None = 20,
    con: duckdb.DuckDBPyConnection | None = None,
) -> list[dict]:
    """Gibt Sets zurück, in denen möglichst viele der Teile vorkommen.

    ``parts`` enthält Teilenummern, optional mit Farbe: ``"3001"`` oder
    ``("3001", 4)``, die Farbe auch als Name. Ohne Farbe zählt das Teil in
    jeder Farbe, doppelte Einträge zählen einmal.

    Sortiert nach Anzahl übereinstimmender Teile; bei Gleichstand zuerst das
    kleinere Set. Sets ohne Teile und die Sonderfarben ``-1``/``9999`` fallen
    raus. ``limit=None`` gibt alle Treffer zurück.
    """
    if not parts:
        return []

    connection = con if con is not None else duckdb.connect(DB_PATH, read_only=True)
    try:
        rows = []
        for part in parts:
            if isinstance(part, str):
                rows.append((part, None))
                continue
            part_num, color = part
            rows.append((part_num, resolve_color(connection, color) if isinstance(color, str) else color))

        connection.execute("CREATE OR REPLACE TEMP TABLE query_parts (part_num VARCHAR, color_id BIGINT)")
        connection.executemany("INSERT INTO query_parts VALUES (?, ?)", rows)

        sql = f"""
            WITH q AS (
                SELECT DISTINCT part_num, color_id FROM query_parts
            ),
            -- Ein Sucheintrag zählt pro Set einmal, auch wenn das Teil dort in
            -- mehreren Farben liegt.
            hits AS (
                SELECT DISTINCT sp.set_num, q.part_num, q.color_id
                FROM set_parts sp
                JOIN q
                  ON sp.part_num = q.part_num
                 AND (q.color_id IS NULL OR sp.color_id = q.color_id)
                WHERE sp.color_id NOT IN (-1, 9999)
            ),
            scored AS (
                SELECT set_num, count(*) AS matched_parts
                FROM hits
                GROUP BY set_num
            )
            SELECT
                s.set_num,
                s.name AS set_name,
                s.year,
                s.img_url,
                sc.matched_parts,
                s.num_parts
            FROM scored sc
            JOIN sets s ON s.set_num = sc.set_num
            WHERE s.num_parts > 0
            ORDER BY sc.matched_parts DESC, s.num_parts ASC, s.set_num
        """
        params = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        cursor = connection.execute(sql, params)
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        if con is None:
            connection.close()


def main() -> None:
    """Gibt die Sets zu den Teilenummern aus der Kommandozeile aus."""
    parts = sys.argv[1:]
    if not parts:
        print("Aufruf: python -m lego_scanner.database.queries <teilenummer> ...")
        return
    for row in find_sets_for_parts(parts, limit=10):
        print(f"{row['set_num']:>10}  {row['matched_parts']}/{len(parts)} Teile  {row['set_name']} ({row['year']})")


if __name__ == "__main__":
    main()
