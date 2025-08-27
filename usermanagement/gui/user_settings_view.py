# usermanagement/gui/user_settings_view.py

from __future__ import annotations
import tkinter as tk
from tkinter import Frame, Label, Button

try:
    # Optional fallback to global context if controller is not provided
    from core.common.app_context import AppContext
except Exception:  # pragma: no cover
    AppContext = None


class UserSettingsView(Frame):
    """
    Displays the current user's settings.

    Robustness:
    - 'controller' is optional. We try controller.user_manager first,
      then fall back to AppContext.user_manager (if available).
    - If no user_manager is available, we show a friendly message instead of crashing.
    """

    def __init__(self, parent, *, controller=None, settings_manager=None, sm=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.controller = controller
        self._sm = settings_manager or sm

        # ---- obtain a user_manager safely
        self._user_manager = None
        if controller is not None:
            self._user_manager = getattr(controller, "user_manager", None)
        if self._user_manager is None and AppContext is not None:
            self._user_manager = getattr(AppContext, "user_manager", None)

        Label(self, text="Benutzereinstellungen", font=("Arial", 18, "bold")).pack(pady=20)

        user = None
        if self._user_manager and hasattr(self._user_manager, "get_logged_in_user"):
            try:
                user = self._user_manager.get_logged_in_user()
            except Exception:
                user = None

        if user:
            # UI texts can stay German; code/comments are English
            Label(self, text=f"Benutzername: {getattr(user, 'username', '-')}", font=("Arial", 12)).pack(pady=5)
            Label(self, text=f"E-Mail: {getattr(user, 'email', '-')}", font=("Arial", 12)).pack(pady=5)
            try:
                role_value = getattr(getattr(user, "role", None), "value", None) or "-"
            except Exception:
                role_value = "-"
            Label(self, text=f"Rolle: {role_value}", font=("Arial", 12)).pack(pady=5)
        else:
            Label(self, text="Kein Benutzer angemeldet oder kein User-Manager verfügbar.", fg="red").pack(pady=10)

        # Only show Back button if we have a working controller with a navigation method
        if self._can_navigate_back():
            Button(self, text="Zurück", command=self._back).pack(pady=25)

    # ---------------- internal helpers ----------------
    def _can_navigate_back(self) -> bool:
        ctrl = self.controller
        return bool(
            ctrl
            and hasattr(ctrl, "_load_feature_view")
            and hasattr(ctrl, "features")
            and isinstance(ctrl.features, dict)
        )

    def _back(self):
        """
        Navigate back to the User Management view, if available.
        """
        if not self._can_navigate_back():
            return
        # Try common keys; fall back to first feature if key not present
        key_candidates = ["User Management", "UserManagement", "Users"]
        target = None
        for k in key_candidates:
            if k in self.controller.features:
                target = self.controller.features[k]
                break
        if target is None and self.controller.features:
            # pick any view as a safe fallback
            target = next(iter(self.controller.features.values()))
        if target is not None:
            try:
                self.controller._load_feature_view(target)
            except Exception:
                pass
