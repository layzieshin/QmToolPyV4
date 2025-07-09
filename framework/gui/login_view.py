"""
login_view.py – Tkinter login dialog (GUI layer).

The view no longer writes log entries; all logging is handled by
UserManager, keeping GUI completely decoupled from audit logic.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import Label, Entry, Button, StringVar, messagebox

from core.common.app_context import AppContext


class LoginView(tk.Frame):
    """Username / password dialog that delegates authentication to
    UserManager and reports the result via *login_callback*.
    """

    def __init__(self, parent, login_callback, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._login_callback = login_callback

        # --- form ------------------------------------------------------
        self._username_var = StringVar()
        self._password_var = StringVar()

        Label(self, text="Benutzername:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        Entry(self, textvariable=self._username_var).grid(row=0, column=1, padx=5, pady=5)

        Label(self, text="Passwort:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        Entry(self, show="*", textvariable=self._password_var).grid(row=1, column=1, padx=5, pady=5)

        Button(self, text="Login", command=self._attempt_login).grid(
            row=2, column=0, columnspan=2, pady=10
        )

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #
    def _attempt_login(self) -> None:
        """Validate form input via UserManager and notify caller."""
        username = self._username_var.get().strip()
        password = self._password_var.get()

        user = AppContext.user_manager.try_login(username, password)
        if user:
            # Persist session in AppContext
            AppContext.current_user = user
            self._login_callback(True, user)
        else:
            messagebox.showerror("Login fehlgeschlagen", "Benutzername oder Passwort falsch.")
            self._login_callback(False, None)
