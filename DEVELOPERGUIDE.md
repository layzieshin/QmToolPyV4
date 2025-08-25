DEVREADME – Module in QmToolPyV4 entwickeln

Diese Anleitung ist der Single-Source-Leitfaden für neue Module/Features.
Sie beschreibt die Projektkonventionen, die Auto-Discovery per meta.json, Dependency Injection über Parameternamen sowie die Templates für Main-View, Settings-View und die Interfaces für Signatur & Lizenz.
Ziel: Ein neues Modul so bauen, dass es ohne Sonderfälle automatisch geladen wird, sauber testbar ist und eine konsistente UX liefert.

Inhaltsverzeichnis

Grundsätze

Ordnerstruktur je Feature

Auto-Discovery: meta.json

Dependency Injection (DI) per Parameternamen

Settings – richtig lesen/schreiben (inkl. pro User)

UX- und Coding-Konventionen

Internationalisierung (i18n)

Lizenz- und Signatur-Schnittstellen

Templates (ready to copy)

9.1 meta.json Beispiel

9.2 Main-View Template (gui/main_view.py)

9.3 Settings-View Template (gui/settings_view.py)

9.4 Interface: core/contracts/signable.py

9.5 Interface: core/contracts/licensable.py

9.6 Optionaler Typ: core/contracts/licensing_service.py

Checkliste vor dem Commit

Smoke-Test (90 Sekunden)

Grundsätze

Feature-zentriert, SRP: Jedes Modul kapselt UI (gui/), Logik (logic/), Daten/Modelle (models/).

Keine eigenen Globals/Singletons: Services werden injiziert, nicht global importiert.

Stabile Schnittstellen:

Konfiguration/Settings ausschließlich über den SettingsManager.

Benutzer & Rollen über core.models.user.

Übersetzungen über T("key").

Kein Hardcoding: Pfade, Strings, Settings, User-Klassen – bitte über Core nutzen.

Kommerziell nutzbar: Nur Libraries verwenden, die kommerziell unkritisch sind.

Ordnerstruktur je Feature
<feature_id>/
  meta.json
  gui/
    main_view.py         # Hauptansicht (Frame)
    settings_view.py     # Settings-Tab (optional, empfohlen)
  logic/
    __init__.py
    ...                  # Services, Repositories, Formatter (SRP!)
  models/
    __init__.py
    ...                  # Dataclasses, Enums (One class per file)
  README.md              # (optional) Kurzbeschreibung


Tipp: Ordnername == meta.json.id. Pfade in meta.json voll qualifiziert angeben.

Auto-Discovery: meta.json

Die Anwendung scannt Feature-Ordner nach meta.json. Die main_class und optional settings_class werden importiert.
Sichtbarkeit wird per Rollenliste gesteuert; Reihenfolge über sort_order.

Pflichtfelder:

id, label, version

main_class (voll qualifizierter Pfad zur Klasse)

visible_for (Rollen)
Empfohlen:

settings_class (für den zentralen Settings-Notebook)

requires_login (bool)

sort_order (int)

Dependency Injection (DI) per Parameternamen

Der Loader injiziert Services anhand der Parameternamen der __init__-Signatur:

Häufige Services:

settings_manager: SettingsManager (oder sm)

licensing_service: Optional[LicensingService]

ggf. logger, locale_manager, …

Regeln:

Nur Services anfordern, die wirklich benötigt werden.

Immer Fallbacks einbauen (z. B. wenn kein licensing_service vorhanden ist).

Keine langsamen I/O-Operationen im UI-Thread: in logic/ auslagern.

Settings – richtig lesen/schreiben (inkl. pro User)

Ausschließlich über SettingsManager lesen/schreiben.

Bei eingeloggten Nutzern pro Benutzer speichern: user_specific=True und user_id=AppContext.current_user.id.

Werte vor Persistenz validieren (Range, Enum, Format), niemals ungültige Werte speichern.

Beispiel:

from core.common.app_context import AppContext

uid = getattr(AppContext, "current_user", None)
uid = getattr(uid, "id", None)

sm.set("my_feature", "some_key", 123,
       user_specific=bool(uid), user_id=uid)

UX- und Coding-Konventionen

Tkinter ttk verwenden (systemnah).

Layout: klare Überschriften, Inhalte linksbündig, Buttons rechts; Padding 8–12 px.

Live-Feedback im Settings-Tab (Preview).

Docstrings + Typen, eine Klasse pro Datei.

Keine UI-Blocker (Netz/Disk) – in logic/ auslagern.

Internationalisierung (i18n)

