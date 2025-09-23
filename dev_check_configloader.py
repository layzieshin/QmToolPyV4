# dev_check_configloader.py
import sys, traceback, pathlib

# Ensure project root is importable (points to directory that contains "core/")
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("=== Check 1: config_loader symbols & types ===")
try:
    from core.config.config_loader import INI_PATH, _DEFAULT_INI_CONTENT, config_loader
    print("INI_PATH ->", type(INI_PATH).__name__, INI_PATH)
    k = list(_DEFAULT_INI_CONTENT.keys())[:3] if hasattr(_DEFAULT_INI_CONTENT, "keys") else []
    print("_DEFAULT_INI_CONTENT ->", type(_DEFAULT_INI_CONTENT).__name__, f"sections(sample)={k}")
    print("_config present? ", hasattr(config_loader, "_config"))
    print("_load_config present? ", hasattr(config_loader, "_load_config"))
    print("CHECK 1: OK\n")
except Exception:
    print("CHECK 1: FAILED\n")
    traceback.print_exc()

print("=== Check 2: import settings view ===")
try:
    import core.config.gui.config_settings_view as view
    print("config_settings_view import: OK")
except Exception:
    print("CHECK 2: FAILED")
    traceback.print_exc()
from core.config.config_loader import QM_DB_PATH, LOG_DB_PATH
print("QM DB:", QM_DB_PATH)
print("LOG DB:", LOG_DB_PATH)
