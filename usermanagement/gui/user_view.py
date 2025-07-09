# user_view.py
#
# Main user management view for QMTool.
# - Provides login, profile editing, password change, admin management
# - All UI texts use the locale manager for dynamic language switching
# - Logging and status for every relevant action

# user_view.py
#
# Main user management view for QMTool.
# Logging and status for every relevant action.

import tkinter as tk
from tkinter import Frame, Label, Entry, Button, ttk, messagebox
from core.i18n.locale import locale
from core.logging.logic.logger import logger
from usermanagement.logic.user_manager import UserManager
from core.models.user import UserRole

class UserManagementView(Frame):
    """
    User management interface: login/logout, profile view/edit, admin panel.
    Logging and status for every relevant action.
    """

    def __init__(self, parent, user_manager: UserManager,
                 on_login_success=None, on_logout=None,
                 set_status_message=None, controller=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.active_user = self.user_manager.get_logged_in_user()
        self.on_login_success = on_login_success
        self.on_logout = on_logout
        self.set_status = set_status_message if set_status_message else lambda msg: None
        self.controller = controller
        self.user_profile_fields = [
            f for f in self.user_manager.get_editable_fields()
            if f not in ("role", "id")
        ]
        if self.active_user:
            self.build_main_view()
        else:
            self.build_login_view()

    def clear_view(self):
        """
        Remove all child widgets from this frame.
        """
        # FIX: never destroy self, only children!
        if self.winfo_exists():
            for widget in self.winfo_children():
                widget.destroy()

    def build_login_view(self):
        self.clear_view()
        Label(self, text=locale.t("login"), font=("Arial", 16)).pack(pady=10)
        self.username_entry = Entry(self)
        self.username_entry.pack(pady=5)
        self.username_entry.insert(0, locale.t("username"))
        self.password_entry = Entry(self, show="*")
        self.password_entry.pack(pady=5)
        self.password_entry.insert(0, locale.t("password"))
        Button(self, text=locale.t("login"), command=self.handle_login).pack(pady=10)
        if not self.user_manager.get_all_users():
            Button(self, text="Seed Admin", command=self.seed_admin).pack(pady=5)

    def handle_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        user = self.user_manager.try_login(username, password)
        if user:
            self.active_user = user
            self.set_status(f"{locale.t('login')} {locale.t('success')}")
            logger.log(feature="User", event="Login", user=user, message="Login successful.")
            if self.on_login_success:
                self.on_login_success()
            self.build_main_view()
        else:
            self.set_status(locale.t("current_password_wrong"))
            logger.log(feature="User", event="LoginFailed", user={"username": username}, message="Login failed.")
            messagebox.showerror(locale.t("error"), locale.t("current_password_wrong"))

    def handle_logout(self):
        logger.log(feature="User", event="Logout", user=self.active_user, message="User logged out.")
        self.set_status(locale.t("logout"))
        if self.on_logout:
            self.on_logout()
        self.active_user = None
        self.build_login_view()

    def seed_admin(self):
        self.user_manager.register_admin_minimal("admin", "admin123", "admin@example.com")
        self.set_status("Admin seeded")
        logger.log(feature="User", event="SeedAdmin", user={"username": "admin"}, message="Initial admin seeded.")

    def build_main_view(self):
        # FIX: catch destroyed widget, don't attempt clear on dead self
        if not self.winfo_exists():
            return
        self.clear_view()
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        profile_frame = Frame(notebook)
        self.build_profile_tab(profile_frame)
        notebook.add(profile_frame, text=locale.t("profile_tab"))
        password_frame = Frame(notebook)
        self.build_password_tab(password_frame)
        notebook.add(password_frame, text=locale.t("change_password"))
        signature_frame = Frame(notebook)
        Label(signature_frame, text=locale.t("sign_pdf")).pack()
        notebook.add(signature_frame, text=locale.t("sign_pdf"))
        if self.active_user.role == UserRole.ADMIN:
            admin_frame = Frame(notebook)
            self.build_admin_panel(admin_frame)
            notebook.add(admin_frame, text=locale.t("user_management"))

    def build_profile_tab(self, frame):
        """
        Show editable profile fields (except role, id, password).
        """
        Label(frame, text=locale.t("profile_title"), font=("Arial", 14, "bold")).pack(pady=8)
        table = Frame(frame)
        table.pack(padx=10, pady=8)
        self.profile_entries = {}
        for i, field in enumerate(self.user_profile_fields):
            label = locale.t(field) if locale.t(field) != field else field.replace("_", " ").capitalize()
            Label(table, text=label, width=18, anchor="w").grid(row=i, column=0, sticky="w", pady=2, padx=(0, 8))
            value = getattr(self.active_user, field, "") or ""
            valvar = tk.StringVar(value=value)
            entry = Entry(table, textvariable=valvar)
            entry.grid(row=i, column=1, sticky="ew", pady=2)
            self.profile_entries[field] = valvar
        table.grid_columnconfigure(1, weight=1)
        Button(frame, text=locale.t("save_profile"), command=self.save_profile).pack(pady=10)

    def save_profile(self):
        """
        Save all editable fields in the profile tab.
        """
        updates = {f: v.get() for f, v in self.profile_entries.items()}
        result = self.user_manager.update_user_profile(self.active_user.username, updates)
        if result:
            self.set_status(locale.t("profile_saved"))
            for field, val in updates.items():
                setattr(self.active_user, field, val)
            logger.log(feature="Profile", event="ProfileUpdated", user=self.active_user, message="Profile updated.")
        else:
            self.set_status(locale.t("profile_save_failed"))
            logger.log(feature="Profile", event="ProfileUpdateFailed", user=self.active_user, message="Profile update failed.")

    def build_password_tab(self, frame):
        """
        Password change UI (status and logging on every action).
        """
        Label(frame, text=locale.t("change_password"), font=("Arial", 14, "bold")).pack(pady=10)
        form = Frame(frame)
        form.pack(pady=10)
        Label(form, text=locale.t("current_password")).grid(row=0, column=0, sticky="w")
        old_pw_entry = Entry(form, show="*"); old_pw_entry.grid(row=0, column=1, pady=2)
        Label(form, text=locale.t("new_password")).grid(row=1, column=0, sticky="w")
        new_pw_entry = Entry(form, show="*"); new_pw_entry.grid(row=1, column=1, pady=2)
        Label(form, text=locale.t("repeat_new_password")).grid(row=2, column=0, sticky="w")
        repeat_pw_entry = Entry(form, show="*"); repeat_pw_entry.grid(row=2, column=1, pady=2)

        def do_change_pw():
            old = old_pw_entry.get(); new = new_pw_entry.get(); repeat = repeat_pw_entry.get()
            if not old or not new or not repeat:
                self.set_status(locale.t("all_fields_required"))
                messagebox.showerror(locale.t("error"), locale.t("all_fields_required"))
                logger.log(feature="Password", event="ChangeFailed", user=self.active_user, message="Fields missing")
                return
            if new != repeat:
                self.set_status(locale.t("passwords_no_match"))
                messagebox.showerror(locale.t("error"), locale.t("passwords_no_match"))
                logger.log(feature="Password", event="ChangeFailed", user=self.active_user, message="No match")
                return
            success = self.user_manager.change_password(self.active_user.username, old, new)
            if success:
                self.set_status(locale.t("password_changed"))
                messagebox.showinfo(locale.t("success"), locale.t("password_changed"))
                logger.log(feature="Password", event="Changed", user=self.active_user, message="Password changed")
            else:
                self.set_status(locale.t("current_password_wrong"))
                messagebox.showerror(locale.t("error"), locale.t("current_password_wrong"))
                logger.log(feature="Password", event="ChangeFailed", user=self.active_user, message="Wrong current password")
            old_pw_entry.delete(0, "end"); new_pw_entry.delete(0, "end"); repeat_pw_entry.delete(0, "end")

        Button(frame, text=locale.t("change_password_btn"), command=do_change_pw).pack(pady=10)

    def build_admin_panel(self, frame):
        """
        User management (list, edit, create, delete) for admins.
        All actions logged and reflected in status bar.
        """
        Label(frame, text=locale.t("user_management"), font=("Arial", 14, "bold")).pack(pady=(10, 4))
        columns = ["username", "email", "role", "full_name", "phone", "department", "job_title"]
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=locale.t(col) if locale.t(col) != col else col.capitalize())
            tree.column(col, minwidth=100, width=120, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.admin_user_tree = tree
        self.refresh_user_list()

        # Button row
        btn_frame = Frame(frame)
        btn_frame.pack(pady=4)
        Button(btn_frame, text=locale.t("edit"), command=self.popup_edit_user).pack(side="left", padx=5)
        Button(btn_frame, text=locale.t("delete"), command=self.delete_selected_user).pack(side="left", padx=5)
        Button(btn_frame, text=locale.t("save"), command=self.popup_create_user).pack(side="left", padx=5)

    def refresh_user_list(self):
        """
        Loads all users into the admin user table.
        """
        for row in self.admin_user_tree.get_children():
            self.admin_user_tree.delete(row)
        for user in self.user_manager.get_all_users():
            self.admin_user_tree.insert(
                "", "end",
                values=[
                    user.username, user.email, user.role.name,
                    getattr(user, "full_name", ""), getattr(user, "phone", ""),
                    getattr(user, "department", ""), getattr(user, "job_title", "")
                ]
            )

    def popup_edit_user(self):
        """
        Opens a popup for editing the selected user's data.
        """
        selected = self.admin_user_tree.focus()
        if not selected:
            self.set_status(locale.t("update_failed"))
            messagebox.showerror(locale.t("error"), locale.t("update_failed"))
            return
        username = self.admin_user_tree.item(selected)["values"][0]
        user = self.user_manager.get_user(username)
        popup = tk.Toplevel(self)
        popup.title(f"Edit: {username}")
        fields = ["email", "role", "full_name", "phone", "department", "job_title"]
        entries = {}
        for i, field in enumerate(fields):
            Label(popup, text=locale.t(field) if locale.t(field) != field else field.capitalize()).grid(row=i, column=0, sticky="w")
            entry = Entry(popup)
            entry.insert(0, getattr(user, field, ""))
            entry.grid(row=i, column=1, pady=2, padx=4)
            entries[field] = entry

        def save():
            updates = {f: entries[f].get() for f in fields}
            ok = self.user_manager.update_user_profile(username, updates)
            self.refresh_user_list()
            popup.destroy()
            if ok:
                self.set_status(locale.t("profile_saved"))
                logger.log(feature="UserManagement", event="UserUpdated", user={"username": username}, message="User edited")
            else:
                self.set_status(locale.t("profile_save_failed"))
                logger.log(feature="UserManagement", event="UpdateFailed", user={"username": username}, message="Edit failed")

        Button(popup, text=locale.t("save"), command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def popup_create_user(self):
        """
        Opens a popup for creating a new user.
        """
        popup = tk.Toplevel(self)
        popup.title(locale.t("user_management"))
        fields = ["username", "email", "role", "full_name", "phone", "department", "job_title", "password"]
        entries = {}
        for i, field in enumerate(fields):
            Label(popup, text=locale.t(field) if locale.t(field) != field else field.capitalize()).grid(row=i, column=0, sticky="w")
            entry = Entry(popup, show="*" if field == "password" else None)
            entry.grid(row=i, column=1, pady=2, padx=4)
            entries[field] = entry

        def save():
            user_data = {f: entries[f].get() for f in fields}
            if not user_data["username"] or not user_data["password"] or not user_data["role"]:
                self.set_status(locale.t("all_fields_required"))
                messagebox.showerror(locale.t("error"), locale.t("all_fields_required"))
                return
            ok = self.user_manager.register_full(user_data)
            self.refresh_user_list()
            popup.destroy()
            if ok:
                self.set_status(locale.t("profile_saved"))
                logger.log(feature="UserManagement", event="UserCreated", user={"username": user_data["username"]}, message="User created")
            else:
                self.set_status(locale.t("profile_save_failed"))
                logger.log(feature="UserManagement", event="CreateFailed", user={"username": user_data["username"]}, message="Create failed")

        Button(popup, text=locale.t("save"), command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def delete_selected_user(self):
        """
        Deletes the selected user.
        """
        selected = self.admin_user_tree.focus()
        if not selected:
            self.set_status(locale.t("update_failed"))
            messagebox.showerror(locale.t("error"), locale.t("update_failed"))
            return
        username = self.admin_user_tree.item(selected)["values"][0]
        if username == self.active_user.username:
            self.set_status("Cannot delete your own account.")
            messagebox.showerror(locale.t("error"), "Cannot delete your own account.")
            return
        if messagebox.askyesno(locale.t("delete"), f"{locale.t('delete')} {username}?"):
            ok = self.user_manager.delete_user(username)
            self.refresh_user_list()
            if ok:
                self.set_status(locale.t("profile_saved"))
                logger.log(feature="UserManagement", event="UserDeleted", user={"username": username}, message="User deleted")
            else:
                self.set_status(locale.t("profile_save_failed"))
                logger.log(feature="UserManagement", event="DeleteFailed", user={"username": username}, message="Delete failed")
