"""
main_window.py

Root-Window mit dynamischer Navigation (Module-Registry) und zentralem
AppContext für geteilte Services & Login-Status.
© QMToolPyV4 – 2025
"""

from __future__ import annotations
from tkinter import messagebox
from core.config.config_loader import config_loader
from core.config.gui.config_settings_view import ConfigSettingsTab
import inspect
import tkinter as tk
from tkinter import Frame, Label, Button, X, LEFT, RIGHT, DISABLED, NORMAL
from typing import Optional, Dict

from framework.gui.login_view import LoginView
from core.common.app_context import AppContext
from core.common.module_registry import load_registry, ModuleDescriptor

try:
    _ = config_loader            # Zugriff erzwingt _mandatory_check()
except RuntimeError as exc:
    # Hauptfenster ist noch nicht da? -> Stand‑alone Dialog
    root = tk.Tk()
    root.withdraw()              # kein großes Fenster
    messagebox.showinfo("Erstkonfiguration", str(exc), parent=root)
    ConfigSettingsTab(root, modal=True)   # modal=True imctor -> waits
    root.destroy()

class MainWindow(tk.Tk):
    """Hauptfenster der Anwendung mit dynamischem Button-Aufbau."""

    # ------------------------------------------------------------------ #
    # Konstruktor                                                        #
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        super().__init__()

        # Gemeinsame Services aus dem AppContext
        self.log_controller = AppContext.log_controller
        self.user_manager = AppContext.user_manager        # << NEU >>

        # Fenster-Eigenschaften
        self.title("QMToolPy")
        self.geometry("1100x750")

        # State
        self.logged_in: bool = False
        self.active_view: Optional[tk.Frame] = None

        # Registry
        self.registry: Dict[str, ModuleDescriptor] = load_registry()
        self.nav_buttons: Dict[str, Button] = {}

        # ---------- Navigation -----------------------------------------
        self.nav_frame = Frame(self, height=40, bg="#dddddd")
        self.nav_frame.pack(side="top", fill=X)

        self.nav_buttons_frame = Frame(self.nav_frame, bg="#dddddd")
        self.nav_buttons_frame.pack(side=LEFT)

        self.build_navigation()
        self.build_login_button()

        # ---------- Central Display Area -------------------------------
        self.display_area = Frame(self, bg="white")
        self.display_area.pack(fill="both", expand=True)

        # ---------- Status Bar -----------------------------------------
        self.status_bar = Label(self, text="Welcome", anchor="w", bg="#eeeeee")
        self.status_bar.pack(side="bottom", fill=X)

        # ---------- Start mit Login-Maske ------------------------------
        self.load_login_view()

    # ------------------------------------------------------------------ #
    # Navigation                                                         #
    # ------------------------------------------------------------------ #
    def build_navigation(self) -> None:
        for mod in self.registry.values():
            btn = Button(
                self.nav_buttons_frame,
                text=mod.label,
                command=lambda m=mod: self.load_view(m),
                state=DISABLED if mod.requires_login else NORMAL,
                padx=12,
                pady=2,
            )
            btn.pack(side=LEFT, padx=5, pady=5)
            self.nav_buttons[mod.id] = btn

    def build_login_button(self) -> None:
        self.login_logout_button = Button(
            self.nav_frame,
            text="Login",
            command=self.toggle_login_logout,
            padx=12,
            pady=2,
        )
        self.login_logout_button.pack(side=RIGHT, padx=10, pady=5)

    # ------------------------------------------------------------------ #
    # View-Handling                                                      #
    # ------------------------------------------------------------------ #
    def clear_display_area(self) -> None:
        for widget in self.display_area.winfo_children():
            widget.destroy()

    def load_view(self, mod: ModuleDescriptor) -> None:
        self.clear_display_area()
        view_cls = mod.load_class()

        sig = inspect.signature(view_cls.__init__)
        kwargs: dict[str, object] = {}
        for name, param in list(sig.parameters.items())[2:]:
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            if name in AppContext.services:
                kwargs[name] = AppContext.services[name]
            elif hasattr(self, name) and callable(getattr(self, name)):
                kwargs[name] = getattr(self, name)
            elif param.default is inspect._empty:
                tk.messagebox.showerror(
                    "Module error",
                    f"Cannot instantiate '{mod.label}'.\n"
                    f"Missing dependency: '{name}'",
                    parent=self,
                )
                return

        try:
            self.active_view = view_cls(self.display_area, **kwargs)
        except Exception as exc:
            tk.messagebox.showerror("Module error", str(exc), parent=self)
            return

        self.active_view.pack(fill="both", expand=True)
        self.set_status(f"{mod.label} loaded")

    # ------------------------------------------------------------------ #
    # Login / Logout-Handling                                            #
    # ------------------------------------------------------------------ #
    def toggle_login_logout(self) -> None:
        if self.logged_in:
            # ---------- Logout ----------
            self.user_manager.logout()                 # << Aufruf >>
            self.logged_in = False
            self.login_logout_button.config(text="Login")
            self.set_nav_login_state(False)
            self.load_login_view()
            self.set_status("Logged out")
        else:
            # ---------- Login ----------
            self.load_login_view()

    def load_login_view(self) -> None:
        self.clear_display_area()
        LoginView(
            self.display_area,
            login_callback=self.on_login_result,
        ).pack(fill="both", expand=True)

    def on_login_result(self, success: bool, user) -> None:
        if success:
            self.logged_in = True
            self.login_logout_button.config(text="Logout")
            self.set_nav_login_state(True)
            self.load_welcome_view()
            self.set_status(f"Logged in as {user.username}")
        else:
            self.set_status("Login failed")

    # ------------------------------------------------------------------ #
    # Button-Aktivierung abhängig vom Login                              #
    # ------------------------------------------------------------------ #
    def set_nav_login_state(self, logged_in: bool) -> None:
        for mod in self.registry.values():
            if mod.requires_login:
                state = NORMAL if logged_in else DISABLED
                self.nav_buttons[mod.id].config(state=state)

    # ------------------------------------------------------------------ #
    # Sonstige Helfer                                                    #
    # ------------------------------------------------------------------ #
    def load_welcome_view(self) -> None:
        self.clear_display_area()
        Label(
            self.display_area,
            text="Welcome to QMTool!",
            font=("Arial", 24),
        ).pack(expand=True)

    def set_status(self, message: str) -> None:
        self.status_bar.config(text=message)


# --------------------------------------------------------------------------- #
# Stand-alone-Start                                                           #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    MainWindow().mainloop()
