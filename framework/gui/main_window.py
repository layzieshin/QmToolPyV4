"""
main_window.py  – dynamic navigation via module registry
"""

from __future__ import annotations

import tkinter as tk
from tkinter import Frame, Label, Button, X, LEFT, RIGHT, DISABLED, NORMAL
from typing import Optional, Dict

from framework.gui.login_view import LoginView
from core.common.module_registry import load_registry, ModuleDescriptor
from core.logging.logic.log_controller import LogController      # shared business logic


class MainWindow(tk.Tk):
    """Root window with dynamic navigation."""

    def __init__(self) -> None:
        super().__init__()

        # Shared controllers / services
        self.log_controller = LogController()

        # Window
        self.title("QMToolPy")
        self.geometry("1100x750")

        # State
        self.logged_in = False
        self.active_view: Optional[tk.Frame] = None
        self.registry: Dict[str, ModuleDescriptor] = load_registry()
        self.nav_buttons: Dict[str, Button] = {}

        # ---------- Navigation bar ----------
        self.nav_frame = Frame(self, height=40, bg="#dddddd")
        self.nav_frame.pack(side="top", fill=X)

        self.nav_buttons_frame = Frame(self.nav_frame, bg="#dddddd")
        self.nav_buttons_frame.pack(side=LEFT)

        self.build_navigation()           # <— dynamic!
        self.build_login_button()

        # ---------- Central area & status ----------
        self.display_area = Frame(self, bg="white")
        self.display_area.pack(fill="both", expand=True)

        self.status_bar = Label(self, text="Welcome", anchor="w", bg="#eeeeee")
        self.status_bar.pack(side="bottom", fill=X)

        self.load_login_view()

    # ------------------------------------------------------------------ #
    # Navigation                                                         #
    # ------------------------------------------------------------------ #
    def build_navigation(self) -> None:
        """Create one button per registry entry."""
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
    # View loading                                                       #
    # ------------------------------------------------------------------ #
    def clear_display_area(self) -> None:
        for widget in self.display_area.winfo_children():
            widget.destroy()

    def load_view(self, mod: ModuleDescriptor) -> None:
        """Instantiate and display the view of *mod*."""
        self.clear_display_area()

        view_cls = mod.load_class()

        # Provide common controllers only if requested via __init__ signature
        try:
            self.active_view = view_cls(
                self.display_area,
                controller=self.log_controller,   # works for LogView
            )
        except TypeError:
            # View doesn't expect a controller
            self.active_view = view_cls(self.display_area)

        self.active_view.pack(fill="both", expand=True)
        self.set_status(f"{mod.label} loaded")

    # ------------------------------------------------------------------ #
    # Login / logout                                                     #
    # ------------------------------------------------------------------ #
    def toggle_login_logout(self) -> None:
        if self.logged_in:
            self.logged_in = False
            self.login_logout_button.config(text="Login")
            self.set_nav_login_state(False)
            self.load_login_view()
            self.set_status("Logged out")
        else:
            self.load_login_view()

    def load_login_view(self) -> None:
        self.clear_display_area()
        LoginView(self.display_area, login_callback=self.on_login_result).pack(
            fill="both", expand=True
        )

    def on_login_result(self, success: bool, username: str) -> None:
        if success:
            self.logged_in = True
            self.login_logout_button.config(text="Logout")
            self.set_nav_login_state(True)
            self.load_welcome_view()
            self.set_status(f"Logged in as {username}")
        else:
            self.set_status("Login failed")

    def set_nav_login_state(self, logged_in: bool) -> None:
        """Enable/disable buttons that require login."""
        for mod in self.registry.values():
            if mod.requires_login:
                state = NORMAL if logged_in else DISABLED
                self.nav_buttons[mod.id].config(state=state)

    # ------------------------------------------------------------------ #
    # Misc                                                               #
    # ------------------------------------------------------------------ #
    def load_welcome_view(self) -> None:
        self.clear_display_area()
        Label(
            self.display_area,
            text="Welcome to QMTool!",
            font=("Arial", 24)
        ).pack(expand=True)

    def set_status(self, message: str) -> None:
        self.status_bar.config(text=message)


if __name__ == "__main__":
    MainWindow().mainloop()
