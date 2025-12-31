from core.qm_logging.models.log_entry import LogEntry
from core.config.config_loader import config_loader
from core.common.db_interface import SQLiteRepository

logs_db_path = config_loader.get_logging_db_path()


class LoggerRepository(SQLiteRepository):
    def __init__(self):
        # Ableiten aus der Haupt-DB (aber eigene Datei)
        #self.db_path = db_path.parent / "logs.db"

        # Optional: Debug-Ausgabe nur wenn aktiviert
        from core.config.config_loader import config_loader
       # if config_loader.get_bool("General", "debug_db_paths", False):
        print(f"[DEBUG] Logger DB ➡ {logs_db_path}")

        super().__init__(logs_db_path)
        self._ensure_db()

    def _ensure_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                feature TEXT NOT NULL,
                event TEXT NOT NULL,
                user_id INTEGER,
                username TEXT,
                reference_id TEXT,
                message TEXT,
                log_level TEXT NOT NULL DEFAULT 'INFO'
            )
        """)
        self.conn.commit()

    def insert_log(self, entry: LogEntry):
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO logs
               (timestamp, feature, event, user_id, username, reference_id, message, log_level)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.timestamp,
                entry.feature,
                entry.event,
                entry.user_id,
                entry.username,
                entry.reference_id,
                entry.message,
                entry.log_level,
            )
        )
        self.conn.commit()

    def fetch_logs(self, limit=100):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        return [LogEntry.from_dict(dict(row)) for row in rows]

    def query_logs(self, user_id=None, username=None, feature=None, level=None,
                   start_time=None, end_time=None, limit=1000):
        cursor = self.conn.cursor()
        query = "SELECT * FROM logs WHERE 1=1"
        params = []

        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        if username is not None:
            query += " AND username = ?"
            params.append(username)
        if feature is not None:
            query += " AND feature = ?"
            params.append(feature)
        if level is not None:
            query += " AND log_level = ?"
            params.append(level)
        if start_time is not None:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time is not None:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [LogEntry.from_dict(dict(row)) for row in rows]

    def clear_logs(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM logs")
        self.conn.commit()
