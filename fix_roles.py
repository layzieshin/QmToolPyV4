# fix_roles.py  – einmalig ausführen
import sqlite3
from core.config.config_loader import config_loader

db_path = config_loader.get_config_value("Database", "qm_tool")
sql = """
UPDATE users
SET role = 'USER'
WHERE role NOT IN ('ADMIN', 'USER', 'GUEST');
"""

with sqlite3.connect(db_path) as conn:
    affected = conn.execute(sql).rowcount
    conn.commit()

print(f"{affected} Datensätze korrigiert.")
