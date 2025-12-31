"""
log_view.py

GUI component for the logging feature.

Provides filter inputs, log display, sorting, and actions such as archive, delete, export, and print.

Relies on a separate controller class that encapsulates all logic.

Can be used standalone for testing or integrated into a larger application.
"""

import tkinter as tk                     # <— NEU: stellt das Kürzel „tk“ bereit
from tkinter import ttk, messagebox, filedialog
from datetime import date
from typing import Optional
from tkcalendar import DateEntry

# ------------------------------------------------------------
# Optional dependency: tkcalendar
# ------------------------------------------------------------
try:
    from tkcalendar import DateEntry
    _TKCALENDAR_AVAILABLE = True
except ImportError:
    DateEntry = None  # type: ignore
    _TKCALENDAR_AVAILABLE = False

class LogView(ttk.Frame):
    """
    LogView widget contains all UI elements for filters, actions, and log display.

    All user interactions are forwarded via callback methods to the controller,
    which handles all logic and data management.
    """

    def __init__(self, parent, controller, *args, **kwargs):
        """
        Initialize UI components and load initial data.

        :param parent: Parent Tkinter widget
        :param controller: Instance of LogController responsible for business logic
        """
        super().__init__(parent, *args, **kwargs)
        self.controller = controller

        if not _TKCALENDAR_AVAILABLE:
            self._show_missing_dependency()
            return

        # Variables to hold filter input values (synchronized with DateEntry widgets)
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.feature_var = tk.StringVar()
        self.event_var = tk.StringVar()
        self.log_level_var = tk.StringVar()
        self.reference_id_var = tk.StringVar()

        # Sorting state
        self._sort_column = "timestamp"
        self._sort_ascending = False

        self._build_ui()
        self._load_filter_options()
        # Initial sorting set for controller
        self.controller.set_sorting(self._sort_column, self._sort_ascending)
        self._populate_logs()

    # ------------------------------------------------------------

    def _show_missing_dependency(self) -> None:
        msg = (
            "Das Logger-Modul benötigt das optionale Paket 'tkcalendar'.\n\n"
            "Bitte installiere es mit:\n\n"
            "    pip install tkcalendar\n\n"
            "Danach kann das Modul verwendet werden."
        )
        label = ttk.Label(self, text=msg, foreground="red", justify=tk.LEFT)
        label.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # ------------------------------------------------------------

    def _build_ui(self):
        """
        Construct and place all UI elements: filter inputs, action buttons, and log table.
        """
        filter_frame = ttk.LabelFrame(self, text="Filters")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text="From:").grid(row=0, column=0, sticky=tk.W, padx=2, pady=2)
        self.start_date_picker = DateEntry(
            filter_frame, date_pattern="dd.MM.yyyy", textvariable=self.start_date_var, width=12
        )
        self.start_date_picker.grid(row=0, column=1, padx=2, pady=2)

        ttk.Label(filter_frame, text="To:").grid(row=0, column=2, sticky=tk.W, padx=2, pady=2)
        self.end_date_picker = DateEntry(
            filter_frame, date_pattern="dd.MM.yyyy", textvariable=self.end_date_var, width=12
        )
        self.end_date_picker.grid(row=0, column=3, padx=2, pady=2)
        self.end_date_picker.set_date(date.today())

        ttk.Label(filter_frame, text="Feature:").grid(row=1, column=0, sticky=tk.W, padx=2, pady=2)
        self.feature_cb = ttk.Combobox(filter_frame, textvariable=self.feature_var, state="readonly")
        self.feature_cb.grid(row=1, column=1, padx=2, pady=2)

        ttk.Label(filter_frame, text="Event:").grid(row=1, column=2, sticky=tk.W, padx=2, pady=2)
        self.event_cb = ttk.Combobox(filter_frame, textvariable=self.event_var, state="readonly")
        self.event_cb.grid(row=1, column=3, padx=2, pady=2)

        ttk.Label(filter_frame, text="Log Level:").grid(row=2, column=0, sticky=tk.W, padx=2, pady=2)
        self.log_level_cb = ttk.Combobox(filter_frame, textvariable=self.log_level_var, state="readonly")
        self.log_level_cb.grid(row=2, column=1, padx=2, pady=2)

        ttk.Label(filter_frame, text="Reference ID:").grid(row=2, column=2, sticky=tk.W, padx=2, pady=2)
        ttk.Entry(filter_frame, textvariable=self.reference_id_var, width=20).grid(row=2, column=3, padx=2, pady=2)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Refresh", command=self._on_refresh).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Archive Older Logs...", command=self._on_archive).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Delete Older Logs", command=self._on_delete).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Export JSON...", command=self._on_export).pack(side=tk.LEFT, padx=2)
        # Print-Button entfernt – wird ggf. in Zukunft vom Print-Modul bereitgestellt
        #ttk.Button(btn_frame, text="Print Logs...", command=self._on_print).pack(side=tk.LEFT, padx=2)

        columns = ("timestamp", "username", "feature", "event", "reference_id", "message", "log_level")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        for col, text in zip(
            columns,
            ["Timestamp", "User", "Feature", "Event", "Reference ID", "Message", "Level"],
        ):
            self.tree.heading(col, text=text, command=lambda _col=col: self._on_sort(_col))
            self.tree.column(col, width=120, anchor=tk.W)

    def _load_filter_options(self):
        """
        Load unique values for Feature, Event, and Log Level dropdown filters from the controller.
        """
        options = self.controller.get_filter_options()
        self.feature_cb["values"] = [""] + options["features"]
        self.event_cb["values"] = [""] + options["events"]
        self.log_level_cb["values"] = [""] + options["levels"]

    def _parse_date(self, date_str: str) -> Optional[date]:
        """
        Parse a date string in 'DD.MM.YYYY' format to a date object.
        Returns None if empty or invalid.
        """
        if not date_str.strip():
            return None
        try:
            from datetime import datetime
            return datetime.strptime(date_str.strip(), "%d.%m.%Y").date()
        except ValueError:
            messagebox.showerror("Invalid Date", f"Invalid date format: {date_str}\nExpected DD.MM.YYYY")
            return None

    def _populate_logs(self):
        """
        Fetch logs from the controller according to current filter values
        and display them in the treeview table.
        """
        logs = self.controller.get_logs(
            start_date=self._parse_date(self.start_date_var.get()),
            end_date=self._parse_date(self.end_date_var.get()),
            feature=self.feature_var.get() or None,
            event=self.event_var.get() or None,
            reference_id=self.reference_id_var.get() or None,
            log_level=self.log_level_var.get() or None,
        )

        # Clear existing rows
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Insert new rows
        for log in logs:
            self.tree.insert(
                "",
                "end",
                values=(
                    log.get("timestamp", ""),
                    log.get("username") or (f"ID:{log.get('user_id')}" if log.get("user_id") else "Unknown"),
                    log.get("feature"),
                    log.get("event"),
                    log.get("reference_id") or "",
                    log.get("message") or "",
                    log.get("log_level"),
                ),
            )

    # ---------------------------------------------------------------------
    # Button- und Tree-Callbacks
    # ---------------------------------------------------------------------

    def _on_refresh(self):
        """Refresh logs display when the Refresh button is clicked."""
        self._populate_logs()

    def _on_sort(self, column):
        """
        Toggle sorting direction when clicking on column headers,
        then refresh the log display.
        The new sorting is passed to the controller.
        """
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True
        self.controller.set_sorting(self._sort_column, self._sort_ascending)
        self._populate_logs()

    def _on_archive(self):
        """
        Archive logs older than the 'From' date filter by exporting to JSON and removing them.
        """
        older_than = self._parse_date(self.start_date_var.get())
        if not older_than:
            messagebox.showerror("Missing Date", "Please select a valid start date for archiving.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Select archive file to save logs",
        )
        if not file_path:
            return
        try:
            count = self.controller.archive_logs(older_than, file_path)
            messagebox.showinfo("Archive Complete", f"{count} logs archived and removed from database.")
            self._populate_logs()
        except Exception as e:
            messagebox.showerror("Archive Error", f"Failed to archive logs:\n{e}")

    def _on_delete(self):
        """
        Delete logs older than the 'From' date filter after confirmation.
        """
        older_than = self._parse_date(self.start_date_var.get())
        if not older_than:
            messagebox.showerror("Missing Date", "Please select a valid start date for deletion.")
            return
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete all logs older than {older_than}?"):
            return
        try:
            count = self.controller.delete_logs(older_than)
            messagebox.showinfo("Delete Complete", f"{count} logs deleted.")
            self._populate_logs()
        except Exception as e:
            messagebox.showerror("Delete Error", f"Failed to delete logs:\n{e}")

    def _on_export(self):
        """
        Export the currently displayed logs to a JSON file.
        """
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Save filtered logs as JSON",
        )
        if not file_path:
            return
        logs = []
        for iid in self.tree.get_children():
            vals = self.tree.item(iid)["values"]
            logs.append(
                {
                    "timestamp": vals[0],
                    "user": vals[1],
                    "feature": vals[2],
                    "event": vals[3],
                    "reference_id": vals[4],
                    "message": vals[5],
                    "log_level": vals[6],
                }
            )
        try:
            self.controller.export_logs_to_json(logs, file_path)
            messagebox.showinfo("Export Successful", f"Logs exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export logs:\n{e}")

    def _on_print(self):
        """
        Print the currently displayed logs in a formatted text view.
        """
        logs = []
        for iid in self.tree.get_children():
            vals = self.tree.item(iid)["values"]
            logs.append(
                {
                    "timestamp": vals[0],
                    "username": vals[1],
                    "feature": vals[2],
                    "event": vals[3],
                    "reference_id": vals[4],
                    "message": vals[5],
                    "log_level": vals[6],
                }
            )
        try:
            self.controller.print_logs(logs)
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to print logs:\n{e}")


if __name__ == "__main__":
    # redundanter Import schadet nicht, kann aber entfallen,
    # da „tk“ bereits am Dateianfang importiert wurde.
    import tkinter as tk

    root = tk.Tk()
    root.title("Log Viewer Standalone Test")
    root.geometry("1000x600")

    # You would normally pass your real controller here.
    # For standalone testing, you can create a mock controller or pass a stub.
    from core.qm_logging.logic.log_controller import LogController

    controller = LogController()
    log_view = LogView(root, controller)
    log_view.pack(fill=tk.BOTH, expand=True)

    root.mainloop()
