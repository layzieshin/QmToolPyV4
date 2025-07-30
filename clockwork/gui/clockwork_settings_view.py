"""
Spezielle Settings-GUI für Clockwork (optional),
wird geladen, weil MODULE_META['has_settings_view'] = True.
"""

from tkinter import ttk

TIMEZONE_LABELS = {
    "America/Los_Angeles": "Los Angeles",
    "America/New_York": "New York",
    "Europe/Berlin": "Berlin",
    "Australia/Sydney": "Sydney",
}

class ClockworkSettingsTab(ttk.Frame):
    SETTINGS_TAB = True

    def __init__(self, parent, sm=None):
        super().__init__(parent)
        self.sm = sm
        ttk.Label(self, text="Zeitzone wählen:").grid(row=0, column=0, sticky="w", pady=4, padx=4)
        self.var = ttk.Combobox(
            self,
            state="readonly",
            values=[TIMEZONE_LABELS[z] for z in TIMEZONE_LABELS],
        )
        self.var.grid(row=0, column=1, pady=4, padx=4)
