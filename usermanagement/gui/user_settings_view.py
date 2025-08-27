# usermanagement/gui/user_settings_view.py

import tkinter as tk
from tkinter import Frame, Label, Button

class UserSettingsView(Frame):
    """
    Zeigt die Benutzereinstellungen des aktuellen Users an.
    """
    def __init__(self, parent, controller, *, settings_manager=None, sm=None, **kwargs):
        super().__init__(parent)
        self.controller = controller
        user = controller.user_manager.get_logged_in_user()
        self._sm = settings_manager or sm
        Label(self, text="Benutzereinstellungen", font=("Arial", 18, "bold")).pack(pady=20)

        if user:
            Label(self, text=f"Benutzername: {user.username}", font=("Arial", 12)).pack(pady=5)
            Label(self, text=f"E-Mail: {user.email}", font=("Arial", 12)).pack(pady=5)
            Label(self, text=f"Rolle: {user.role.value}", font=("Arial", 12)).pack(pady=5)
            # Hier könntest du Buttons zum Ändern des Passworts, etc. ergänzen!
        else:
            Label(self, text="Kein Benutzer angemeldet.", fg="red").pack(pady=10)

        Button(self, text="Zurück", command=self._back).pack(pady=25)

    def _back(self):
        """
        Zurück zur User-Übersicht.
        """
        # Wechsel zurück zum UserManagementView
        self.controller._load_feature_view(self.controller.features["User Management"])
