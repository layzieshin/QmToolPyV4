# create_admin.py
from getpass import getpass

from usermanagement.logic.user_repository import UserRepository
from core.models.user import UserRole

repo = UserRepository()

username = input("Neuer Admin-Benutzername: ").strip().lower()
pw       = getpass("Passwort: ")
email    = input("E-Mail: ").strip()

ok = repo.create_user(
        {"username": username, "password": pw, "email": email},
        role=UserRole.ADMIN,
)

print("✅  Admin angelegt" if ok else "❌  Benutzer existiert schon")
