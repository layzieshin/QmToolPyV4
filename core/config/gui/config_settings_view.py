"""
core/config/gui/config_settings_view.py
=======================================

Admin-only GUI zur Pflege der globalen INI-Konfiguration.

• Liest / schreibt via ConfigLoader
• Backup / Restore in ConfigRepository
• Neue Pfade: modules_json, labels_tsv
• AppContext wird vollständig genutzt (Übersetzung + Username-Logging)
"""

from __future__ import annotations

# ----------------------------------------------------------- #
#  Imports                                                    #
# ----------------------------------------------------------- #
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from core.config.config_loader import (
    config_loader,
    _DEFAULT_INI_CONTENT,
    INI_PATH,
)
from core.config.config_repository import ConfigRepository
from core.logging.logic.logger import logger
from core.common.app_context import T, AppContext

# ----------------------------------------------------------- #
#  Konstanten                                                 #
# ----------------------------------------------------------- #
MANDATORY_FIELDS: list[tuple[str, str]] = [
    ("Database", "qm_tool"),
    ("Database", "logging"),
    ("General", "app_name"),
    ("Files", "modules_json"),
    ("Files", "labels_tsv"),
]

TOGGLE_FIELDS: list[tuple[str, str]] = [
    ("Features", "enable_document_signer"),
    ("Features", "enable_workflow_manager"),
]

BACKUP_SECTION = "ConfigBackup"
BACKUP_KEY = "ini_text"


# ----------------------------------------------------------- #
#  Hilfsfunktionen                                            #
# ----------------------------------------------------------- #
def _current_username() -> str | None:
    """Helper: liefert den aktuell angemeldeten Username (oder None)."""
    user = getattr(AppContext, "current_user", None)
    return getattr(user, "username", None) if user else None


