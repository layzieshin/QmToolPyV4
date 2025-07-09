"""
login_view.py – GUI-Komponente für den Login-Dialog
"""

from __future__ import annotations

import tkinter as tk
from tkinter import Label, Entry, Button, StringVar, messagebox

from core.common.app_context import AppContext
from core.logging.logic.logger import logger


class LoginView(tk.Frame):
    """Login-Maske (Username, Password) mit echtem UserManager-Check."""

    def __init__(self, parent, login_callback, *args, **kwargs):
        """
        :param parent: Tk-Container
        :param login_callback: Funktion (success: bool, user_or_none)
        """
        super().__init__(parent, *args, **kwargs)
        self.login_callback = login_callback

        self.username_var = StringVar()
        self.password_var = StringVar()

        Label(self, text="Benutzername:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        Entry(self, textvariable=self.username_var).grid(row=0, column=1, padx=5, pady=5)

        Label(self, text="Passwort:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        Entry(self, show="*", textvariable=self.password_var).grid(row=1, column=1, padx=5, pady=5)

        Button(self, text="Login", command=self.attempt_login).grid(row=2, column=0, columnspan=2, pady=10)

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #

    def attempt_login(self) -> None:
        """Validiert die Eingaben über UserManager & feuert Callback."""
        username = self.username_var.get().strip()
        password = self.password_var.get()

        user = AppContext.user_manager.try_login(username, password)

        if user:
            # Globale Session setzen
            AppContext.current_user = user
            # ---------- FIX: richtige Parameter ----------
            logger.log(
                feature="User",
                event="Login",
                user_id=user.id,
                username=user.username,
                message="Login successful",
            )
            self.login_callback(True, user)
        else:
            messagebox.showerror("Login fehlgeschlagen", "Benutzername oder Passwort falsch.")
            # ---------- FIX: richtige Parameter ----------
            logger.log(
                feature="User",
                event="LoginFailed",
                username=username,
                message="Login failed",
            )
            self.login_callback(False, None)
