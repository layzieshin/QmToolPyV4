from __future__ import annotations
import json, sqlite3
from threading import RLock
from typing import Any, Final
from core.config.config_loader import QM_DB_PATH
from core.logging.logic.logger import logger
from core.common.db_interface import SQLiteRepository

def _to_json(v: Any) -> str:            # serialisieren
    try: return json.dumps(v)
    except TypeError: return json.dumps(str(v))

def _from_json(txt: str) -> Any:        # deserialisieren
    try: return json.loads(txt)
    except Exception: return txt        # noqa: BLE001

# ------------------------------------------------------------------ #
class SettingsRepository(SQLiteRepository):
    _inst: "SettingsRepository|None" = None
    _lock: Final[RLock] = RLock()

    def __new__(cls):                   # Singleton
        with cls._lock:
            if cls._inst is None:
                cls._inst = super().__new__(cls)
        return cls._inst

    def __init__(self) -> None:
        if getattr(self, "_ready", False): return
        self._ready = True
        super().__init__(QM_DB_PATH, check_same_thread=False)
        self._ensure_schema()

    # ------------------------- öffentliche API ----------------------- #
    def get(self, ns: str, key: str, uid: str | None, fb: Any = None) -> Any | None:
        try:
            row = self.conn.execute(
                "SELECT value FROM settings WHERE namespace=? AND key=? AND user_id IS ?",
                (ns, key, uid),
            ).fetchone()
            return _from_json(row["value"]) if row else fb
        except sqlite3.OperationalError as exc:
            if "namespace" in str(exc): self._hard_rebuild(); return self.get(ns, key, uid, fb)
            raise

    def set(self, ns: str, key: str, val: Any, uid: str | None) -> None:
        try:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO settings (namespace,key,value,user_id)
                    VALUES (?,?,?,?)
                    ON CONFLICT(namespace,key,user_id) DO
                    UPDATE SET value=excluded.value
                    """,
                    (ns, key, _to_json(val), uid),
                )
        except sqlite3.OperationalError as exc:
            if "namespace" in str(exc): self._hard_rebuild(); self.set(ns, key, val, uid)
            else: raise

    def delete(self, ns: str, key: str, uid: str | None) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM settings WHERE namespace=? AND key=? AND user_id IS ?",
                (ns, key, uid),
            )

    # ------------------------- Schema / Migration -------------------- #
    def _ensure_schema(self) -> None:
        # Normales Ziel-Schema
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings(
                namespace TEXT NOT NULL,
                key       TEXT NOT NULL,
                value     TEXT NOT NULL,
                user_id   TEXT,
                PRIMARY KEY(namespace,key,user_id)
            )
            """
        )
        self.conn.commit()

        cols = {c["name"] for c in self.conn.execute("PRAGMA table_info(settings)")}
        if "namespace" not in cols or "user_id" not in cols:
            self._hard_rebuild()

    # ------------------------- HARDR E B U I L D --------------------- #
    def _hard_rebuild(self) -> None:
        """Rebuild für alle denkbaren Alt-Schemata: section, namespace oder gar nichts."""
        logger.log("SettingsRepo", "HardRebuild", message="start")

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings_new(
                namespace TEXT NOT NULL,
                key       TEXT NOT NULL,
                value     TEXT NOT NULL,
                user_id   TEXT,
                PRIMARY KEY(namespace,key,user_id)
            )
            """
        )

        cur = self.conn.execute("PRAGMA table_info(settings)")
        legacy_cols = {r["name"] for r in cur.fetchall()}

        if "section" in legacy_cols:
            # GANZ alt
            select = "SELECT section AS namespace, key, value, NULL AS user_id FROM settings GROUP BY section, key"
        elif "namespace" in legacy_cols:
            select = "SELECT namespace, key, value, COALESCE(user_id,NULL) AS user_id FROM settings GROUP BY namespace, key, user_id"
        elif "key" in legacy_cols and "value" in legacy_cols:
            # Nur key, value – wir nehmen "app" als Standard-Namespace
            select = "SELECT 'app' AS namespace, key, value, NULL AS user_id FROM settings GROUP BY key"
        else:
            # Nichts passt, Tabelle einfach löschen
            self.conn.execute("DROP TABLE settings")
            self.conn.execute("ALTER TABLE settings_new RENAME TO settings")
            self.conn.commit()
            logger.log("SettingsRepo", "HardRebuild", message="reset blank")
            return

        self.conn.execute(f"INSERT OR REPLACE INTO settings_new(namespace,key,value,user_id) {select}")
        self.conn.execute("DROP TABLE settings")
        self.conn.execute("ALTER TABLE settings_new RENAME TO settings")
        self.conn.commit()
        logger.log("SettingsRepo", "HardRebuild", message="done")
