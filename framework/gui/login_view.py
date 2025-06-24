"""
login_view.py

Dieses Modul implementiert die LoginView, eine GUI-Komponente für die Benutzeranmeldung
im QMToolPy-Projekt.

Die LoginView stellt Eingabefelder für Benutzername und Passwort bereit und führt
eine einfache Dummy-Authentifizierung durch. Nach erfolgreichem Login informiert
sie das Hauptfenster (MainWindow) über das Ergebnis per Callback.

Diese Komponente ist kein Feature im klassischen Sinne und wird daher nicht über die
Feature-Registry geladen, sondern direkt im MainWindow eingebunden.

---

Speicherort im Projekt:
features/login/gui/login_view.py

---

Integration:
- Import in main_window.py:
    from features.login.gui.login_view import LoginView
- Im MainWindow im Anzeigebereich anzeigen via:
    self.login_view = LoginView(self.display_area, login_callback=self.on_login_result)
    self.login_view.pack(fill="both", expand=True)
- Callback-Methode on_login_result im MainWindow verarbeitet Login-Erfolg
"""

import tkinter as tk
from tkinter import Label, Entry, Button, StringVar, messagebox

class LoginView(tk.Frame):
    """
    GUI-Komponente für den Login.

    Zeigt Eingabefelder für Benutzername und Passwort und einen Login-Button an.
    Validiert die Eingaben mit einer Dummy-Authentifizierung (Benutzername='admin', Passwort='secret').

    Bei Erfolg wird der MainWindow-Callback mit (True, username) aufgerufen,
    bei Fehler mit (False, None).
    """

    def __init__(self, parent, login_callback, *args, **kwargs):
        """
        Konstruktor.

        :param parent: Übergeordnetes Tkinter-Widget, in das diese View eingebettet wird.
        :param login_callback: Funktion, die das Ergebnis des Logins als
                               (bool success, str username) entgegennimmt.
        :param args: optionale Positionsargumente für Frame
        :param kwargs: optionale benannte Argumente für Frame
        """
        super().__init__(parent, *args, **kwargs)
        self.login_callback = login_callback

        # Variablen zur Bindung der Eingabefelder
        self.username_var = StringVar()
        self.password_var = StringVar()

        # Benutzername Label und Eingabefeld
        Label(self, text="Benutzername:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        Entry(self, textvariable=self.username_var).grid(row=0, column=1, padx=5, pady=5)

        # Passwort Label und Eingabefeld (Sternchen maskieren)
        Label(self, text="Passwort:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        Entry(self, show="*", textvariable=self.password_var).grid(row=1, column=1, padx=5, pady=5)

        # Login-Button, der die Prüfung startet
        Button(self, text="Login", command=self.attempt_login).grid(row=2, column=0, columnspan=2, pady=10)

    def attempt_login(self):
        """
        Prüft Benutzername und Passwort mit Dummy-Daten.

        Bei erfolgreichem Login wird self.login_callback(True, username) aufgerufen,
        andernfalls eine Fehlermeldung angezeigt und self.login_callback(False, None).
        """
        username = self.username_var.get()
        password = self.password_var.get()

        # Dummy-Validierung: Benutzername = 'admin', Passwort = 'secret'
        if username == "admin" and password == "secret":
            self.login_callback(True, username)
        else:
            messagebox.showerror("Login fehlgeschlagen", "Benutzername oder Passwort falsch.")
            self.login_callback(False, None)
