# Datenexploration Rebrickable-CSVs (Issue #5)

Notizen aus der Exploration der Rebrickable-Dateien in `data/raw/` (entpackt als `.csv`). Grundlage für das Build-Skript. Exploration abgeschlossen am 01.11.2026.

## Konsequenzen für das Build-Skript (Zusammenfassung)

1. **Typen explizit festlegen** statt raten lassen: `part_num`, `set_num`, `rgb` als VARCHAR (führende Nullen, Buchstaben).
2. **Rohdaten vollständig laden, gefiltert wird erst in Views/Abfragen.** So bleibt nachvollziehbar, was weggelassen wurde, und Filter lassen sich ändern, ohne neu zu laden.
3. **View `set_parts`** (Set, Teil, Farbe, Menge):
   - nur **eine Inventar-Version pro Set** (die kleinste vorhandene, nicht blind `version = 1`)
   - JOIN mit `sets` → Minifiguren-Inventare (`fig-…`) fallen automatisch raus
   - **ohne Ersatzteile** (`is_spare = false`)
4. **Für den Abgleich filtern:** Sets mit `num_parts = 0` (Merchandise, Bundles) und Sonderfarben `-1` und `9999` ausschließen.
5. **Spaltennamen eindeutig machen**, wo Tabellen gleichnamige Spalten haben (`name` in parts, part_categories, colors, sets, themes).
6. **Integritätschecks** ins Skript übernehmen (siehe unten, alle aktuell bestanden).

## parts.csv

- **Zeilen:** 64.944
- **Spalten (von DuckDB erraten):** `part_num` VARCHAR, `name` VARCHAR, `part_cat_id` BIGINT, `part_material` VARCHAR. Alle laut DESCRIBE nullable.
- **`part_num` muss Text sein:** Es gibt führende Nullen (z. B. `003381`). Als Zahl würde daraus `3381` → stille Datenkorruption, Joins passen nicht mehr. DuckDB hat hier richtig geraten (Stichprobe), trotzdem im Build-Skript **explizit als VARCHAR** festlegen.
- Datei ist als **Text** sortiert (beginnt mit `003381`, `003383`, …).
- Die ersten Zeilen sind Aufkleberbögen (`Sticker Sheet for Set …`, Kategorie 58, Material `Plastic`). Nicht jedes „Teil“ ist ein Stein.
- **Teilenummern mit Zusätzen**, z. B. `24323c00pr1129`: `pr…` = bedruckte Variante (Print), `c…` = zusammengesetztes Teil. Bedruckte Varianten haben dieselbe Form wie das Grundteil → für die Formerkennung praktisch dasselbe Teil (Zusammenhang über `part_relationships`).
- **`part_material`-Verteilung:**

  | Material | Anzahl |
  |---|---|
  | Plastic | 59.293 |
  | Cardboard/Paper | 4.179 |
  | Cloth | 991 |
  | Rubber | 324 |
  | Foam | 81 |
  | Flexible Plastic | 49 |
  | Metal | 27 |

  Summe = 64.944 = Gesamtzahl → keine NULL-Werte in `part_material`.
- **Erkenntnis:** Material allein reicht nicht zum Filtern auf Steine. Aufkleberbögen sind als `Plastic` geführt. Für die Auswahl relevanter Teile braucht es die **Kategorien**.

## part_categories.csv

- **Spalten:** `id` (int64), `name` (varchar). Flache Liste ohne Hierarchie.
- **77 Kategorien**, IDs 1–78. **ID 2 fehlt** → IDs sind nicht lückenlos, nicht davon ausgehen.
- **Kategorie 58 = Stickers.**
- Namen bilden informelle Gruppen über Präfixe: `Bricks …`, `Plates …`, `Tiles …`, `Technic …`, `Minifig …`, `Minidoll …`, `Duplo …`.
- **Kandidaten für klassische Steine (abhängig vom Inhalt der Tüte):**
  - Bricks: 11 Bricks, 3 Bricks Sloped, 5 Bricks Special, 6 Bricks Wedged, 20 Bricks Round and Cones, 37 Bricks Curved
  - Plates: 14 Plates, 9 Plates Special, 21 Plates Round Curved and Dishes, 49 Plates Wedged
  - Tiles: 19 Tiles, 15 Tiles Special, 67 Tiles Round and Curved
  - evtl. 8 Technic Bricks, 1 Baseplates
- Klar irrelevant für die Erkennung: Stickers (58), Minifig-/Minidoll-Kategorien, Duplo (4), Non-System Parts (77), Pen & Watch (78) usw.

