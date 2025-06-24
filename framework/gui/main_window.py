import tkinter as tk
from core.utils.auth_service import AuthServiceInterface
from framework.gui.login_view import LoginView

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self.auth_service = AuthServiceInterface

        self.login_view = LoginView(
            self,
            auth_service=self.auth_service,
            on_success=self.login_success,
            on_failure=self.login_failure,
        )
        self.login_view.pack(fill="both", expand=True)

    def login_success(self, user):
        self.login_view.pack_forget()
        print(f"Erfolgreich eingeloggt: {user.username}")
        # Hier Feature-Views anzeigen

    def login_failure(self, message):
        tk.messagebox.showerror("Login Fehler", message)
