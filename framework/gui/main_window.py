"""
main_window.py

Hauptfenster des QMToolPy-Projekts.

- Enthält Navigation, Anzeige-Bereich und Statusleiste.
- Verwaltet den Login-Status (eingeloggt/ausgeloggt).
- Bindet die LoginView ein und zeigt sie beim Start.
- Nach erfolgreichem Login wird die Navigationsleiste aktualisiert,
  der Logs-Button erscheint und die LogView kann geladen werden.

Speicherort:
QMToolPy/framework/gui/main_window.py

Integration:
- Importiert LoginView aus features/login/gui/login_view.py
- Importiert LogView aus features/logging/gui/log_view.py
"""

import tkinter as tk
from tkinter import Frame, Label, Button, X, LEFT, RIGHT

from framework.gui.login_view import LoginView  # Pfad ggf. anpassen

try:
    from features.logging.gui.log_view import LogView
except ImportError:
    # Dummy-Fallback, falls LogView fehlt
    class LogView(tk.Frame):
        def __init__(self, parent, controller=None):
            super().__init__(parent)
            label = Label(self, text="LogView nicht verfügbar", fg="red")
            label.pack(expand=True)

class MainWindow(tk.Tk):
    """
    Hauptfenster der Anwendung.

    - Navigation mit dynamisch aktualisierbaren Buttons.
    - Anzeige-Bereich zum Laden verschiedener Views.
    - Statusleiste zur Anzeige von Meldungen.
    - Login-Status und LoginView-Integration.
    """

    def __init__(self):
        super().__init__()

        self.title("QMToolPy Hauptfenster")
        self.geometry("1100x750")

        self.logged_in = False
        self.active_view = None

        # === Navigation (oben) ===
        self.nav_frame = Frame(self, height=40, bg="#dddddd")
        self.nav_frame.pack(side="top", fill=X)

        # Container für Navigations-Buttons links
        self.nav_buttons_frame = Frame(self.nav_frame, bg="#dddddd")
        self.nav_buttons_frame.pack(side=LEFT)

        # Login/Logout-Button rechts fest im Nav-Bereich
        self.login_logout_button = Button(self.nav_frame, text="Login", command=self.toggle_login_logout)
        self.login_logout_button.pack(side=RIGHT, padx=10, pady=5)

        # === Anzeigebereich (Mitte) ===
        self.display_area = Frame(self, bg="white")
        self.display_area.pack(fill="both", expand=True)

        # === Statusleiste (unten) ===
        self.status_bar = Label(self, text="Bitte einloggen", anchor="w", bg="#eeeeee")
        self.status_bar.pack(side="bottom", fill=X)

        # Beim Start die LoginView laden
        self.load_login_view()

    def toggle_login_logout(self):
        """
        Reagiert auf Klick auf Login/Logout-Button.
        Wechselt den Login-Status und aktualisiert UI entsprechend.
        """
        if self.logged_in:
            # Logout
            self.logged_in = False
            self.login_logout_button.config(text="Login")
            self.load_login_view()
            self.refresh_navigation()
            self.set_status("Abgemeldet")
        else:
            # Login (LoginView anzeigen, tatsächliche Auth im LoginView)
            self.load_login_view()

    def on_login_result(self, success, username):
        """
        Callback vom LoginView bei Loginversuch.

        :param success: True bei erfolgreichem Login
        :param username: Eingeloggter Benutzername
        """
        if success:
            self.logged_in = True
            self.login_logout_button.config(text="Logout")
            self.set_status(f"Eingeloggt als: {username}")
            self.refresh_navigation()
            self.load_logs_view()  # Optional: Logs direkt nach Login anzeigen
        else:
            self.set_status("Login fehlgeschlagen")

    def refresh_navigation(self):
        """
        Baut die Navigationsbuttons links neu auf, abhängig vom Login-Status.
        """
        # Vorherige Buttons entfernen
        for widget in self.nav_buttons_frame.winfo_children():
            widget.destroy()

        if self.logged_in:
            # Logs-Button anzeigen, wenn eingeloggt
            btn_logs = Button(self.nav_buttons_frame, text="Logs", command=self.load_logs_view)
            btn_logs.pack(side=LEFT, padx=5, pady=5)
            # Hier können weitere Feature-Buttons ergänzt werden

    def clear_display_area(self):
        """
        Entfernt alle Widgets aus dem Anzeige-Bereich.
        """
        for widget in self.display_area.winfo_children():
            widget.destroy()
        self.active_view = None

    def load_login_view(self):
        """
        Lädt die LoginView im Anzeigebereich.

        Erstellt eine neue LoginView-Instanz, um Fehler mit zerstörten Widgets zu vermeiden.
        """
        self.clear_display_area()

        if hasattr(self, 'login_view') and self.login_view.winfo_exists():
            self.login_view.destroy()

        self.login_view = LoginView(self.display_area, login_callback=self.on_login_result)
        self.login_view.pack(fill="both", expand=True)
        self.set_status("Bitte einloggen")

    def load_logs_view(self):
        """
        Lädt die LogView im Anzeigebereich.
        """
        self.clear_display_area()
        self.active_view = LogView(self.display_area, controller=self)
        self.active_view.pack(fill="both", expand=True)
        self.set_status("Logs geladen")

    def set_status(self, message):
        """
        Setzt den Text in der Statusleiste.
        """
        self.status_bar.config(text=message)


if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
