# create_admin.py
# python
# create_admin.py (angepasst)
import sys
from getpass import getpass

from usermanagement.logic.user_repository import UserRepository
from core.models.user import UserRole

repo = UserRepository()

def read_input(prompt: str, hide: bool = False) -> str:
    try:
        if hide and sys.stdin.isatty() and sys.stdout.isatty():
            return getpass(prompt)
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\nAbgebrochen")
        sys.exit(1)

username = read_input("Neuer Admin-Benutzername: ").strip().lower()
while not username:
    print("Benutzername darf nicht leer sein.")
    username = read_input("Neuer Admin-Benutzername: ").strip().lower()

pw = read_input("Passwort: ", hide=True)
email = read_input("E-Mail: ").strip()

ok = repo.create_user(
    {"username": username, "password": pw, "email": email},
    role=UserRole.ADMIN,
)

print("✅  Admin angelegt" if ok else "❌  Benutzer existiert schon")