## JOIN parts ↔ part_categories

- Verbindung: `parts.part_cat_id = part_categories.id` funktioniert.
- **Namenskonflikt:** Beide Tabellen haben eine Spalte `name` → in Abfragen und in der späteren Datenbank eindeutig benennen (z. B. Kategorie als `category_name`).
- Bei `SELECT *` erscheint der Schlüssel doppelt (`part_cat_id` und `id`).

### Teile pro Kategorie (Auszug)

| Kategorie | Teile |
|---|---|
| Minifig Upper Body | 7.883 |
| Minifig Heads | 5.425 |
| Duplo, Quatro and Primo | 5.203 |
| Gear Parts | 5.056 |
| Stickers | 4.659 |
| Tiles | 3.724 |
| Minifig Lower Body | 3.257 |
| Bricks | 1.829 |
| Tiles Round and Curved | 1.290 |
| Bricks Curved | 899 |
| Bricks Round and Cones | 734 |
| Bricks Sloped | 647 |
| Tiles Special | 524 |
| Plates Special | 499 |
| Bricks Wedged | 480 |
| Plates Round Curved and Dishes | 391 |
| Bricks Special | 327 |
| Plates | 148 |
| Plates Wedged | 79 |
| Technic Bricks | 29 |

- **Ergebnis hat 76 Zeilen, es gibt aber 77 Kategorien** → eine Kategorie hat keine Teile (verschwindet beim INNER JOIN). Für das Projekt unwichtig.
- **Drucke blähen die Zahlen auf:** Tiles (3.724) und Bricks (1.829) haben viel mehr Einträge als Plates (148), weil Fliesen und Steine oft bedruckt werden, Platten kaum. Minifig-Kategorien ebenso. Die Zahl der unterschiedlichen *Formen* ist deutlich kleiner.

## colors.csv

- **Zeilen:** 275, IDs von -1 bis 1147 plus 9999 → **stark lückenhaft**.
- **Spalten:** `id` BIGINT, `name` VARCHAR, `rgb` VARCHAR, `is_trans` BOOLEAN, `num_parts` BIGINT, `num_sets` BIGINT, `y1` BIGINT, `y2` BIGINT. Alle nullable.
- **Zwei Sonderfarben, keine echten Farben:**
  - `-1` „[Unknown]“ (17 Teile, 2 Sets)
  - `9999` „[No Color/Any Color]“ (10.979 Teile, 10.732 Sets) – für Teile ohne Farbangabe (z. B. `stickerupn0077` in `inventory_parts`)
  - → beim Abgleich ausschließen bzw. gesondert behandeln. **Über die ID filtern, nicht über `rgb`:** 9999 hat denselben RGB-Wert wie Black (`05131D`).
- **`rgb`** ist ein Hex-Wert ohne `#` (z. B. `05131D`) → muss **Text** bleiben (führende Nullen wie `0033B2`). **Groß-/Kleinschreibung uneinheitlich** (`5d5c36` vs. `05131D`) → beim Vergleichen normalisieren (z. B. `upper()`). Für die Farberkennung später in drei Zahlen R, G, B umrechnen.
- **`is_trans`**: transparente Farben. Für die Bilderkennung schwierig (Hintergrund scheint durch).
- **`num_parts` / `num_sets`**: von Rebrickable vorberechnete Häufigkeiten (Black: ~850.000 Teile in ~235.000 Sets). Nützlich für die Gewichtung beim Abgleich (seltene Farben = aussagekräftiger). Unklar, ob Ersatzteile/Drucke mitgezählt sind → im Zweifel selbst aus `inventory_parts` berechnen.
- **`y1` / `y2`**: erstes und letztes Jahr, in dem die Farbe verwendet wurde. **`y2` = 2027** kommt vor → die Daten enthalten bereits angekündigte Sets der Zukunft. Kurzlebige Farben wie die Neonfarben (1997–1999).
- **Alte vs. neue Farben:** „Light Gray“ (bis 2007) und „Dark Gray“ (bis 2006) sowie „Brown“ (bis 2006) sind alte Farben, die LEGO um 2004 durch neue Töne ersetzt hat. Optisch sehr ähnlich → relevant für Farberkennung und Abgleich mit älteren Sets.

## sets.csv

