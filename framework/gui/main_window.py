"""
framework/gui/main_window.py
============================

Root-Window mit dynamischer Navigation auf Basis der Module-Registry.
– Registry wird nach Login/Logout neu geladen, damit nur
  sichtbare Module-Tabs erscheinen.
© QMToolPyV5 – 2025
"""

from __future__ import annotations

import inspect
import tkinter as tk
from tkinter import (
    Frame,
    Label,
    Button,
    X,
    LEFT,
    RIGHT,
    DISABLED,
    NORMAL,
    messagebox,
)
from typing import Optional, Dict

from core.common.app_context import AppContext
from core.config.config_loader import config_loader
from core.config.gui.config_settings_view import ConfigSettingsTab
from core.common.module_registry import (
    load_registry,
    invalidate_registry_cache,
)
from core.common.module_descriptor import ModuleDescriptor
from framework.gui.login_view import LoginView

# --------------------------------------------------------------------------- #
#  Erstkonfiguration (falls INI fehlt)                                        #
# --------------------------------------------------------------------------- #
try:
    _ = config_loader  # erzwingt _mandatory_check()
except RuntimeError as exc:
    tmp = tk.Tk()
    tmp.withdraw()
    messagebox.showinfo("Erstkonfiguration", str(exc), parent=tmp)
    ConfigSettingsTab(tmp, modal=True)
    tmp.destroy()


