"""
Settings tab for Documents feature.

- Repository basics
- Module-local RBAC configuration (lists remain for power users)
- User-friendly dialogs:
  * Manage role membership (admin)
  * Process role requests (admin)
  * Request a role (all users)
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from core.common.app_context import AppContext
except Exception:
    class AppContext:
        app_storage_dir: str | None = None
        current_user: object | None = None

from documents.gui.i18n import tr
from core.settings.logic.settings_manager import SettingsManager
from documents.logic.rbac_service import RBACService


# Dialogs (declared below in same file for single-file shipping)
# - ManageRolesDialog
# - RoleRequestDialog
# - RoleRequestsAdminDialog


class DocumentsSettingsTab(ttk.Frame):
    _FEATURE_ID = "documents"

    def __init__(self, parent: tk.Misc, *, sm: SettingsManager) -> None:
        super().__init__(parent)
        self._sm = sm

        self.columnconfigure(1, weight=1)

        ttk.Label(self, text=tr("documents.settings.title", "Documents – Settings"),
                  font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(12, 8))

        # --- Repository basics -------------------------------------------------
        ttk.Label(self, text=tr("documents.settings.root", "Repository root")).grid(row=1, column=0, sticky="w", padx=10)
        self.e_root = ttk.Entry(self); self.e_root.grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        ttk.Label(self, text=tr("documents.settings.idprefix", "ID prefix")).grid(row=2, column=0, sticky="w", padx=10)
        self.e_prefix = ttk.Entry(self, width=12); self.e_prefix.grid(row=2, column=1, sticky="w", padx=10, pady=4)

        ttk.Label(self, text=tr("documents.settings.idpattern", "ID pattern")).grid(row=3, column=0, sticky="w", padx=10)
        self.e_pattern = ttk.Entry(self); self.e_pattern.grid(row=3, column=1, sticky="ew", padx=10, pady=4)

        ttk.Label(self, text=tr("documents.settings.types", "Allowed types (comma-separated)")).grid(row=4, column=0, sticky="w", padx=10)
        self.e_types = ttk.Entry(self); self.e_types.grid(row=4, column=1, sticky="ew", padx=10, pady=4)

        ttk.Label(self, text=tr("documents.settings.review", "Review cycle (months)")).grid(row=5, column=0, sticky="w", padx=10)
        self.sp_review = ttk.Spinbox(self, from_=1, to=60, width=6); self.sp_review.grid(row=5, column=1, sticky="w", padx=10, pady=4)

        ttk.Label(self, text=tr("documents.settings.watermark", "Watermark text (controlled copy)")).grid(row=6, column=0, sticky="w", padx=10)
        self.e_watermark = ttk.Entry(self); self.e_watermark.grid(row=6, column=1, sticky="ew", padx=10, pady=4)

        # --- RBAC (module-local) ----------------------------------------------
        ttk.Separator(self).grid(row=7, column=0, columnspan=4, sticky="ew", padx=10, pady=10)
        ttk.Label(self, text="Role-Based Access Control (module-local)",
                  font=("Segoe UI", 11, "bold")).grid(row=8, column=0, columnspan=4, sticky="w", padx=10, pady=(0,6))
        ttk.Label(self, text="Admins can manage membership and process requests. All users may request roles.")\
            .grid(row=9, column=0, columnspan=4, sticky="w", padx=10, pady=(0,6))

        # Lists remain editable (power users)
        self._rbac_rows = [
            ("Admins", "rbac_admins"),
            ("QMB", "rbac_qmb"),
            ("Authors", "rbac_authors"),
            ("Reviewers", "rbac_reviewers"),
            ("Approvers", "rbac_approvers"),
            ("Readers", "rbac_readers"),
        ]
        self._rbac_entries: dict[str, ttk.Entry] = {}
        row = 10
        for label, key in self._rbac_rows:
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=2)
            e = ttk.Entry(self); e.grid(row=row, column=1, sticky="ew", padx=10, pady=2)
            self._rbac_entries[key] = e
            row += 1

        # Buttons (Save/Reset)
        ttk.Separator(self).grid(row=row, column=0, columnspan=4, sticky="ew", padx=10, pady=10)
        btns = ttk.Frame(self); btns.grid(row=row+1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 12))
        ttk.Button(btns, text=tr("common.save", "Save"), command=self._on_save).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(btns, text=tr("common.reset", "Reset"), command=self._on_reset).grid(row=0, column=1)

        # Role dialogs (right aligned)
        rbtns = ttk.Frame(self); rbtns.grid(row=row+1, column=2, columnspan=2, sticky="e", padx=10, pady=(0, 12))
        ttk.Button(rbtns, text="Manage role membership…", command=self._open_manage_roles).grid(row=0, column=0, padx=6)
        ttk.Button(rbtns, text="Process role requests…", command=self._open_requests_admin).grid(row=0, column=1, padx=6)
        ttk.Button(rbtns, text="Request a role…", command=self._open_request_role).grid(row=0, column=2, padx=6)

        self._load()

    # ---- Helpers -------------------------------------------------------------
    def _defaults(self) -> dict:
        app_store = getattr(AppContext, "app_storage_dir", None) or os.path.join(os.getcwd(), "data")
        root = os.path.join(app_store, "documents_repo")
        return {
            "root_path": root,
            "id_prefix": "DOC",
            "id_pattern": "{YYYY}-{seq:04d}",
            "allowed_types": "SOP,WI,FB,CL",
            "review_months": 24,
            "watermark_copy": "KONTROLLIERTE KOPIE",
            # RBAC (module-local)
            "rbac_admins": "",
            "rbac_qmb": "",
            "rbac_authors": "",
            "rbac_reviewers": "",
            "rbac_approvers": "",
            "rbac_readers": "",
        }

    def _db_path(self) -> str:
        root = self.e_root.get().strip() or self._defaults()["root_path"]
        return os.path.join(root, "_meta", "documents.sqlite3")

    def _load(self) -> None:
        d = self._defaults()
        get = lambda k: self._sm.get(self._FEATURE_ID, k, d[k])
        self.e_root.delete(0, "end"); self.e_root.insert(0, str(get("root_path")))
        self.e_prefix.delete(0, "end"); self.e_prefix.insert(0, str(get("id_prefix")))
        self.e_pattern.delete(0, "end"); self.e_pattern.insert(0, str(get("id_pattern")))
        self.e_types.delete(0, "end"); self.e_types.insert(0, str(get("allowed_types")))
        self.sp_review.delete(0, "end"); self.sp_review.insert(0, str(int(get("review_months"))))
        self.e_watermark.delete(0, "end"); self.e_watermark.insert(0, str(get("watermark_copy")))

        for _, key in self._rbac_rows:
            val = str(get(key))
            e = self._rbac_entries[key]
            e.delete(0, "end"); e.insert(0, val)

    def _on_save(self) -> None:
        vals = {
            "root_path": self.e_root.get().strip(),
            "id_prefix": self.e_prefix.get().strip() or "DOC",
            "id_pattern": self.e_pattern.get().strip() or "{YYYY}-{seq:04d}",
            "allowed_types": self.e_types.get().strip() or "SOP,WI,FB,CL",
            "review_months": int(self.sp_review.get() or 24),
            "watermark_copy": self.e_watermark.get().strip() or "KONTROLLIERTE KOPIE",
        }
        if not vals["root_path"]:
            messagebox.showerror(title="Validation", message="Root path required.", parent=self); return

        for _, key in self._rbac_rows:
            vals[key] = self._rbac_entries[key].get().strip()

        for k, v in vals.items():
            self._sm.set(self._FEATURE_ID, k, v)

        messagebox.showinfo(title=tr("documents.settings.saved", "Saved"),
                            message=tr("documents.settings.saved_msg", "Settings saved."), parent=self)

    def _on_reset(self) -> None:
        d = self._defaults()
        for k, v in d.items():
            self._sm.set(self._FEATURE_ID, k, v)
        self._load()

    # ---- Role Dialogs --------------------------------------------------------
    def _make_rbac_service(self) -> RBACService:
        return RBACService(self._db_path(), self._sm)

    def _open_manage_roles(self) -> None:
        dlg = ManageRolesDialog(self, service=self._make_rbac_service())
        self.wait_window(dlg)

    def _open_requests_admin(self) -> None:
        dlg = RoleRequestsAdminDialog(self, service=self._make_rbac_service())
        self.wait_window(dlg)

    def _open_request_role(self) -> None:
        dlg = RoleRequestDialog(self, service=self._make_rbac_service())
        self.wait_window(dlg)


# ---------------- Dialogs ----------------------------------------------------

class ManageRolesDialog(tk.Toplevel):
    ROLES = ("ADMIN", "QMB", "AUTHOR", "REVIEWER", "APPROVER")  # READER ist implizit

    def __init__(self, parent: tk.Misc, *, service: RBACService) -> None:
        super().__init__(parent)
        self.title("Manage role membership")
        self.resizable(True, True)
        self._svc = service
        self._members: dict[str, set[str]] = {k: set(self._svc.get_members(_role_to_key(k))) for k in self.ROLES}

        frm = ttk.Frame(self, padding=10); frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1); self.rowconfigure(0, weight=1)

        # Left: users list
        left = ttk.Frame(frm); left.grid(row=0, column=0, sticky="nsw", padx=(0,12))
        ttk.Label(left, text="Users").grid(row=0, column=0, sticky="w")
        self.lb_users = tk.Listbox(left, width=32, height=18, exportselection=False)
        self.lb_users.grid(row=1, column=0, sticky="nsw")
        self.lb_users.bind("<<ListboxSelect>>", self._on_user_select)

        # Right: checkboxes
        right = ttk.Frame(frm); right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="Membership").grid(row=0, column=0, sticky="w")
        self._vars: dict[str, tk.BooleanVar] = {}
        rrow = 1
        for role in self.ROLES:
            var = tk.BooleanVar(value=False)
            self._vars[role] = var
            ttk.Checkbutton(right, text=role, variable=var).grid(row=rrow, column=0, sticky="w", pady=3)
            rrow += 1

        btns = ttk.Frame(frm); btns.grid(row=1, column=0, columnspan=2, sticky="e", pady=(12,0))
        ttk.Button(btns, text="Apply", command=self._apply).grid(row=0, column=0, padx=(0,6))
        ttk.Button(btns, text="Close", command=self.destroy).grid(row=0, column=1)

        # Load users
        self._users = self._svc.list_users()
        for u in self._users:
            label = u.get("username") or u.get("email") or u.get("id")
            self.lb_users.insert("end", label)

    def _current_user_ident(self) -> str | None:
        sel = self.lb_users.curselection()
        if not sel:
            return None
        u = self._users[sel[0]]
        return u.get("username") or u.get("email") or u.get("id")

    def _on_user_select(self, _evt=None) -> None:
        ident = self._current_user_ident()
        if not ident:
            return
        for role in self.ROLES:
            self._vars[role].set(ident in self._members[role])

    def _apply(self) -> None:
        ident = self._current_user_ident()
        if not ident:
            return
        # mutate local sets
        for role in self.ROLES:
            if self._vars[role].get():
                self._members[role].add(ident)
            else:
                self._members[role].discard(ident)
        # write back to settings
        for role in self.ROLES:
            self._svc.set_members(_role_to_key(role), sorted(self._members[role]))
        messagebox.showinfo(title="Saved", message="Membership updated.", parent=self)


class RoleRequestDialog(tk.Toplevel):
    ROLES = ("AUTHOR", "REVIEWER", "APPROVER", "QMB", "ADMIN")  # READER implizit

    def __init__(self, parent: tk.Misc, *, service: RBACService) -> None:
        super().__init__(parent)
        self.title("Request a role")
        self.resizable(False, False)
        self._svc = service

        frm = ttk.Frame(self, padding=10); frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)

        ttk.Label(frm, text="Select roles to request:").grid(row=0, column=0, sticky="w")
        self._vars: dict[str, tk.BooleanVar] = {}
        r = 1
        for role in self.ROLES:
            v = tk.BooleanVar(value=False)
            self._vars[role] = v
            ttk.Checkbutton(frm, text=role, variable=v).grid(row=r, column=0, sticky="w", pady=2)
            r += 1

        ttk.Label(frm, text="Comment (optional):").grid(row=r, column=0, sticky="w", pady=(8,0)); r += 1
        self.txt = tk.Text(frm, width=50, height=5); self.txt.grid(row=r, column=0, sticky="ew"); r += 1

        btns = ttk.Frame(frm); btns.grid(row=r, column=0, sticky="e", pady=(8,0))
        ttk.Button(btns, text="Submit", command=self._submit).grid(row=0, column=0, padx=(0,6))
        ttk.Button(btns, text="Close", command=self.destroy).grid(row=0, column=1)

    def _submit(self) -> None:
        roles = [k for k, v in self._vars.items() if v.get()]
        comment = self.txt.get("1.0", "end").strip() or None
        if not roles:
            messagebox.showwarning(title="Validation", message="Select at least one role.", parent=self); return
        try:
            rid = self._svc.submit_request(roles, comment)
            messagebox.showinfo(title="Sent", message=f"Request submitted (ID {rid}).", parent=self)
            self.destroy()
        except Exception as ex:
            messagebox.showerror(title="Error", message=str(ex), parent=self)


class RoleRequestsAdminDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, *, service: RBACService) -> None:
        super().__init__(parent)
        self.title("Role requests")
        self.resizable(True, True)
        self._svc = service

        frm = ttk.Frame(self, padding=10); frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1); self.rowconfigure(0, weight=1)

        cols = ("id","username","roles","requested_at","status","comment")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse", height=14)
        for c, w in [("id",60),("username",160),("roles",160),("requested_at",140),("status",100),("comment",300)]:
            self.tree.heading(c, text=c.upper()); self.tree.column(c, width=w, anchor="w", stretch=True if c in ("comment","roles") else False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._refresh_btns())

        btns = ttk.Frame(frm); btns.grid(row=1, column=0, sticky="e", pady=(8,0))
        self.btn_refresh = ttk.Button(btns, text="Refresh", command=self._reload)
        self.btn_approve = ttk.Button(btns, text="Approve", command=self._approve)
        self.btn_deny = ttk.Button(btns, text="Deny", command=self._deny)
        for i, b in enumerate([self.btn_refresh, self.btn_approve, self.btn_deny]):
            b.grid(row=0, column=i, padx=6)

        self._reload(); self._refresh_btns()

    def _reload(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for req in self._svc.list_requests():
            self.tree.insert("", "end", iid=str(req.req_id), values=(
                req.req_id, req.username, ",".join(req.roles), req.requested_at.strftime("%Y-%m-%d %H:%M"),
                req.status, req.comment or ""
            ))

    def _sel_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _refresh_btns(self) -> None:
        sel = self._sel_id()
        self.btn_approve.configure(state=("normal" if sel else "disabled"))
        self.btn_deny.configure(state=("normal" if sel else "disabled"))

    def _approve(self) -> None:
        rid = self._sel_id()
        if not rid: return
        self._svc.approve_request(rid)
        self._reload()

    def _deny(self) -> None:
        rid = self._sel_id()
        if not rid: return
        self._svc.deny_request(rid)
        self._reload()


# helper from rbac_service
def _role_to_key(role: str) -> str:
    r = role.upper()
    if r == "ADMIN": return "rbac_admins"
    if r == "QMB": return "rbac_qmb"
    if r == "AUTHOR": return "rbac_authors"
    if r == "REVIEWER": return "rbac_reviewers"
    if r == "APPROVER": return "rbac_approvers"
    if r == "READER": return "rbac_readers"
    raise KeyError(f"Unknown role: {role}")