# ----------------------------------------------------------- #
#  GUI-Klasse                                                 #
# ----------------------------------------------------------- #
class ConfigSettingsTab(ttk.Frame):
    """
    Tab/Dialog zum Bearbeiten der INI-Konfiguration.
    """

    # --------------------------------------------------------------------- #
    #  Konstruktor                                                          #
    # --------------------------------------------------------------------- #
    def __init__(self, parent: tk.Widget | None = None, *, standalone: bool = False):
        self._owned_toplevel: tk.Toplevel | None = None
        if standalone or parent is None:
            self._owned_toplevel = tk.Toplevel()
            self._owned_toplevel.title("QM-Tool • Config")
            self._owned_toplevel.grab_set()
            parent = self._owned_toplevel  # type: ignore[assignment]

        super().__init__(parent)

        self.repo = ConfigRepository.instance()
        self.vars: dict[tuple[str, str], tk.Variable] = {}

        self._build_ui()
        self._populate_from_ini()
        self._update_save_state()

        if self._owned_toplevel:
            self._owned_toplevel.bind("<Escape>", lambda _e: self._owned_toplevel.destroy())

    # ------------------------------------------------------------------ UI --
    def _build_ui(self) -> None:
        """Erzeugt Widgets."""
        self.columnconfigure(1, weight=1)
        row = 0

        # Pflichtpfade -------------------------------------------------------
        for section, key in MANDATORY_FIELDS:
            ttk.Label(self, text=key).grid(row=row, column=0, sticky="w", padx=4, pady=4)

            var = tk.StringVar()
            ttk.Entry(self, textvariable=var, width=46).grid(
                row=row, column=1, sticky="ew", padx=4, pady=4
            )
            ttk.Button(
                self, text="…", width=3, command=lambda v=var: self._choose_file(v)
            ).grid(row=row, column=2, padx=2)

            self.vars[(section, key)] = var
            row += 1

        # Version (read-only) -----------------------------------------------
        ttk.Label(self, text="version").grid(row=row, column=0, sticky="w", padx=4, pady=6)
        ver_var = tk.StringVar(value=config_loader.get_version())
        ttk.Entry(self, textvariable=ver_var, state="readonly").grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=4, pady=6
        )
        row += 1

        ttk.Separator(self).grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        row += 1

        # Toggles ------------------------------------------------------------
        for section, key in TOGGLE_FIELDS:
            var = tk.BooleanVar()
            ttk.Checkbutton(
                self, text=key, variable=var, command=self._on_change
            ).grid(row=row, column=0, columnspan=3, sticky="w", padx=4, pady=2)
            self.vars[(section, key)] = var
            row += 1

        # Buttons ------------------------------------------------------------
        row += 1
        btn_row = ttk.Frame(self)
        btn_row.grid(row=row, column=0, columnspan=3, sticky="e", pady=10)

        ttk.Button(btn_row, text="Save", command=self._save_to_ini).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Save to DB", command=self._backup_to_db).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Restore from DB", command=self._restore_from_db).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Export from DB", command=self._export_from_db).pack(side="left", padx=4)

    # ------------------------------------------------ Populate / Validate ---
    def _populate_from_ini(self) -> None:
        """Füllt Widgets mit Werten aus der INI."""
        for (section, key), var in self.vars.items():
            fallback = _DEFAULT_INI_CONTENT.get(section, {}).get(key, "")
            raw_val = config_loader._config.get(section, key, fallback=fallback)

            if isinstance(var, tk.BooleanVar):
                var.set(str(raw_val).lower() in ("true", "1", "yes"))
            else:
                var.set(raw_val)

    def _validate(self) -> tuple[bool, str]:
        """Validiert Pflichtpfade."""
        for section, key in MANDATORY_FIELDS:
            value = self.vars[(section, key)].get().strip()
            if not value:
                return False, f"{key} may not be empty"

            if any(key.endswith(ext) for ext in (".db", ".json", ".tsv")):
                if not Path(value).expanduser().parent.exists():
                    return False, f"Directory for '{key}' does not exist"
        return True, ""

    # --------------------------------------------------- UI-Events ----------
    def _choose_file(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            initialdir=Path(var.get() or Path.home()), title="Select file"
        )
        if path:
            var.set(Path(path).expanduser().as_posix())
            self._on_change()
            logger.log("Config", "FileChosen", username=_current_username(), message=path)

    def _on_change(self) -> None:
        self._update_save_state()

    def _update_save_state(self) -> None:
        ok, _ = self._validate()
        # Buttons müssten deaktiviert werden, falls ok=False – derzeit nicht nötig

    # ---------------------------------------------------- Save / Backup -----
    def _save_to_ini(self) -> None:
        ok, msg = self._validate()
        if not ok:
            messagebox.showerror(T("Invalid configuration"), msg)
            logger.log("Config", "SaveFailed", username=_current_username(), message=msg)
            return

        # ConfigParser aktualisieren
        for (section, key), var in self.vars.items():
            if not config_loader._config.has_section(section):
                config_loader._config.add_section(section)
            val = str(var.get()).lower() if isinstance(var, tk.BooleanVar) else var.get()
            config_loader._config.set(section, key, val)

        # INI schreiben
        with INI_PATH.open("w", encoding="utf-8") as fh:
            config_loader._config.write(fh)

        self._backup_to_db(silent=True)
        AppContext.update_language()                     # Sprache ggf. neu laden
        messagebox.showinfo(T("Saved"), T("Configuration updated."))
        logger.log("Config", "SaveToINI", username=_current_username())

    # -------- Backup-Helpers ---------- #
    def _backup_to_db(self, *, silent: bool = False) -> None:
        ini_text = INI_PATH.read_text(encoding="utf-8")
        self.repo.set(BACKUP_SECTION, BACKUP_KEY, ini_text)
        if not silent:
            messagebox.showinfo("Backup", "INI saved to DB.")
        logger.log("Config", "BackupToDB", username=_current_username())

    def _restore_from_db(self) -> None:
        ini_text = self.repo.get(BACKUP_SECTION, BACKUP_KEY, None)
        if not ini_text:
            messagebox.showwarning("Restore", "No backup found in DB.")
            logger.log("Config", "RestoreFailed", username=_current_username())
            return

        INI_PATH.write_text(ini_text, encoding="utf-8")
        config_loader._load_config()
        self._populate_from_ini()
        AppContext.update_language()
        messagebox.showinfo("Restore", "INI restored from DB.")
        logger.log("Config", "RestoreFromDB", username=_current_username())

    def _export_from_db(self) -> None:
        ini_text = self.repo.get(BACKUP_SECTION, BACKUP_KEY, None)
        if not ini_text:
            messagebox.showwarning("Export", "No backup found in DB.")
            logger.log("Config", "ExportFailed", username=_current_username())
            return

        dst = filedialog.asksaveasfilename(
            defaultextension=".ini",
            filetypes=[("INI files", "*.ini")],
            title="Save backup as …",
        )
        if dst:
            Path(dst).write_text(ini_text, encoding="utf-8")
            messagebox.showinfo("Export", f"Backup exported to:\n{dst}")
            logger.log("Config", "ExportFromDB", username=_current_username(), message=dst)

    # ------------------------------------------------ Closing helper ---------
    def _close(self) -> None:
        if self._owned_toplevel:
            self._owned_toplevel.destroy()


# Kompatibilitäts-Alias
ConfigSettingsView = ConfigSettingsTab
