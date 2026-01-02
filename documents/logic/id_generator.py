from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from documents.adapters.database_adapter import DatabaseAdapter


class IdGenerator:
    def __init__(self, db: "DatabaseAdapter", prefix: str, pattern: str) -> None:
        self._db = db
        self._prefix = prefix
        self._pattern = pattern
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS sequences (
                year INTEGER NOT NULL,
                prefix TEXT NOT NULL,
                seq INTEGER NOT NULL,
                PRIMARY KEY (year, prefix)
            )
        """)

    def next_id(self) -> str:
        year = datetime.utcnow().year

        row = self._db.fetchone(
            "SELECT seq FROM sequences WHERE year=? AND prefix=?",
            (year, self._prefix)
        )

        if row is None:
            seq = 1
            self._db.execute(
                "INSERT INTO sequences(year,prefix,seq) VALUES (?,?,?)",
                (year, self._prefix, seq)
            )
            self._db.commit()
        else:
            seq = int(row["seq"]) + 1
            self._db.execute(
                "UPDATE sequences SET seq=? WHERE year=? AND prefix=?",
                (seq, year, self._prefix)
            )
            self._db.commit()

        # Format ID
        token = self._pattern.replace("{YYYY}", str(year))
        import re
        m = re.search(r"\{seq: (\d+)d\}", token)
        if m:
            width = int(m.group(1))
            token = re.sub(r"\{seq:\d+d\}", f"{seq:0{width}d}", token)
        else:
            token = token.replace("{seq}", str(seq))

        return f"{self._prefix}-{token}"