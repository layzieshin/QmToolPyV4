"""
log_view.py

Tkinter-GUI für Anzeige, Filterung und Verwaltung der Logs.
"""

import tkinter as tk
from tkinter import Frame, Label, Button, ttk
from core.logging.logic.log_controller import LogController

class LogView(tk.Frame):
    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.controller = controller or LogController()

        self._build_ui()
        self._load_filter_options()
        self._load_logs()

    def _build_ui(self):
        filter_frame = Frame(self)
        filter_frame.pack(fill="x", padx=5, pady=5)

        self.filter_user_var = tk.StringVar()
        self.filter_feature_var = tk.StringVar()
        self.filter_level_var = tk.StringVar()

        Label(filter_frame, text="Benutzer:").pack(side="left")
        self.filter_user_cb = ttk.Combobox(filter_frame, textvariable=self.filter_user_var)
        self.filter_user_cb.pack(side="left", padx=5)

        Label(filter_frame, text="Feature:").pack(side="left")
        self.filter_feature_cb = ttk.Combobox(filter_frame, textvariable=self.filter_feature_var)
        self.filter_feature_cb.pack(side="left", padx=5)

        Label(filter_frame, text="Level:").pack(side="left")
        self.filter_level_cb = ttk.Combobox(filter_frame, textvariable=self.filter_level_var)
        self.filter_level_cb.pack(side="left", padx=5)

        Button(filter_frame, text="Filter anwenden", command=self._load_logs).pack(side="left", padx=10)

        self.tree = ttk.Treeview(self, columns=("timestamp", "log_level", "username", "feature", "event"), show="headings")
        self.tree.heading("timestamp", text="Zeit")
        self.tree.heading("log_level", text="Level")
        self.tree.heading("username", text="Benutzer")
        self.tree.heading("feature", text="Feature")
        self.tree.heading("event", text="Ereignis")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_filter_options(self):
        opts = self.controller.get_filter_options()
        self.filter_user_cb['values'] = [""] + opts["users"]
        self.filter_feature_cb['values'] = [""] + opts["features"]
        self.filter_level_cb['values'] = [""] + opts["levels"]

    def _load_logs(self):
        self.controller.filter_username = self.filter_user_var.get() or None
        self.controller.filter_feature = self.filter_feature_var.get() or None
        self.controller.filter_level = self.filter_level_var.get() or None

        logs = self.controller.get_logs()

        for i in self.tree.get_children():
            self.tree.delete(i)

        for log in logs:
            self.tree.insert("", "end", values=(log.timestamp, log.log_level, log.username, log.feature, log.event))