# --------------------------------------------------------------------------- #
#  MainWindow                                                                 #
# --------------------------------------------------------------------------- #
class MainWindow(tk.Tk):
    """Hauptfenster der Anwendung mit dynamischem Button-Aufbau."""

    # ------------------------------------------------------------------ #
    # Konstruktor                                                        #
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        super().__init__()

        # Services aus AppContext
        self.log_controller = AppContext.log_controller
        self.user_manager = AppContext.user_manager

        # Fenster-Eigenschaften
        self.title("QMToolPy")
        self.geometry("1100x750")

        # State
        self.logged_in: bool = False
        self.active_view: Optional[tk.Frame] = None
        self.registry: Dict[str, ModuleDescriptor] = {}

        # ---------- Frames ---------------------------------------------
        self.nav_frame = Frame(self, height=40, bg="#dddddd")
        self.nav_frame.pack(side="top", fill=X)

        self.nav_buttons_frame = Frame(self.nav_frame, bg="#dddddd")
        self.nav_buttons_frame.pack(side=LEFT)

        self.display_area = Frame(self, bg="white")
        self.display_area.pack(fill="both", expand=True)

        self.status_bar = Label(self, text="Welcome", anchor="w", bg="#eeeeee")
        self.status_bar.pack(side="bottom", fill=X)

        # ---------- Buttons --------------------------------------------
        self.nav_buttons: Dict[str, Button] = {}
        self.login_logout_button: Button = Button(
            self.nav_frame, text="Login", command=self.toggle_login_logout, padx=12, pady=2
        )
        self.login_logout_button.pack(side=RIGHT, padx=10, pady=5)

        # ---------- Initialer Aufbau -----------------------------------
        self._reload_registry(role=None)      # keine Tabs vor Login
        self.load_login_view()

    # ------------------------------------------------------------------ #
    # Registry / Navigation                                              #
    # ------------------------------------------------------------------ #
    def _reload_registry(self, role: str | None) -> None:
        """Registry neu laden und Navigation neu aufbauen."""
        invalidate_registry_cache()
        self.registry = load_registry(role)
        self._rebuild_navigation(role)

    def _rebuild_navigation(self, role: str | None) -> None:
        # Alte Buttons entfernen
        for btn in self.nav_buttons.values():
            btn.destroy()
        self.nav_buttons.clear()

        # Neue Buttons anlegen
        for mod in self.registry.values():
            btn = Button(
                self.nav_buttons_frame,
                text=mod.label,
                command=lambda m=mod: self.load_view(m),
                state=DISABLED if mod.requires_login and not self.logged_in else NORMAL,
                padx=12,
                pady=2,
            )
            btn.pack(side=LEFT, padx=5, pady=5)
            self.nav_buttons[mod.id] = btn

    # ------------------------------------------------------------------ #
    # View-Handling                                                      #
    # ------------------------------------------------------------------ #
    def clear_display_area(self) -> None:
        for widget in self.display_area.winfo_children():
            widget.destroy()

    def load_view(self, mod: ModuleDescriptor) -> None:
        """
        Load a module view into the display area.

        Improvements:
        - Shows the real exception/traceback when import/class loading fails.
        - Shows detailed instantiation errors (constructor, missing deps, etc.).
        """
        import traceback

        self.clear_display_area()

        # ------------------- 1) Load view class -------------------
        try:
            view_cls = mod.safe_load_class()
        except Exception as exc:  # pragma: no cover
            tb = traceback.format_exc()
            messagebox.showerror(
                "Module error",
                f"Failed to load class for module '{mod.label}' ({mod.id}).\n\n{exc}\n\n{tb}",
                parent=self,
            )
            return

        if view_cls is None:
            # Try to show the real import error collected by ModuleDescriptor
            details = getattr(mod, "last_import_error", None)

            if not details:
                details = (
                    "No detailed import error available.\n\n"
                    "Possible causes:\n"
                    "- wrong main_class path in meta.json\n"
                    "- missing __init__.py in package\n"
                    "- missing dependency\n"
                    "- syntax error in imported module\n\n"
                    "Check application logs for ModuleDescriptor/ImportError."
                )

            messagebox.showerror(
                "Module error",
                f"Cannot load module '{mod.label}' ({mod.id}).\n\n"
                f"Import details:\n\n{details}",
                parent=self,
            )
            return

        # ------------------- 2) Resolve dependencies -------------------
        sig = inspect.signature(view_cls.__init__)
        kwargs = {}

        # NOTE: parameters are typically: (self, parent, ...)
        for name, param in list(sig.parameters.items())[2:]:
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            if name in AppContext.services:
                kwargs[name] = AppContext.services[name]
                continue

            # convenience: expose full context itself
            if name in ("ctx", "context", "app_context"):
                kwargs[name] = AppContext
                continue

            if hasattr(self, name) and callable(getattr(self, name)):
                kwargs[name] = getattr(self, name)
                continue

            if param.default is inspect._empty:
                messagebox.showerror(
                    "Module error",
                    f"Missing dependency '{name}' for '{mod.label}' ({mod.id}).\n\n"
                    f"Constructor signature: {view_cls.__init__}",
                    parent=self,
                )
                return

        # ------------------- 3) Instantiate view -------------------
        try:
            self.active_view = view_cls(self.display_area, **kwargs)
        except Exception as exc:  # pragma: no cover
            tb = traceback.format_exc()
            messagebox.showerror(
                "Module error",
                f"Failed to instantiate module '{mod.label}' ({mod.id}).\n\n{exc}\n\n{tb}",
                parent=self,
            )
            return

        self.active_view.pack(fill="both", expand=True)
        self.set_status(f"{mod.label} loaded")

    # ------------------------------------------------------------------ #
    # Login / Logout-Handling                                            #
    # ------------------------------------------------------------------ #
    def toggle_login_logout(self) -> None:
        if self.logged_in:
            # ---------- Logout ----------
            self.user_manager.logout()
            self.logged_in = False
            self.login_logout_button.config(text="Login")
            self._reload_registry(role=None)
            self.load_login_view()
            self.set_status("Logged out")
        else:
            # ---------- Login ----------
            self.load_login_view()

    def load_login_view(self) -> None:
        self.clear_display_area()
        LoginView(self.display_area, login_callback=self.on_login_result).pack(fill="both", expand=True)

    def on_login_result(self, success: bool, user) -> None:
        if success:
            self.logged_in = True
            self.login_logout_button.config(text="Logout")
            self._reload_registry(role=user.role)   # Tabs nach Rolle laden
            self.load_welcome_view()
            self.set_status(f"Logged in as {user.username}")
        else:
            self.set_status("Login failed")

    # ------------------------------------------------------------------ #
    # Sonstige Helfer                                                    #
    # ------------------------------------------------------------------ #
    def load_welcome_view(self) -> None:
        self.clear_display_area()
        Label(self.display_area, text="Welcome to QMTool!", font=("Arial", 24)).pack(expand=True)

    def set_status(self, message: str) -> None:
        self.status_bar.config(text=message)


# --------------------------------------------------------------------------- #
# Stand-alone-Start                                                           #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    MainWindow().mainloop()
