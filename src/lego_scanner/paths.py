"""Zentrale Pfade des Projekts.

Alle Module importieren ihre Pfade von hier, damit Speicherorte nur an
einer Stelle festgelegt sind. Die Pfade werden über ``__file__`` relativ
zu dieser Datei berechnet und funktionieren daher unabhängig davon, aus
welchem Verzeichnis ein Skript gestartet wird.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT/"data"
RAW_DIR = DATA_DIR/"raw"
DB_PATH = DATA_DIR/"lego.duckdb"
