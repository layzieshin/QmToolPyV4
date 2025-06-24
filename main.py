import tkinter as tk
from tkinter import Frame, Label, Button, X, LEFT, RIGHT
from core.logging.gui.log_view import LogView
print("LogView import:", LogView)
# Falls du die Feature-Registry schon hast, importiere sie
try:
    from core.feature_registry import feature_registry
except ImportError:
    feature_registry = {}

# Beispiel-Import von LogView, Pfad ggf. anpassen
try:
    from core.logging.gui.log_view import LogView
except ImportError:
    LogView = None  # Dummy falls LogView nicht vorhanden

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("QMToolPy Hauptfenster")
        self.geometry("1100x750")
        self.logged_in = False
        self.active_view = None

        # Navigationsleiste (oben)
        self.nav_frame = Frame(self, height=40, bg="#dddddd")
        self.nav_frame.pack(side="top", fill=X)

        self.nav_buttons_frame = Frame(self.nav_frame, bg="#dddddd")
        self.nav_buttons_frame.pack(side=LEFT)

        # Login/Logout Button (rechts)
        self.login_button = Button(self.nav_frame, text="Login", command=self.toggle_login)
        self.login_button.pack(side=RIGHT, padx=10, pady=5)

        # Anzeige-Bereich (Mitte)
        self.display_area = Frame(self, bg="white")
        self.display_area.pack(fill="both", expand=True)

        # Statusleiste (unten)
        self.status_bar = Label(self, text="Bitte einloggen", anchor="w", bg="#eeeeee")
        self.status_bar.pack(side="bottom", fill=X)

        self.refresh_navigation()
        self.clear_display_area()

    def toggle_login(self):
        """Schaltet zwischen Login und Logout um."""
        self.logged_in = not self.logged_in
        self.login_button.config(text="Logout" if self.logged_in else "Login")

        self.clear_display_area()
        self.refresh_navigation()

        status = "Eingeloggt" if self.logged_in else "Bitte einloggen"
        self.set_status(status)

    def refresh_navigation(self):
        """Aktualisiert die Navigation abhängig vom Login-Status."""
        # Alle Buttons entfernen
        for widget in self.nav_buttons_frame.winfo_children():
            widget.destroy()

        if self.logged_in:
            # Beispiel: Logs-Button, sofern LogView vorhanden ist
            if LogView:
                btn_logs = Button(self.nav_buttons_frame, text="Logs", command=self.load_logs_view)
                btn_logs.pack(side=LEFT, padx=5, pady=5)
            # Hier kannst du weitere Feature-Buttons ergänzen

    def clear_display_area(self):
        """Entfernt alle Widgets im Anzeigebereich."""
        for widget in self.display_area.winfo_children():
            widget.destroy()
        self.active_view = None

    def load_logs_view(self):
        """Lädt die LogView in den Anzeigebereich."""
        self.clear_display_area()
        if LogView:
            self.active_view = LogView(self.display_area, controller=self)
            self.active_view.pack(fill="both", expand=True)
            self.set_status("Logs geladen")
        else:
            self.set_status("LogView nicht verfügbar")

    def set_status(self, message):
        """Aktualisiert die Statusleiste."""
        self.status_bar.config(text=message)

if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