- **Zeilen:** 28.561, **Jahre 1949–2027** (2027 = bereits angekündigte Sets).
- **Spalten:** `set_num` VARCHAR, `name` VARCHAR, `year` BIGINT, `theme_id` BIGINT, `num_parts` BIGINT, `img_url` VARCHAR. Alle nullable.
- **`set_num`** = Nummer + `-` + Variante (z. B. `0011-2`, `0011-3`: gleiche Grundnummer, unterschiedliche Ausgaben). Durch den Bindestrich eindeutig Text, trotzdem **explizit als VARCHAR** festlegen. Führende Nullen kommen vor (`001-1`).
- **8.384 Sets mit `num_parts = 0`** (rund **29 %**). Bestätigt über die Themen: fast ausschließlich **Merchandise**. Top-Themen: Bags, Totes & Luggage (1.004), Key Chain (803), Clothing & Footwear (711), Stationery and Office Supplies (691), Houseware (626), Gear (564), Story Books (386), Video Games and Accessories (277), Activity Books (261), Role Play Toys and Costumes (240), Plush Toys (175), Storage (138), Bag and Luggage Tags (135), Non-fiction Books (130), Tabletop Games and Puzzles (118).
- Weitere Nicht-Sets mit wenigen Teilen: Bücher mit beigelegter Figur („Ninjago: Book of Adventures“, 1 Teil), Bundles („Castle 2 for 1 Bonus Offer“, 0 Teile).
- → **Für den Abgleich `num_parts > 0` filtern**, ggf. zusätzlich Merchandise-Themen ausschließen.
- **`num_parts`** ist Rebrickables eigene Zählung. Unklar, ob sie mit der Summe aus `inventory_parts` übereinstimmt (Ersatzteile, Minifiguren) → bei Bedarf prüfen.
- **`img_url`**: Link auf ein Bild des Sets bei Rebrickable → nützlich, um gefundene Sets später in der Streamlit-App anzuzeigen (braucht Internet).
- **`theme_id`** verweist auf `themes.id`.

## themes.csv

- **Zeilen:** 496, davon **150 Hauptthemen** (`parent_id` ist NULL).
- **Spalten:** `id` BIGINT, `name` VARCHAR, `parent_id` BIGINT.
- **Hierarchie über Selbstbezug:** `parent_id` zeigt auf ein anderes Thema derselben Tabelle (z. B. „Competition“, „Expert Builder“ → Elternthema 1 „Technic“). Kann über mehrere Ebenen gehen.
- **Themennamen sind nicht eindeutig:** „Star Wars“ (id 18) ist ein Unterthema von Technic, daneben gibt es das Hauptthema Star Wars. → Immer über die **ID** arbeiten, nie über den Namen.

## inventories.csv

- **Zeilen:** 47.858
- **Spalten:** `id` BIGINT, `version` BIGINT, `set_num` VARCHAR.
- **Versionen:** 45.903 × Version 1, 1.289 × Version 2, bis maximal Version 12. **1.293 Sets haben mehr als ein Inventar.** Da es mehr Sets mit mehreren Inventaren als Version-2-Einträge gibt, fehlen bei einigen Sets Versionsnummern dazwischen → pro Set die **kleinste vorhandene Version** nehmen statt fest `version = 1`.
- **17.344 Inventare ohne passendes Set:** `set_num` wie `fig-000007` → **Inventare von Minifiguren** (gehören zu `minifigs.csv`, die wir bewusst weglassen). Fallen beim JOIN mit `sets` automatisch raus. Folge: Minifiguren-Teile zählen nicht zu den Set-Stücklisten. Für die Steinerkennung unproblematisch.

## inventory_parts.csv

- **Zeilen:** 1.572.772 → mit Abstand die größte Tabelle.
- **Spalten:** `inventory_id` BIGINT, `part_num` VARCHAR, `color_id` BIGINT, `quantity` BIGINT, `is_spare` BOOLEAN, `img_url` VARCHAR.
- **Ersatzteile:** 112.096 Zeilen mit `is_spare = true` (rund 7 %), 1.460.676 ohne. `is_spare` wird korrekt als BOOLEAN erkannt.
- **`img_url`**: Bild des Teils in genau dieser Farbe (teilweise NULL). Evtl. nützlich für die App oder als Vergleichsbild.

## Integritätschecks (alle bestanden)

| Check | Ergebnis |
|---|---|
| Jedes Teil hat eine gültige Kategorie (JOIN-Zeilen = 64.944) | ✅ 64.944 |
| `inventory_parts` verweist nur auf existierende Teile | ✅ 0 unbekannte |
| `inventory_parts` verweist nur auf existierende Farben | ✅ 0 unbekannte |
| `inventories` → `sets` | ❗ 17.344 ohne Set, erklärt durch Minifiguren-Inventare (gewollt) |
