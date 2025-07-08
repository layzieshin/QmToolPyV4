"""
main_window.py

Hauptfenster des QMToolPy-Projekts.
"""

import tkinter as tk
from tkinter import Frame, Label, Button, X, LEFT, RIGHT

from framework.gui.login_view import LoginView                      #  Login GUI
from core.logging.logic.log_controller import LogController         #  NEW import

# LogView (oder Fallback, falls Modul fehlt)
try:
    from core.logging.gui.log_view import LogView
except ImportError:
    class LogView(tk.Frame):
        def __init__(self, parent, controller=None):
            super().__init__(parent)
            Label(self, text="LogView nicht verfügbar", fg="red").pack(expand=True)


class MainWindow(tk.Tk):
    """Hauptfenster der Anwendung."""

    # -------------------------------------------------------------- #
    # Construction                                                   #
    # -------------------------------------------------------------- #

    def __init__(self):
        super().__init__()

        # Shared controller instance (single responsibility!)
        self.log_controller = LogController()

        self.title("QMToolPy Hauptfenster")
        self.geometry("1100x750")

        self.logged_in = False
        self.active_view = None

        # === Navigation (oben) ===
        self.nav_frame = Frame(self, height=40, bg="#dddddd")
        self.nav_frame.pack(side="top", fill=X)

        self.nav_buttons_frame = Frame(self.nav_frame, bg="#dddddd")
        self.nav_buttons_frame.pack(side=LEFT)

        self.login_logout_button = Button(
            self.nav_frame, text="Login", command=self.toggle_login_logout
        )
        self.login_logout_button.pack(side=RIGHT, padx=10, pady=5)

        # === Anzeige-Bereich (Mitte) ===
        self.display_area = Frame(self, bg="white")
        self.display_area.pack(fill="both", expand=True)

        # === Statusbar (unten) ===
        self.status_bar = Label(self, text="Willkommen", anchor="w", bg="#eeeeee")
        self.status_bar.pack(side="bottom", fill=X)

        # Beim Start zunächst Login-Maske anzeigen
        self.load_login_view()

    # -------------------------------------------------------------- #
    # Navigation helper                                              #
    # -------------------------------------------------------------- #

    def clear_display_area(self):
        for widget in self.display_area.winfo_children():
            widget.destroy()

    def set_status(self, message: str):
        self.status_bar.config(text=message)

    # -------------------------------------------------------------- #
    # Login handling                                                 #
    # -------------------------------------------------------------- #

    def toggle_login_logout(self):
        if self.logged_in:
            # Logout
            self.logged_in = False
            self.login_logout_button.config(text="Login")
            self.load_login_view()
            self.set_status("Abgemeldet")
        else:
            # Login-Maske
            self.load_login_view()

    def load_login_view(self):
        self.clear_display_area()
        LoginView(self.display_area, login_callback=self.on_login_result).pack(
            fill="both", expand=True
        )

    def on_login_result(self, success: bool, username: str):
        if success:
            self.logged_in = True
            self.login_logout_button.config(text="Logout")
            self.load_welcome_view()
            self.set_status(f"Eingeloggt als {username}")
        else:
            self.set_status("Login fehlgeschlagen")

    # -------------------------------------------------------------- #
    # Feature – LOGS                                                 #
    # -------------------------------------------------------------- #

   # def load_logs_view(self):
   #     """Lädt die LogView in den Anzeigebereich."""
   #     self.clear_display_area()
   #     self.active_view = LogView(
   #         self.display_area, controller=self.log_controller      # <-- richtiger Controller
   #     )
   #     self.active_view.pack(fill="both", expand=True)
   #     self.set_status("Logs geladen")

    def load_welcome_view(self):
        self.clear_display_area()
        # Erstellen eines einfachen Fensters mit dem Text „Willkommen“
        Label(self.display_area, text="Willkommen im QMTool!", font=("Arial", 24)).pack(
            expand=True
        )

if __name__ == "__main__":
    MainWindow().mainloop()
