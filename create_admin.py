# create_admin.py
# python
# create_admin.py (angepasst)
import sys
from getpass import getpass

from usermanagement.logic.user_repository import UserRepository
from core.models.user import UserRole

from core.settings.logic.settings_manager import settings_manager
def _seed_documents_admin(user_id: str) -> None:
    """Seed documents RBAC admin membership with the given user_id (ID-only)."""
    raw = str(settings_manager.get("documents", "rbac_admins", "") or "")
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    if user_id not in parts:
        parts.append(user_id)
        settings_manager.set("documents", "rbac_admins", ", ".join(parts))


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

if ok:
    user = repo.get_user_by_username(username)
    if user:
        _seed_documents_admin(str(getattr(user, "id", "")))
print("✅  Admin angelegt" if ok else "❌  Benutzer existiert schon")
