# tools/smoke_import_signature.py
import importlib

def must_import(path: str):
    mod_path, _, cls_name = path.rpartition(".")
    print(f"Trying import: {path}")
    m = importlib.import_module(mod_path)
    cls = getattr(m, cls_name)
    print(f"  OK: {cls}")

if __name__ == "__main__":
    must_import("signature.gui.signature_view.SignatureView")
    must_import("signature.gui.signature_settings_view.SignatureSettingsView")
    print("All good.")
