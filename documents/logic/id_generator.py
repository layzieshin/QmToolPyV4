from __future__ import annotations

import re
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
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sequences (
                year INTEGER NOT NULL,
                prefix TEXT NOT NULL,
                seq INTEGER NOT NULL,
                PRIMARY KEY (year, prefix)
            );
            """
        )

    def next_id(self) -> str:
        year = datetime.utcnow().year

        row = self._db.fetchone(
            "SELECT seq FROM sequences WHERE year=? AND prefix=?",
            (year, self._prefix)
        )

        if row is None:
            # If the sequence row does not exist yet for (year, prefix), try to
            # continue from existing documents to avoid collisions with a pre-seeded DB.
            like_pattern = f"{self._prefix}-{year}-%"
            last = self._db.fetchone(
                "SELECT doc_id FROM documents WHERE doc_id LIKE ?  ORDER BY doc_id DESC LIMIT 1",
                (like_pattern,)
            )

            base = 0
            if last and last. get("doc_id"):
                try:
                    last_id = str(last["doc_id"])
                    seq_part = last_id.split("-")[-1]
                    base = int(seq_part)
                except Exception:
                    base = 0

            seq = base + 1
            self._db.execute(
                "INSERT INTO sequences(year,prefix,seq) VALUES (?,?,?)",
                (year, self._prefix, seq)
            )
            self._db. commit()
        else:
            seq = int(row["seq"]) + 1
            self._db.execute(
                "UPDATE sequences SET seq=? WHERE year=? AND prefix=?",
                (seq, year, self._prefix)
            )
            self._db.commit()

        # Format ID
        token = self._pattern.replace("{YYYY}", str(year))

        # Support both "{seq: 04d}" and "{seq:  04d}" (with optional whitespace)
        # Pattern: {seq:  ? (\d+)d}
        m = re.search(r"\{seq:\s*(\d+)d\}", token)
        if m:
            width = int(m.group(1))
            token = re.sub(r"\{seq:\s*\d+d\}", f"{seq:0{width}d}", token)
        else:
            token = token.replace("{seq}", str(seq))

        return f"{self._prefix}-{token}"