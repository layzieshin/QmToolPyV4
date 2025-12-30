"""
core/common/module_repository.py
================================

SQLite-Persistenz + Meta-Import + Auto-Scan-Hooks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from core.config.config_loader import QM_DB_PATH
from core.logging.logic.logger import logger
from core.common.module_descriptor import ModuleDescriptor
from core.common.module_auto_discovery import discover_meta_files, default_roots
from core.common.db_interface import SQLiteRepository


class ModuleRepository(SQLiteRepository):
    def __init__(self) -> None:
        super().__init__(QM_DB_PATH, check_same_thread=False)
        self._ensure_schema()

    # ---------------- Schema ---------------- #
    def _ensure_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS modules (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                module_path TEXT NOT NULL,
                class_name TEXT NOT NULL,
                version TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                is_core INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 999,
                visible_for TEXT NOT NULL DEFAULT '["Admin","QMB","User"]',
                settings_for TEXT NOT NULL DEFAULT '["Admin"]',
                requires_login INTEGER NOT NULL DEFAULT 1,
                permissions TEXT
            )
            """
        )
        self.conn.commit()

        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(modules)")}
        if "settings_class" not in cols:
            self.conn.execute("ALTER TABLE modules ADD COLUMN settings_class TEXT")
        if "meta_path" not in cols:
            self.conn.execute("ALTER TABLE modules ADD COLUMN meta_path TEXT")
        if "license_required" not in cols:
            self.conn.execute("ALTER TABLE modules ADD COLUMN license_required INTEGER NOT NULL DEFAULT 0")
        if "license_tag" not in cols:
            self.conn.execute("ALTER TABLE modules ADD COLUMN license_tag TEXT")
        self.conn.commit()

    # ---------------- CRUD ------------------- #
    def upsert(self, desc: ModuleDescriptor) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO modules (
                    id, label, module_path, class_name, version, enabled, is_core,
                    sort_order, visible_for, settings_for, requires_login, permissions,
                    settings_class, meta_path, license_required, license_tag
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    label=excluded.label,
                    module_path=excluded.module_path,
                    class_name=excluded.class_name,
                    version=excluded.version,
                    enabled=excluded.enabled,
                    is_core=excluded.is_core,
                    sort_order=excluded.sort_order,
                    visible_for=excluded.visible_for,
                    settings_for=excluded.settings_for,
                    requires_login=excluded.requires_login,
                    permissions=excluded.permissions,
                    settings_class=excluded.settings_class,
                    meta_path=excluded.meta_path,
                    license_required=excluded.license_required,
                    license_tag=excluded.license_tag
                """,
                (
                    desc.id,
                    desc.label,
                    desc.module_path,
                    desc.class_name,
                    desc.version,
                    desc.enabled,
                    desc.is_core,
                    desc.sort_order,
                    desc.visible_for,
                    desc.settings_for,
                    desc.requires_login,
                    desc.permissions,
                    desc.settings_class,
                    desc.meta_path,
                    desc.license_required,
                    desc.license_tag,
                ),
            )

    def get_by_id(self, module_id: str) -> Optional[ModuleDescriptor]:
        row = self.conn.execute("SELECT * FROM modules WHERE id=?", (module_id,)).fetchone()
        return ModuleDescriptor.from_row(row) if row else None

    def delete(self, module_id: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM modules WHERE id=?", (module_id,))

    def all_modules(self, *, enabled_only: bool = False) -> List[ModuleDescriptor]:
        sql = "SELECT * FROM modules"
        if enabled_only:
            sql += " WHERE enabled=1"
        sql += " ORDER BY is_core DESC, sort_order ASC, label ASC"
        cur = self.conn.execute(sql)
        return [ModuleDescriptor.from_row(r) for r in cur.fetchall()]

    # ---------------- Meta-Import ----------- #
    def upsert_from_meta(self, meta_path: Path) -> ModuleDescriptor:
        desc = ModuleDescriptor.from_meta_json(meta_path)
        self.upsert(desc)
        logger.log("ModuleRepository", "UpsertFromMeta", message=f"{desc.id}:{desc.version}")
        return desc

    def discover_and_register(self, roots: Iterable[Path] | None = None) -> int:
        """
        Sucht meta.json Dateien und trägt/aktualisiert Module in der DB.
        Gibt Anzahl verarbeiteter Einträge zurück.
        """
        meta_files = discover_meta_files(list(roots) if roots else default_roots())
        count = 0
        for meta in meta_files:
            try:
                self.upsert_from_meta(meta)
                count += 1
            except Exception as exc:  # noqa: BLE001
                logger.log("ModuleRepository", "MetaImportFailed", message=f"{meta}: {exc}")
        if count:
            logger.log("ModuleRepository", "AutoDiscovery", message=f"{count} modules registered/updated")
        return count
