"""
GUI‑Haupteinstieg des Moduls.
Pflicht: Klasse erbt von `tk.Frame` oder `ttk.Frame`.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ------------------------------------------------------------------
#  Meta‑Daten (werden vom Module‑Importer geparst)
# ------------------------------------------------------------------
MODULE_META = {
    "id": "<modul_slug>",           # *einmalig*, Kleinbuchstaben/Unterstrich
    "label": "<Modul‑Titel>",      # erscheint in Navigation
    "class": "<ModulClass>",        # Name der GUI‑Klasse weiter unten
    "sort_order": 300,               # Menüposition (klein = links)
    "roles": [                       # optionale Workflow‑Rollen
        "Creator",
        "Editor",
        "Publisher",
    ],
    "visible_for": ["Admin", "QMB", "User"],   # wer sieht den Tab
    "settings_for": ["Admin"],                    # wer sieht Einstellungs‑Tab
}


class <ModulClass>(ttk.Frame):
    """Stub‑GUI (fülle eigene Widgets hier ein)."""

    def __init__(self, parent: tk.Widget, **_kwargs):
        super().__init__(parent)
        ttk.Label(self, text="<Modul‑Titel>").pack(padx=20, pady=20)