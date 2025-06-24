"""
main_window.py

Hauptfenster des QMToolPy-Projekts.

- Enthält Navigation, Anzeige-Bereich und Statusleiste.
- Verwaltet den Login-Status (eingeloggt/ausgeloggt).
- Bindet die LoginView ein und zeigt sie beim Start.
- Nach erfolgreichem Login wird die Navigationsleiste aktualisiert,
  der Logs-Button erscheint und die LogView kann geladen werden.

Speicherort:
QMToolPy/main_window.py

Integration:
- Importiert LoginView aus features/login/gui/login_view.py
- Importiert LogView aus features/logging/gui/log_view.py
"""

import tkinter as tk
from tkinter import Frame, Label, Button, X, LEFT, RIGHT

# Import LoginView - Pfad ggf. anpassen
from framework.gui.login_view import LoginView

# Import LogView - Pfad ggf. anpassen
try:
    from core.logging.gui.log_view import LogView
except ImportError:
    # Fallback Dummy, falls LogView nicht vorhanden ist
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

        # Navigationsleiste (oben)
        self.nav_frame = Frame(self, height=40, bg="#dddddd")
        self.nav_frame.pack(side="top", fill=X)

        # Container für Navigationsbuttons links
        self.nav_buttons_frame = Frame(self.nav_frame, bg="#dddddd")
        self.nav_buttons_frame.pack(side=LEFT)

        # Rechts in der Navigationsleiste evtl. Buttons o.ä. (hier nicht genutzt)

        # Anzeige-Bereich in der Mitte für wechselnde Views
        self.display_area = Frame(self, bg="white")
        self.display_area.pack(fill="both", expand=True)

        # Statusleiste (unten)
        self.status_bar = Label(self, text="Bitte einloggen", anchor="w", bg="#eeeeee")
        self.status_bar.pack(side="bottom", fill=X)

        # LoginView instanziieren mit Callback auf MainWindow Methode
        self.login_view = LoginView(self.display_area, login_callback=self.on_login_result)

        # Direkt beim Start die LoginView anzeigen
        self.load_login_view()

    def load_login_view(self):
        """
        Zeigt die LoginView im Anzeige-Bereich an.
        """
        self.clear_display_area()
        self.login_view.pack(fill="both", expand=True)
        self.set_status("Bitte einloggen")

    def on_login_result(self, success, username):
        """
        Callback, der vom LoginView aufgerufen wird.

        :param success: True, wenn Login erfolgreich, sonst False
        :param username: Name des angemeldeten Benutzers oder None
        """
        if success:
            self.logged_in = True
            self.set_status(f"Eingeloggt als: {username}")
            self.refresh_navigation()
            self.load_logs_view()  # Optional: LogView nach Login automatisch laden
        else:
            self.logged_in = False
            self.set_status("Login fehlgeschlagen")

    def refresh_navigation(self):
        """
        Aktualisiert die Navigationsleiste abhängig vom Login-Status.
        """
        # Bestehende Buttons entfernen
        for widget in self.nav_buttons_frame.winfo_children():
            widget.destroy()

        if self.logged_in:
            # Logs-Button nur anzeigen, wenn eingeloggt
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

    def load_logs_view(self):
        """
        Lädt die LogView in den Anzeige-Bereich.
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
