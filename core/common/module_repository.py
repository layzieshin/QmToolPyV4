"""
core/common/module_repository.py
================================

SQLite-Repository für die Tabelle *modules*.

• Erstellt / migriert das Schema:
    – Umbenennung der alten Spalte "order" → "sort_order".
• Importiert einmalig Module aus modules.json (falls Tabelle leer).
• Bietet CRUD-Methoden für Admin-UIs.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from core.config.config_loader import MODULES_JSON_PATH, QM_DB_PATH
from core.common.module_descriptor import ModuleDescriptor
from core.logging.logic.logger import logger


class ModuleRepository:
    """Singleton-Zugriff auf die *modules*-Tabelle."""

    _instance: "ModuleRepository | None" = None

    # ------------------------------------------------------------------ #
    #  Singleton-Erzeugung                                               #
    # ------------------------------------------------------------------ #
    def __new__(cls) -> "ModuleRepository":  # noqa: D401
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ------------------------------------------------------------------ #
    #  Initialisierung                                                   #
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.conn = sqlite3.connect(QM_DB_PATH.as_posix())
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()
        self._migrate_from_json_if_needed()

    # ------------------------------------------------------------------ #
    #  Öffentliche API                                                   #
    # ------------------------------------------------------------------ #
    def all_modules(self) -> list[ModuleDescriptor]:
        rows = self.conn.execute("SELECT * FROM modules").fetchall()
        return [ModuleDescriptor.from_row(row) for row in rows]

    def enabled_modules(self) -> list[ModuleDescriptor]:
        rows = self.conn.execute(
            "SELECT * FROM modules WHERE enabled = 1 ORDER BY sort_order"
        ).fetchall()
        return [ModuleDescriptor.from_row(row) for row in rows]

    def upsert(self, desc: ModuleDescriptor) -> None:
        """Insert oder Update per Primärschlüssel ``id``."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO modules (
                    id, label, module_path, class_name,
                    enabled, is_core, sort_order,
                    visible_for, settings_for, requires_login, permissions
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO
                UPDATE SET
                    label          = excluded.label,
                    module_path    = excluded.module_path,
                    class_name     = excluded.class_name,
                    enabled        = excluded.enabled,
                    sort_order     = excluded.sort_order,
                    visible_for    = excluded.visible_for,
                    settings_for   = excluded.settings_for,
                    requires_login = excluded.requires_login,
                    permissions    = excluded.permissions
                """,
                desc.to_row(),
            )

    # ------------------------------------------------------------------ #
    #  Interne Helfer                                                    #
    # ------------------------------------------------------------------ #
    def _ensure_schema(self) -> None:
        """Stellt sicher, dass Schema & evtl. Spalten-Rename vorhanden sind."""
        # 1) Tabelle anlegen, falls sie noch nicht existiert
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS modules (
                id            TEXT PRIMARY KEY,
                label         TEXT NOT NULL,
                module_path   TEXT NOT NULL,
                class_name    TEXT NOT NULL,
                enabled       INTEGER NOT NULL DEFAULT 1,
                is_core       INTEGER NOT NULL DEFAULT 0,
                sort_order    INTEGER NOT NULL DEFAULT 100,
                visible_for   TEXT NOT NULL DEFAULT '["Admin","QMB","User"]',
                settings_for  TEXT NOT NULL DEFAULT '["Admin"]',
                requires_login INTEGER NOT NULL DEFAULT 1,
                permissions   TEXT
            )
            """
        )
        self.conn.commit()

        # 2) Prüfen, ob noch eine alte Spalte "order" existiert ➜ umbenennen
        cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(modules)")}
        if "order" in cols and "sort_order" not in cols:
            try:
                self.conn.execute('ALTER TABLE modules RENAME COLUMN "order" TO sort_order')
                self.conn.commit()
                logger.log("ModuleRepository", "SchemaMigration", message='Renamed column "order" ➜ sort_order')
            except sqlite3.OperationalError as exc:
                # Alte SQLite-Version?  -> Meldung loggen, aber App weiterlaufen lassen
                logger.log("ModuleRepository", "SchemaMigrationFailed", message=str(exc))

    def _migrate_from_json_if_needed(self) -> None:
        """Einmaliger Import der alten *modules.json*, falls Tabelle leer."""
        if not MODULES_JSON_PATH.exists():
            return
        if self.conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0] > 0:
            return  # Tabelle schon befüllt

        data: Iterable[dict[str, Any]] = json.loads(MODULES_JSON_PATH.read_text("utf-8"))
        for entry in data:
            desc = ModuleDescriptor(
                id=entry["id"],
                label=entry["label"],
                module_path=entry["module"],
                class_name=entry["class"],
                enabled=1,
                is_core=1 if entry.get("is_core") else 0,
                sort_order=entry.get("order", 100),
                visible_for='["Admin","QMB","User"]',
                settings_for='["Admin"]',
                requires_login=1 if entry.get("requires_login", True) else 0,
                permissions=None,
            )
            self.upsert(desc)

        MODULES_JSON_PATH.rename(MODULES_JSON_PATH.with_suffix(".migrated.json"))
