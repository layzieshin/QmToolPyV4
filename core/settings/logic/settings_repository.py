from __future__ import annotations
import json, sqlite3
from threading import RLock
from typing import Any, Final
from core.config.config_loader import QM_DB_PATH
from core.logging.logic.logger import logger

def _to_json(v: Any) -> str:            # serialisieren
    try: return json.dumps(v)
    except TypeError: return json.dumps(str(v))

def _from_json(txt: str) -> Any:        # deserialisieren
    try: return json.loads(txt)
    except Exception: return txt        # noqa: BLE001

# ------------------------------------------------------------------ #
class SettingsRepository:
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
        self.conn = sqlite3.connect(QM_DB_PATH.as_posix(), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
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
        """Erstellt settings_new, kopiert Daten spalten-agnostisch, tauscht Tabellen."""
        logger.log("SettingsRepo", "HardRebuild", message="start")
        cur = self.conn.execute("PRAGMA table_info(settings)")
        legacy_cols = [r["name"] for r in cur.fetchall()]            # z. B. ['section','key','value']

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

        # Spalten-Mapping bauen
        select_cols = []
        if "section" in legacy_cols:        # Ur-alt
            select_cols.append("section AS namespace")
        elif "namespace" in legacy_cols:
            select_cols.append("namespace")
        else:
            select_cols.append("'' AS namespace")
        select_cols += [                   # key & value gibt es in jedem Schema
            "key", "value",
        ]
        if "user_id" in legacy_cols:
            select_cols.append("user_id")
        else:
            select_cols.append("NULL AS user_id")

        self.conn.execute(
            f"""
            INSERT INTO settings_new(namespace,key,value,user_id)
            SELECT {', '.join(select_cols)} FROM settings
            """
        )
        self.conn.execute("DROP TABLE settings")
        self.conn.execute("ALTER TABLE settings_new RENAME TO settings")
        self.conn.commit()
        logger.log("SettingsRepo", "HardRebuild", message="done")