Übersetzungen über from core.common.app_context import T

title = T("my_feature.title") or "My Feature"


Keys konsistent prefixen: my_feature.*

Lizenz- und Signatur-Schnittstellen

Lizenzpflichtige Module implementieren Licensable und reagieren auf Lizenzänderungen, z. B. Buttons deaktivieren.

Module mit Signaturfunktion implementieren Signable und kapseln ihren eigenen Signatur-Workflow (SRP).

Die fertigen Interfaces findest du unten in den Templates und d. h. im Code unter core/contracts/….

Templates (ready to copy)

Hinweis: Code ausschließlich in Englisch (Kommentare/Docstrings auch), Dateinamen und Strukturen gemäß Projektkonvention.

9.1 meta.json Beispiel
{
  "id": "feature_skeleton",
  "label": "Feature Skeleton",
  "version": "1.0.0",
  "main_class": "feature_skeleton.gui.main_view.FeatureSkeletonView",
  "settings_class": "feature_skeleton.gui.settings_view.FeatureSkeletonSettingsTab",
  "visible_for": ["Admin", "QMB", "User"],
  "settings_for": ["Admin", "User"],
  "is_core": false,
  "sort_order": 500,
  "requires_login": true
}

9.2 Main-View Template (gui/main_view.py)
"""
FeatureSkeletonView – Main feature view template.

- Requests only required services via DI (by parameter name).
- Reads settings with proper user scoping.
- Reacts to license state if LicensingService is available.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from core.common.app_context import AppContext, T
from core.settings.logic.settings_manager import SettingsManager
from core.contracts.licensable import Licensable, LicenseState
from core.contracts.licensing_service import LicensingService  # structural type


class FeatureSkeletonView(ttk.Frame, Licensable):
    """
    Main feature view template.

    DI parameters (auto-injected by loader):
        settings_manager: SettingsManager
        licensing_service: Optional[LicensingService]  # may be None
    """

    _FEATURE_ID = "feature_skeleton"  # Stable feature ID used for settings & license

    # ---- Licensable --------------------------------------------------------
    def license_feature_id(self) -> str:
        return self._FEATURE_ID

    def apply_license_state(self, state: LicenseState) -> None:
        self._license_state = state
        self._apply_license_to_ui()

    def is_access_allowed(self) -> bool:
        return bool(getattr(self, "_license_state", LicenseState(enabled=True)).enabled)

    # ---- Construction -------------------------------------------------------
    def __init__(
        self,
        parent: tk.Misc,
        *,
        settings_manager: SettingsManager,
        licensing_service: Optional[LicensingService] = None,
    ) -> None:
        super().__init__(parent)
        self._sm = settings_manager
        self._lic = licensing_service
        self._license_state = LicenseState(enabled=True)  # optimistic default

        # Resolve initial license state (if service provided)
        self._hydrate_license_state()

        # Load user-scoped settings
        self._cfg = self._load_cfg()

        # --- UI --------------------------------------------------------------
        self.columnconfigure(0, weight=1)

        title = T("feature_skeleton.title") or "Feature Skeleton"
        self.header = ttk.Label(self, text=title, font=("Segoe UI", 16, "bold"))
        self.header.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        self.info = ttk.Label(self, text=self._make_info_text(), wraplength=680, justify="left")
        self.info.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.action_btn = ttk.Button(self, text=T("common.run") or "Run", command=self._on_run)
        self.action_btn.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 12))

        self._apply_license_to_ui()

    # ---- Helpers ------------------------------------------------------------
    def _hydrate_license_state(self) -> None:
        if self._lic:
            user = getattr(AppContext, "current_user", None)
            uid = getattr(user, "id", None)
            self._license_state = self._lic.get_feature_state(self._FEATURE_ID, uid)

    def _apply_license_to_ui(self) -> None:
        enabled = bool(self._license_state.enabled)
        self.action_btn.configure(state=("normal" if enabled else "disabled"))
        if not enabled:
            self.info.configure(text=T("feature_skeleton.locked") or "This feature is locked by license.")
        else:
            self.info.configure(text=self._make_info_text())

    def _load_cfg(self) -> dict:
        user = getattr(AppContext, "current_user", None)
        uid = getattr(user, "id", None)

        def get(key: str, default):
            if uid:
                return self._sm.get(self._FEATURE_ID, key, default, user_specific=True, user_id=uid)
            return self._sm.get(self._FEATURE_ID, key, default)

        return {
            "example_toggle": bool(get("example_toggle", True)),
            "example_text": str(get("example_text", "Hello from skeleton.")),
        }

    def _make_info_text(self) -> str:
        return f"{self._cfg['example_text']}"

    # ---- Actions ------------------------------------------------------------
    def _on_run(self) -> None:
        # Delegate heavy work to logic/ services; keep UI responsive.
        tk.messagebox.showinfo(
            title=T("feature_skeleton.run.title") or "Run",
            message=T("feature_skeleton.run.ok") or "Action executed successfully.",
            parent=self,
        )

9.3 Settings-View Template (gui/settings_view.py)
"""
FeatureSkeletonSettingsTab – Settings view template.

