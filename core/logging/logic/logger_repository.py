"""
logger_repository.py

Repository for all database operations related to logging.
Handles connection, table creation, and all CRUD for log entries.
"""

import sqlite3
from typing import Optional, List, Dict, Any, Tuple

class LoggerRepository:
    """
    Repository class for database access to logs.
    """

    def __init__(self, db_path: str):
        """
        Initialize repository and ensure logs table exists.
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        """
        Creates the logs table if it does not exist.
        """
        sql = """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_id INTEGER,
            username TEXT,
            feature TEXT NOT NULL,
            event TEXT NOT NULL,
            reference_id TEXT,
            message TEXT,
            log_level TEXT DEFAULT 'INFO'
        );
        """
        with self.conn:
            self.conn.execute(sql)

    def insert_log(self, timestamp: str, user_id: Optional[int], username: Optional[str],
                   feature: str, event: str, reference_id: Optional[str], message: Optional[str],
                   log_level: str) -> int:
        """
        Insert a new log entry.
        """
        sql = """
        INSERT INTO logs (timestamp, user_id, username, feature, event, reference_id, message, log_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        cur = self.conn.cursor()
        cur.execute(sql, (timestamp, user_id, username, feature, event, reference_id, message, log_level))
        self.conn.commit()
        return cur.lastrowid

    def query_logs(self,
                   filters: Optional[List[Tuple[str, str, Any]]] = None,
                   limit: Optional[int] = 1000,
                   offset: int = 0,
                   order_by: str = "timestamp",
                   ascending: bool = False) -> List[Dict[str, Any]]:
        """
        Query log entries with flexible filters.
        """
        filters = filters or []
        conditions = []
        params = []
        allowed_operators = {"=", "!=", "<", ">", "<=", ">="}
        for col, op, val in filters:
            if op not in allowed_operators:
                raise ValueError(f"Invalid operator '{op}' in filter for column '{col}'.")
            conditions.append(f"{col} {op} ?")
            params.append(val)
        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        order_dir = "ASC" if ascending else "DESC"
        query = f"""
        SELECT * FROM logs
        {where_clause}
        ORDER BY {order_by} {order_dir}
        """
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        else:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)
        cur = self.conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def delete_logs_by_ids(self, ids: List[int]) -> int:
        """
        Delete logs by a list of IDs.
        """
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        sql = f"DELETE FROM logs WHERE id IN ({placeholders});"
        cur = self.conn.cursor()
        cur.execute(sql, ids)
        self.conn.commit()
        return cur.rowcount

    def delete_logs_older_than(self, timestamp: str) -> int:
        """
        Delete all logs older than a given timestamp.
        """
        sql = "DELETE FROM logs WHERE timestamp < ?;"
        cur = self.conn.cursor()
        cur.execute(sql, (timestamp,))
        self.conn.commit()
        return cur.rowcount

    def close(self):
        """
        Close the DB connection.
        """
        if self.conn:
            self.conn.close()
            self.conn = None
