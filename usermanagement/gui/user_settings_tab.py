"""
user_settings_tab.py

User profile, password change, and language settings as a modular settings tab for QMToolPyV2.
Intended to be embedded in the global SettingsView.
All text uses the core locale wrapper for i18n.
"""

import tkinter as tk
from tkinter import Frame, Label, Entry, Button, ttk, messagebox, StringVar
from core.models.user import User
from usermanagement.logic.user_manager import UserManager
from core.i18n.locale import locale

class UserSettingsTab(Frame):
    """
    Tab for user profile, password, and language settings.
    Can be added as a subview to any Settings notebook.
    """

    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.controller = controller
        self.user_manager = self.controller.user_manager if controller and hasattr(controller, "user_manager") else UserManager()
        self._active_user = self.user_manager.get_logged_in_user()

        self.language_var = StringVar(value=locale.get_language())
        self.fullname_var = StringVar(value=getattr(self._active_user, "full_name", "") or "")
        self.email_var = StringVar(value=getattr(self._active_user, "email", "") or "")

        self._build_profile_section()
        self._build_password_section()
        self._build_language_section()

    def _build_profile_section(self):
        Label(self, text=locale.t("profile_title"), font=("Arial", 14, "bold")).pack(anchor="w", pady=(10,2))
        f = Frame(self)
        f.pack(fill="x", padx=5)

        Label(f, text=locale.t("username")).grid(row=0, column=0, sticky="w")
        Label(f, text=self._active_user.username).grid(row=0, column=1, sticky="w")

        Label(f, text=locale.t("fullname")).grid(row=1, column=0, sticky="w")
        fullname_entry = Entry(f, textvariable=self.fullname_var)
        fullname_entry.grid(row=1, column=1, sticky="ew")

        Label(f, text=locale.t("email")).grid(row=2, column=0, sticky="w")
        email_entry = Entry(f, textvariable=self.email_var)
        email_entry.grid(row=2, column=1, sticky="ew")

        Button(f, text=locale.t("save_profile"), command=self._save_profile).grid(row=3, column=1, sticky="e", pady=(8,2))

    def _save_profile(self):
        name = self.fullname_var.get().strip()
        email = self.email_var.get().strip()
        if not name or not email:
            messagebox.showerror(locale.t("error"), locale.t("name_email_required"))
            return
        updated = self.user_manager.update_user(
            username=self._active_user.username,
            email=email,
            role=self._active_user.role.value,
            full_name=name
        )
        if updated:
            messagebox.showinfo(locale.t("profile_updated"), locale.t("profile_saved"))
            self._active_user.full_name = name
            self._active_user.email = email
        else:
            messagebox.showerror(locale.t("update_failed"), locale.t("profile_save_failed"))

    def _build_password_section(self):
        Label(self, text=locale.t("change_password"), font=("Arial", 14, "bold")).pack(anchor="w", pady=(18,2))
        f = Frame(self)
        f.pack(fill="x", padx=5)

        Label(f, text=locale.t("current_password")).grid(row=0, column=0, sticky="w")
        old_pw_entry = Entry(f, show="*")
        old_pw_entry.grid(row=0, column=1, sticky="ew")

        Label(f, text=locale.t("new_password")).grid(row=1, column=0, sticky="w")
        new_pw_entry = Entry(f, show="*")
        new_pw_entry.grid(row=1, column=1, sticky="ew")

        Label(f, text=locale.t("repeat_new_password")).grid(row=2, column=0, sticky="w")
        repeat_pw_entry = Entry(f, show="*")
        repeat_pw_entry.grid(row=2, column=1, sticky="ew")

        def do_change_pw():
            old_pw = old_pw_entry.get()
            new_pw = new_pw_entry.get()
            repeat_pw = repeat_pw_entry.get()
            if not old_pw or not new_pw or not repeat_pw:
                messagebox.showerror(locale.t("error"), locale.t("all_fields_required"))
                return
            if new_pw != repeat_pw:
                messagebox.showerror(locale.t("error"), locale.t("passwords_no_match"))
                return
            if self.user_manager.change_password(self._active_user.username, old_pw, new_pw):
                messagebox.showinfo(locale.t("success"), locale.t("password_changed"))
                old_pw_entry.delete(0, "end")
                new_pw_entry.delete(0, "end")
                repeat_pw_entry.delete(0, "end")
            else:
                messagebox.showerror(locale.t("error"), locale.t("current_password_wrong"))

        Button(f, text=locale.t("change_password_btn"), command=do_change_pw).grid(row=3, column=1, sticky="e", pady=(8,2))

    def _build_language_section(self):
        Label(self, text=locale.t("language_settings"), font=("Arial", 14, "bold")).pack(anchor="w", pady=(18,2))
        f = Frame(self)
        f.pack(fill="x", padx=5)

        Label(f, text=locale.t("language")).grid(row=0, column=0, sticky="w")
        languages = locale.get_available_languages()
        lang_combo = ttk.Combobox(f, textvariable=self.language_var, values=languages, state="readonly")
        lang_combo.grid(row=0, column=1, sticky="ew")

        def do_set_language():
            sel = self.language_var.get()
            locale.set_language(sel)
            messagebox.showinfo(locale.t("language_changed"), locale.t("restart_needed"))

        Button(f, text=locale.t("set_language_btn"), command=do_set_language).grid(row=1, column=1, sticky="e", pady=(8,2))
