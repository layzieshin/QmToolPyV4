from __future__ import annotations

from datetime import datetime
from sqlite3 import Connection


class IdGenerator:
    def __init__(self, conn: Connection, prefix: str, pattern: str) -> None:
        self._c = conn
        self._prefix = prefix
        self._pattern = pattern
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._c.execute("""
            CREATE TABLE IF NOT EXISTS sequences (
                year INTEGER NOT NULL,
                prefix TEXT NOT NULL,
                seq INTEGER NOT NULL,
                PRIMARY KEY (year, prefix)
            )
        """)

    def next_id(self) -> str:
        year = datetime.utcnow().year
        row = self._c.execute("SELECT seq FROM sequences WHERE year=? AND prefix=?",
                              (year, self._prefix)).fetchone()
        if row is None:
            seq = 1
            self._c.execute("INSERT INTO sequences(year,prefix,seq) VALUES (?,?,?)", (year, self._prefix, seq))
        else:
            seq = int(row[0]) + 1
            self._c.execute("UPDATE sequences SET seq=? WHERE year=? AND prefix=?", (seq, year, self._prefix))
        token = self._pattern.replace("{YYYY}", str(year))
        if "{seq" in token:
            import re
            m = re.search(r"\{seq:(\d+)d\}", token)
            if m:
                width = int(m.group(1))
                token = re.sub(r"\{seq:\d+d\}", f"{seq:0{width}d}", token)
            else:
                token = token.replace("{seq}", str(seq))
        return f"{self._prefix}-{token}"
