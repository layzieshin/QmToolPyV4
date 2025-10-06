from __future__ import annotations

"""
Simple Tkinter UI to display Word metadata and review comments.

Left: list of review comments (Author, Date, Preview)
Right: full comment text + small info header
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Dict, Any

# Bootstrapping for direct run: add project root to sys.path if needed
if __package__ in (None, "",):
    import sys
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

from word_meta.logic.metadata_extractor import get_document_metadata

class WordCommentsViewer(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.meta: Dict[str, Any] = {}
        self.comments: List[Dict[str, Any]] = []

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8))
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Word Review Comments", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        self.path_var = tk.StringVar(value="No file selected")
        ttk.Label(header, textvariable=self.path_var).grid(row=0, column=1, sticky="ew", padx=(12, 0))
        ttk.Button(header, text="Open Word…", command=self._on_open).grid(row=0, column=2, padx=(12, 0))

        # Left: Tree of comments
        self.tree = ttk.Treeview(self, columns=("author", "date", "preview"), show="headings", selectmode="browse")
        self.tree.heading("author", text="Author")
        self.tree.heading("date", text="Date")
        self.tree.heading("preview", text="Preview (first 20 chars)")
        self.tree.column("author", width=160, anchor="w")
        self.tree.column("date", width=160, anchor="w")
        self.tree.column("preview", width=320, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))

        yscroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=1, column=0, sticky="nse")

        # Right: Details pane
        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)

        self.info_lbl = ttk.Label(right, text="Select a comment to view details.", font=("Segoe UI", 11, "bold"))
        self.info_lbl.grid(row=0, column=0, sticky="w", pady=(0, 6))

        # Small meta header for author/date
        self.meta_lbl = ttk.Label(right, text="", foreground="#555555")
        self.meta_lbl.grid(row=1, column=0, sticky="w", pady=(0, 6))

        self.detail = tk.Text(right, wrap="word")
        self.detail.grid(row=2, column=0, sticky="nsew")

        dscroll = ttk.Scrollbar(right, orient="vertical", command=self.detail.yview)
        self.detail.configure(yscrollcommand=dscroll.set)
        dscroll.grid(row=2, column=0, sticky="nse")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    # ---------------- Actions ----------------
    def _on_open(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Word document",
            filetypes=[("Word document", "*.docx"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            meta_obj = get_document_metadata(path)
            data = meta_obj.to_dict()
        except Exception as ex:
            messagebox.showerror("Error", f"Failed to read metadata:\n{ex}", parent=self)
            return

        self.path_var.set(path)
        self.meta = data
        core = data.get("core") or {}
        self.comments = (core.get("review_comments") or [])
        self._populate_tree()

    def _populate_tree(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.detail.delete("1.0", "end")
        self.info_lbl.configure(text="Select a comment to view details.")
        self.meta_lbl.configure(text="")

        if not self.comments:
            self.tree.insert("", "end", values=("[none]", "", "No review comments found"))
            return

        for idx, c in enumerate(self.comments, start=1):
            author = c.get("author") or "[unknown]"
            dt = c.get("date")
            date_str = ""
            if isinstance(dt, str):
                date_str = dt[:16].replace("T", " ")
            snippet = (c.get("text") or "").replace("\n", " ").strip()
            preview = (snippet[:20] + "…") if len(snippet) > 20 else snippet
            self.tree.insert("", "end", iid=str(idx), values=(author, date_str, preview))

    def _on_select(self, _evt=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0]) - 1
        except Exception:
            return
        if idx < 0 or idx >= len(self.comments):
            return
        c = self.comments[idx]
        author = c.get("author") or "[unknown]"
        dt = c.get("date") or ""
        if isinstance(dt, str):
            dt = dt.replace("T", " ")
        cid = c.get("id", "")
        self.info_lbl.configure(text=f"Comment #{cid}")
        self.meta_lbl.configure(text=f"Author: {author}   Date: {dt}")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", c.get("text") or "")


def main() -> None:
    root = tk.Tk()
    root.title("Word Review Comments Viewer")

    try:
        root.tk.call("tk", "scaling", 1.25)
    except Exception:
        pass

    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "clam" in style.theme_names():
        style.theme_use("clam")

    app = WordCommentsViewer(root)
    app.pack(fill="both", expand=True)

    root.minsize(900, 560)
    root.mainloop()


if __name__ == "__main__":
    main()
