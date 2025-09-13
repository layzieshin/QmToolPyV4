"""
user_view.py

Tk-basierte Ansicht für:
• Login / Logout
• Profil-Bearbeitung
• Passwortänderung
• Admin-Panel (Benutzer-CRUD)

Alle Audit-Logs erfolgen ausschließlich im UserManager.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import Frame, Label, Entry, Button, ttk, messagebox
from typing import Optional, Dict

from core.i18n.translation_manager import T
from usermanagement.logic.user_manager import UserManager
from core.models.user import User, UserRole

ROLE_NAMES = [r.name for r in UserRole]           # ['ADMIN', 'USER', …]

class UserManagementView(Frame):
    # ------------------------------------------------------------------ #
    # Konstruktor                                                        #
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        parent,
        *,
        user_manager: UserManager,
        on_login_success=None,
        on_logout=None,
        set_status_message=None,
        **_,
    ):
        super().__init__(parent)

        # Dependencies
        self.user_manager = user_manager
        self.on_login_success = on_login_success
        self.on_logout = on_logout
        self.set_status = set_status_message if set_status_message else lambda m: None

        # State
        self.active_user: Optional[User] = self.user_manager.get_logged_in_user()
        self.user_profile_fields = [
            f for f in self.user_manager.get_editable_fields() if f not in ("role", "id")
        ]

        # UI-Start
        self._build_main_view() if self.active_user else self._build_login_view()

    # ------------------------------------------------------------------ #
    # Hilfsmethoden                                                     #
    # ------------------------------------------------------------------ #
    def _clear(self) -> None:
        for w in self.winfo_children():
            w.destroy()

    # ------------------------------------------------------------------ #
    # Login / Logout                                                     #
    # ------------------------------------------------------------------ #
    def _build_login_view(self):
        self._clear()
        Label(self, text=T("core.login"), font=("Arial", 16)).pack(pady=10)

        self.username_entry = Entry(self)
        self.username_entry.pack(pady=5)
        self.username_entry.insert(0, T("core.username"))

        self.password_entry = Entry(self, show="*")
        self.password_entry.pack(pady=5)
        self.password_entry.insert(0, T("core.password"))

        Button(self, text=T("core.login"), command=self._handle_login).pack(pady=10)

        # Erst-Admin anlegen, wenn DB leer
        if not self.user_manager.get_all_users():
            Button(self, text="Seed Admin", command=self._seed_admin).pack(pady=5)

    def _handle_login(self):
        user = self.user_manager.try_login(
            self.username_entry.get(),
            self.password_entry.get()
        )

        if user:
            self.active_user = user
            self.set_status(f"{T('core.login')} {T('core.success')}")
            if self.on_login_success:
                self.on_login_success()
            self._build_main_view()
        else:
            self.set_status(T("core.current_password_wrong"))
            messagebox.showerror(T("core.error"), T("core.current_password_wrong"))

    def _handle_logout(self):
        self.user_manager.logout()
        self.set_status(T("core.logout"))
        if self.on_logout:
            self.on_logout()
        self.active_user = None
        self._build_login_view()

    def _seed_admin(self):
        self.user_manager.register_admin_minimal("admin", "admin123", "admin@example.com")
        self.set_status("Admin seeded")

    # ------------------------------------------------------------------ #
    # Haupt-Tabs                                                         #
    # ------------------------------------------------------------------ #
    def _build_main_view(self):
        self._clear()
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Profil
        pf = Frame(nb); self._build_profile_tab(pf)
        nb.add(pf, text=T("core.profile_tab"))

        # Passwort
        pw = Frame(nb); self._build_password_tab(pw)
        nb.add(pw, text=T("core.change_password"))

        # Platzhalter
        sig = Frame(nb); Label(sig, text=T("core.sign_pdf")).pack()
        nb.add(sig, text=T("core.sign_pdf"))

        # Admin
        if self.active_user.role == UserRole.ADMIN:
            adm = Frame(nb); self._build_admin_panel(adm)
            nb.add(adm, text=T("core.user_management"))

    # ------------------------------------------------------------------ #
    # Profil-Tab                                                         #
    # ------------------------------------------------------------------ #
    def _build_profile_tab(self, frame: Frame):
        Label(frame, text=T("core.profile_title"), font=("Arial", 14, "bold")).pack(pady=8)
        tbl = Frame(frame); tbl.pack(padx=10, pady=8)

        self.profile_entries: Dict[str, tk.StringVar] = {}
        for i, fld in enumerate(self.user_profile_fields):
            lbl = T(fld) if T(fld) != fld else fld.replace("_", " ").capitalize()
            Label(tbl, text=lbl, width=18, anchor="w").grid(row=i, column=0, sticky="w", padx=(0, 8), pady=2)
            var = tk.StringVar(value=getattr(self.active_user, fld, "") or "")
            Entry(tbl, textvariable=var).grid(row=i, column=1, sticky="ew", pady=2)
            self.profile_entries[fld] = var
        tbl.grid_columnconfigure(1, weight=1)

        Button(frame, text=T("core.save_profile"), command=self._save_profile).pack(pady=10)

    def _save_profile(self):
        updates = {f: v.get() for f, v in self.profile_entries.items()}
        ok = self.user_manager.update_user_profile(self.active_user.username, updates)
        self.set_status(T("core.profile_saved") if ok else T("core.profile_save_failed"))
        if ok:
            for f, v in updates.items():
                setattr(self.active_user, f, v)

    # ------------------------------------------------------------------ #
    # Passwort-Tab                                                       #
    # ------------------------------------------------------------------ #
    def _build_password_tab(self, frame: Frame):
        Label(frame, text=T("core.change_password"), font=("Arial", 14, "bold")).pack(pady=10)
        form = Frame(frame); form.pack(pady=10)

        Label(form, text=T("core.current_password")).grid(row=0, column=0, sticky="w")
        old_e = Entry(form, show="*"); old_e.grid(row=0, column=1, pady=2)

        Label(form, text=T("core.new_password")).grid(row=1, column=0, sticky="w")
        new_e = Entry(form, show="*"); new_e.grid(row=1, column=1, pady=2)

        Label(form, text=T("core.repeat_new_password")).grid(row=2, column=0, sticky="w")
        rep_e = Entry(form, show="*"); rep_e.grid(row=2, column=1, pady=2)

        def do_change():
            old, new, rep = old_e.get(), new_e.get(), rep_e.get()
            if not all((old, new, rep)):
                self.set_status(T("core.all_fields_required"))
                messagebox.showerror(T("core.error"), T("core.all_fields_required"))
                return
            if new != rep:
                self.set_status(T("core.passwords_no_match"))
                messagebox.showerror(T("core.error"), T("core.passwords_no_match"))
                return
            ok = self.user_manager.change_password(self.active_user.username, old, new)
            if ok:
                self.set_status(T("core.password_changed"))
                messagebox.showinfo(T("core.success"), T("core.password_changed"))
            else:
                self.set_status(T("core.current_password_wrong"))
                messagebox.showerror(T("core.error"), T("core.current_password_wrong"))
            old_e.delete(0, "end"); new_e.delete(0, "end"); rep_e.delete(0, "end")

        Button(frame, text=T("core.change_password_btn"), command=do_change).pack(pady=10)

    # ------------------------------------------------------------------ #
    # Admin-Panel                                                        #
    # ------------------------------------------------------------------ #
    def _build_admin_panel(self, frame: Frame):
        Label(frame, text=T("core.user_management"), font=("Arial", 14, "bold")).pack(pady=(10, 4))

        cols = ["username", "email", "role", "full_name", "phone", "department", "job_title"]
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=T(c) if T(c) != c else c.capitalize())
            tree.column(c, minwidth=100, width=120, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.admin_user_tree = tree

        btn_row = Frame(frame); btn_row.pack(pady=4)
        Button(btn_row, text=T("core.edit"), command=self._popup_edit_user).pack(side="left", padx=5)
        Button(btn_row, text=T("core.delete"), command=self._delete_selected_user).pack(side="left", padx=5)
        Button(btn_row, text=T("core.add"), command=self._popup_create_user).pack(side="left", padx=5)

        self._refresh_user_list()

    def _refresh_user_list(self):
        self.admin_user_tree.delete(*self.admin_user_tree.get_children())
        for u in self.user_manager.get_all_users():
            self.admin_user_tree.insert(
                "", "end",
                values=[
                    u.username, u.email, u.role.name,
                    getattr(u, "full_name", ""), getattr(u, "phone", ""),
                    getattr(u, "department", ""), getattr(u, "job_title", ""),
                ],
            )

    # ---------- CRUD-Pop-ups ----------------------------------------- #
    # ---------- Popup: EDIT USER -------------------------------------- #
    def _popup_edit_user(self):
        sel = self.admin_user_tree.focus()
        if not sel:
            self.set_status(T("core.update_failed"))
            messagebox.showerror(T("core.error"), T("core.update_failed"))
            return

        username = self.admin_user_tree.item(sel)["values"][0]
        user = self.user_manager.get_user(username)

        pop = tk.Toplevel(self); pop.title(f"Edit: {username}")
        pop.grab_set(); pop.resizable(False, False)

        fields = ["email", "role", "full_name", "phone", "department", "job_title"]
        ents: Dict[str, tk.Widget] = {}
        for i, f in enumerate(fields):
            Label(pop, text=T(f) if T(f) != f else f.capitalize()) \
                .grid(row=i, column=0, sticky="w", pady=2, padx=4)

            if f == "role":
                cb = ttk.Combobox(pop, values=ROLE_NAMES, state="readonly", width=17)
                cb.set(user.role.name)
                cb.grid(row=i, column=1, pady=2, padx=4)
                ents[f] = cb
            else:
                e = Entry(pop); e.insert(0, getattr(user, f, "")); e.grid(row=i, column=1, pady=2, padx=4)
                ents[f] = e

        def save():
            upd = {f: ents[f].get() for f in fields}
            ok = self.user_manager.update_user_profile(username, upd)
            self._refresh_user_list(); pop.destroy()
            self.set_status(T("core.profile_saved") if ok else T("core.profile_save_failed"))

        Button(pop, text=T("core.save"), command=save) \
            .grid(row=len(fields), column=0, columnspan=2, pady=10)
    # ---------- Popup: CREATE USER ------------------------------------ #
    def _popup_create_user(self):
        pop = tk.Toplevel(self);
        pop.title(T("core.user_management"))
        pop.grab_set();
        pop.resizable(False, False)

        fields = ["username", "email", "role", "full_name",
                  "phone", "department", "job_title", "password"]
        ents: Dict[str, tk.Widget] = {}

        for i, f in enumerate(fields):
            Label(pop, text=T(f) if T(f) != f else f.capitalize()) \
                .grid(row=i, column=0, sticky="w", pady=2, padx=4)

            if f == "role":
                cb = ttk.Combobox(pop, values=ROLE_NAMES, state="readonly", width=17)
                cb.set("USER")
                cb.grid(row=i, column=1, pady=2, padx=4)
                ents[f] = cb
            else:
                show = "*" if f == "password" else None
                e = Entry(pop, show=show);
                e.grid(row=i, column=1, pady=2, padx=4)
                ents[f] = e

        def save():
            data = {f: (ents[f].get() if f != "password"
                        else ents[f].get())
                    for f in fields}

            if not data["username"] or not data["password"] or not data["email"]:
                self.set_status(T("core.all_fields_required"))
                messagebox.showerror(T("core.error"), T("core.all_fields_required"))
                return

            ok = self.user_manager.register_full(data)
            self._refresh_user_list();
            pop.destroy()
            self.set_status(T("core.profile_saved") if ok else T("core.profile_save_failed"))

        Button(pop, text=T("core.save"), command=save) \
            .grid(row=len(fields), column=0, columnspan=2, pady=10)

    def _delete_selected_user(self):
        sel = self.admin_user_tree.focus()
        if not sel:
            self.set_status(T("core.update_failed"))
            messagebox.showerror(T("core.error"), T("core.update_failed"))
            return

        username = self.admin_user_tree.item(sel)["values"][0]
        if username == self.active_user.username:
            self.set_status("Cannot delete your own account.")
            messagebox.showerror(T("core.error"), "Cannot delete your own account.")
            return

        if messagebox.askyesno(T("core.delete"), f"{T('core.delete')} {username}?"):
            ok = self.user_manager.delete_user(username)
            self._refresh_user_list()
            self.set_status(T("core.profile_saved") if ok else T("core.profile_save_failed"))