- Persist via SettingsManager (scoped per user if available).
- Validate before saving.
- Provide immediate visual feedback (preview).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from core.common.app_context import AppContext, T
from core.settings.logic.settings_manager import SettingsManager
from core.contracts.licensing_service import LicensingService


class FeatureSkeletonSettingsTab(ttk.Frame):
    """
    Settings tab for the feature skeleton.

    DI parameters (auto-injected by loader):
        sm: SettingsManager
        licensing_service: Optional[LicensingService]  # may be None
    """

    _FEATURE_ID = "feature_skeleton"

    def __init__(
        self,
        parent: tk.Misc,
        *,
        sm: SettingsManager,
        licensing_service: Optional[LicensingService] = None,
    ) -> None:
        super().__init__(parent)
        self._sm = sm
        self._lic = licensing_service

        self.columnconfigure(1, weight=1)

        # --- UI --------------------------------------------------------------
        ttk.Label(self, text=T("feature_skeleton.settings.title") or "Feature Skeleton Settings",
                  font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(12, 8))

        self.toggle_var = tk.BooleanVar(value=True)
        self.toggle_chk = ttk.Checkbutton(
            self,
            text=T("feature_skeleton.settings.example_toggle") or "Enable example behavior",
            variable=self.toggle_var,
            command=self._refresh_preview
        )
        self.toggle_chk.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        ttk.Label(self, text=T("feature_skeleton.settings.example_text") or "Example text").grid(
            row=2, column=0, sticky="w", padx=10, pady=4
        )
        self.text_ctrl = ttk.Entry(self)
        self.text_ctrl.grid(row=2, column=1, sticky="ew", padx=10, pady=4)

        # Preview
        ttk.Separator(self).grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        ttk.Label(self, text=T("feature_skeleton.settings.preview") or "Preview").grid(
            row=4, column=0, sticky="w", padx=10, pady=(0, 4)
        )
        self.preview_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.preview_var).grid(row=5, column=0, columnspan=2, sticky="w", padx=10)

        # Buttons
        ttk.Separator(self).grid(row=6, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        btns = ttk.Frame(self); btns.grid(row=7, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 12))
        ttk.Button(btns, text=T("common.save") or "Save", command=self._on_save).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(btns, text=T("common.reset") or "Reset", command=self._on_reset).grid(row=0, column=1)

        # Load & Preview
        self._load_from_store()
        self._refresh_preview()

    # ---- Data binding -------------------------------------------------------
    def _load_from_store(self) -> None:
        user = getattr(AppContext, "current_user", None)
        uid = getattr(user, "id", None)

        def get(key: str, default):
            if uid:
                return self._sm.get(self._FEATURE_ID, key, default, user_specific=True, user_id=uid)
            return self._sm.get(self._FEATURE_ID, key, default)

        self.toggle_var.set(bool(get("example_toggle", True)))
        txt = str(get("example_text", "Hello from skeleton."))
        self.text_ctrl.delete(0, "end"); self.text_ctrl.insert(0, txt)

    def _collect(self) -> dict | None:
        txt = self.text_ctrl.get().strip()
        if len(txt) > 200:
            messagebox.showerror(
                title=T("feature_skeleton.settings.error.title") or "Validation error",
                message=T("feature_skeleton.settings.error.textlen") or "Text must be ≤ 200 characters.",
                parent=self,
            )
            return None
        return {"example_toggle": bool(self.toggle_var.get()),
                "example_text": txt or "Hello from skeleton."}

    # ---- Actions ------------------------------------------------------------
    def _on_save(self) -> None:
        data = self._collect()
        if not data:
            return

        user = getattr(AppContext, "current_user", None)
        uid = getattr(user, "id", None)

        for k, v in data.items():
            if uid:
                self._sm.set(self._FEATURE_ID, k, v, user_specific=True, user_id=uid)
            else:
                self._sm.set(self._FEATURE_ID, k, v)

        messagebox.showinfo(
            title=T("feature_skeleton.settings.saved") or "Settings saved",
            message=T("feature_skeleton.settings.saved_msg") or "Your settings have been saved.",
            parent=self,
        )
        self._refresh_preview()

    def _on_reset(self) -> None:
        self.toggle_var.set(True)
        self.text_ctrl.delete(0, "end"); self.text_ctrl.insert(0, "Hello from skeleton.")
        self._refresh_preview()

    # ---- Preview ------------------------------------------------------------
    def _refresh_preview(self) -> None:
        data = self._collect()
        if not data:
            return
        text = data["example_text"]
        if not data["example_toggle"]:
            text = f"[disabled] {text}"
        self.preview_var.set(text)

