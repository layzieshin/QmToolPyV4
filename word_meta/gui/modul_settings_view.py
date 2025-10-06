"""Komplexes Einstellungs‑UI, falls das Standard‑Schema nicht reicht."""
from tkinter import ttk

class <ModulSettingsTab>(ttk.Frame):
    SETTINGS_TAB = True   # Marker für auto‑Erkennung

    def __init__(self, parent):
        super().__init__(parent)
        ttk.Label(self, text="<Modul‑Titel> – Settings").pack(pady=20)