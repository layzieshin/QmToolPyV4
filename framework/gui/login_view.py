import tkinter as tk
from tkinter import messagebox
from core.utils.auth_service import AuthServiceInterface
class LoginView(tk.Frame):
    """
    Ein einfacher Login-Screen mit zwei Buttons zum direkten Login als Nutzer 1 oder Nutzer 2.
    Authentifizierung via Callback on_success(user).
    """

    def __init__(self, parent, auth_service, on_success, on_failure):
        super().__init__(parent)
        self.auth_service = auth_service
        self.on_success = on_success
        self.on_failure = on_failure

        tk.Label(self, text="Wähle Benutzer zum Login", font=("Arial", 14)).pack(pady=10)

        btn_user1 = tk.Button(self, text="Login als Benutzer 1", command=lambda: self.login_user(1))
        btn_user1.pack(pady=5, ipadx=20, ipady=10)

        btn_user2 = tk.Button(self, text="Login als Benutzer 2", command=lambda: self.login_user(2))
        btn_user2.pack(pady=5, ipadx=20, ipady=10)

    def login_user(self, user_id):
        """
        Versucht den User mit der angegebenen ID zu laden und login_success/failure aufzurufen.
        """
        user = None
        try:
            # auth_service sollte eine Methode haben, um User anhand der ID zu laden
            AuthServiceInterface.authenticate(user_id)
        except Exception as e:
            self.on_failure(f"Fehler beim Laden des Benutzers: {e}")
            return

        if user:
            self.on_success(user)
        else:
            self.on_failure(f"Benutzer mit ID {user_id} nicht gefunden.")
