# core/config/bootstrap.py
from pathlib import Path
import configparser, os

ROOT = Path(__file__).resolve().parents[2]
CFG  = ROOT / "qmtool.cfg"

def bootstrap_db_path() -> Path:
    """Return SQLite path from env or qmtool.cfg or fallback."""
    if (env := os.getenv("QMTOOL_DB")):
        return Path(env).expanduser()

    if CFG.exists():
        p = configparser.ConfigParser()
        p.read(CFG, encoding="utf-8")
        if p.has_option("bootstrap", "db_path"):
            return Path(p.get("bootstrap", "db_path")).expanduser()

    # last fallback: project default
    return ROOT / "databases" / "qm-tool.db"
