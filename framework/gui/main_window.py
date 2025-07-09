"""
main_window.py

Root-Window mit dynamischer Navigation (Module-Registry) und zentralem
AppContext für geteilte Services & Login-Status.

© QMToolPyV4 – 2025
"""

from __future__ import annotations

import tkinter as tk
from tkinter import Frame, Label, Button, X, LEFT, RIGHT, DISABLED, NORMAL
from typing import Optional, Dict

from framework.gui.login_view import LoginView
from core.common.app_context import AppContext
from core.common.module_registry import load_registry, ModuleDescriptor


class MainWindow(tk.Tk):
    """Hauptfenster der Anwendung mit dynamischem Button-Aufbau."""

    # ------------------------------------------------------------------ #
    # Konstruktor                                                        #
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        super().__init__()

        # Gemeinsame Services aus dem AppContext
        self.log_controller = AppContext.log_controller

        # Fenster-Eigenschaften
        self.title("QMToolPy")
        self.geometry("1100x750")

        # State
        self.logged_in: bool = False
        self.active_view: Optional[tk.Frame] = None

        # Registry (wird durch PluginLoader / DB aufgebaut)
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
        """Erzeugt einen Button pro Modul-Eintrag aus der Registry."""
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
        """Entfernt alle Widgets aus dem zentralen Bereich."""
        for widget in self.display_area.winfo_children():
            widget.destroy()

    def load_view(self, mod: ModuleDescriptor) -> None:
        """Instanziiert und zeigt die View des angegebenen Moduls an."""
        self.clear_display_area()

        view_cls = mod.load_class()

        # Einige Views erwarten ggf. zusätzliche Parameter – Beispiel Logs
        try:
            self.active_view = view_cls(
                self.display_area,
                controller=self.log_controller,
            )
        except TypeError:
            # View benötigt keinen Controller
            self.active_view = view_cls(self.display_area)

        self.active_view.pack(fill="both", expand=True)
        self.set_status(f"{mod.label} loaded")

    # ------------------------------------------------------------------ #
    # Login / Logout-Handling                                            #
    # ------------------------------------------------------------------ #
    def toggle_login_logout(self) -> None:
        if self.logged_in:
            # ---------- Logout ----------
            self.logged_in = False
            AppContext.current_user = None
            self.login_logout_button.config(text="Login")
            self.set_nav_login_state(False)
            self.load_login_view()
            self.set_status("Logged out")
        else:
            # ---------- Login ----------
            self.load_login_view()

    def load_login_view(self) -> None:
        """Zeigt die Login-Maske im zentralen Bereich."""
        self.clear_display_area()
        LoginView(self.display_area, login_callback=self.on_login_result).pack(
            fill="both", expand=True
        )

    def on_login_result(self, success: bool, user) -> None:
        """Callback nach Login-Versuch; erhält User-Objekt bei Erfolg."""
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
        """Aktiviert/Deaktiviert Buttons, die Login erfordern."""
        for mod in self.registry.values():
            if mod.requires_login:
                state = NORMAL if logged_in else DISABLED
                self.nav_buttons[mod.id].config(state=state)

    # ------------------------------------------------------------------ #
    # Sonstige Helfer                                                    #
    # ------------------------------------------------------------------ #
    def load_welcome_view(self) -> None:
        """Einfacher Welcome-Screen."""
        self.clear_display_area()
        Label(
            self.display_area,
            text="Welcome to QMTool!",
            font=("Arial", 24),
        ).pack(expand=True)

    def set_status(self, message: str) -> None:
        """Schreibt eine Nachricht in die Status-Leiste."""
        self.status_bar.config(text=message)


# --------------------------------------------------------------------------- #
# Stand-alone-Start                                                           #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    MainWindow().mainloop()