9.4 Interface: core/contracts/signable.py
"""
Signable interface for modules that offer a signing workflow.

Keep SRP: your feature owns its document(s) and implements how a signature is
applied; the host orchestrates who can sign and when.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class SignState(Enum):
    NOT_SIGNED = "not_signed"
    PENDING = "pending"
    SIGNED = "signed"
    FAILED = "failed"
    REVOKED = "revoked"


@dataclass(frozen=True)
class SignRequest:
    user_id: str
    signature: bytes               # e.g., PNG bytes; modules must accept PNG at minimum
    reason: Optional[str] = None
    requested_at: datetime = datetime.utcnow()


@dataclass(frozen=True)
class SignResult:
    success: bool
    state: SignState
    message: Optional[str] = None
    signed_at: Optional[datetime] = None


class Signable(ABC):
    """Contract for signable modules."""

    @abstractmethod
    def is_signing_enabled(self, user_id: Optional[str]) -> bool:
        """Return True if the current user is allowed to sign now."""

    @abstractmethod
    def get_sign_state(self, user_id: Optional[str]) -> SignState:
        """Return the current sign state for the calling user/context."""

    @abstractmethod
    def request_sign(self, req: SignRequest) -> SignResult:
        """
        Apply a signature. Implementers must perform:
        - validation (user rights, status),
        - safe write (atomic if file-based),
        - state transitions and audit trail (owned by the module).
        """

9.5 Interface: core/contracts/licensable.py
"""
Licensable interface for modules gated by a license.

Modules implement this interface to receive license state changes from the host
and must gracefully react (enable/disable features, update UI).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class LicenseState:
    enabled: bool
    expires_at: Optional[datetime] = None
    payload: dict[str, Any] = field(default_factory=dict)


class Licensable(ABC):
    @abstractmethod
    def license_feature_id(self) -> str:
        """Stable identifier used by the licensing backend (e.g., 'documents')."""

    @abstractmethod
    def apply_license_state(self, state: LicenseState) -> None:
        """React to a new license state (idempotent, quick, no UI blocking)."""

    @abstractmethod
    def is_access_allowed(self) -> bool:
        """Return whether the module currently grants access (cheap getter)."""

9.6 Optional-Typ: core/contracts/licensing_service.py
"""
Structural protocol for a host-provided licensing gateway.
"""

from __future__ import annotations
from typing import Optional, Protocol
from .licensable import LicenseState


class LicensingService(Protocol):
    def is_feature_enabled(self, feature_id: str, user_id: Optional[str] = None) -> bool: ...
    def get_feature_state(self, feature_id: str, user_id: Optional[str] = None) -> LicenseState: ...

Checkliste vor dem Commit

 Ordnername = meta.json.id, Klassenpfade korrekt.

 main_class & settings_class existieren, voll qualifiziert.

 Konstruktor-Signaturen nutzen richtige Parameternamen (z. B. settings_manager, sm, licensing_service).

 Settings ausschließlich via SettingsManager; bei Login user_specific + user_id.

 Validierung vor Persistenz (keine ungültigen Werte speichern).

 Keine I/O-Blocker in UI-Callbacks; Logik in logic/.

 Docstrings/Typen vollständig; eine Klasse pro Datei.

 Rollen/Labels in meta.json stimmen; sort_order gesetzt.

 Lizenzzustände werden korrekt in der UI gespiegelt (Buttons deaktivieren, Hinweistext).

 Übersetzungen über T("..."); sinnvolle Defaults mit or "...".

Smoke-Test (90 Sekunden)

Modulordner unter /features/ ablegen.

meta.json prüfen (ID/Klassenpfade).

App starten → Modul erscheint in Navigation (passend zu Rollen).

Settings öffnen → Wert ändern → Speichern → erneut öffnen → Wert ist persistiert.

(Optional) Lizenz wechseln → Buttons sperren/freigeben → Hinweistext ändert sich.   