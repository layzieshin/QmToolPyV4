
# Developer Guide: QMTool Feature/Module Template

## Core Principles

- Every feature **must** use the project's centralized helpers:
    - Logger (`logger`)
    - Status Helper (`set_status`)
    - Config Loader (`config_loader`)
    - I18n/Locale (`locale`)
    - Date/Time Helper (`date_time_helpers`)
- **All user-related logic, data, and permissions must use the central User model**  
  (`from core.models.user import User, UserRole`).
- No hard-coded paths, strings, settings, or custom user classes! Use helpers/config/core models only.

---

## What is Required in the Core/Project?

### a) Helper/Utility Classes (mandatory for all features)

- **Logger**: `from core.logging.logger import logger`
- **StatusHelper**: `from core.utils.status_helper import set_status`
- **ConfigLoader**: `from core.config_loader import config_loader`
- **Locale/I18n**: `from core.i18n.locale import locale`
- **DateTimeHelper**: `from core.utils.date_time_helpers import utc_now` etc.
- **User Model**: `from core.models.user import User, UserRole`

**Recommended contract (see `core/feature_contracts.py`):**
- Use either an abstract base class (`FeatureBase`), a mixin (`CoreUtilsMixin`), or runtime checks to enforce helper/model usage.

---

## b) Settings Concept (per feature)

- **Each feature must provide its own SettingsView (Tkinter Frame).**
    - Settings are always stored in the central DB or as JSON in the DB.
    - All settings access must go through ConfigLoader or a Settings-Manager using ConfigLoader/DB.
- **SettingsView** must include:
    - All configurable feature values (GUI, file paths, flags, etc.)
    - Standard layout (Label, Entry, Combobox, Button, etc.)
    - A "Save" button which validates and saves via core helpers

---

## c) GUI Concept (per feature)

- **Each feature module must provide a main view (Frame).**
    - Frame with `__init__(parent, controller=None)`
    - Always integrates helpers and its SettingsView
    - Must be strictly separated from logic, model, and settings (single responsibility!)

---

## d) Developer Documentation/Blueprint

- README in core and each feature with:
    - Overview of required imports/utilities/models
    - Quick start for creating a new feature (folder, files, entry-point)
    - SettingsPage and GUI integration examples

---

## Feature Directory Structure (Example)

```

feature\_name/
├─ gui/
│    ├─ feature\_view\.py         # Main view (Frame) for the feature
│    └─ feature\_settings\_view\.py# Settings page for the feature
├─ logic/
│    └─ ... (logic/controllers)
├─ models/
│    └─ ... (data models)
└─ README.md                    # Short description and usage notes

````

---

## Required Helper Imports (In Every View/Settings/Logic)

```python
from core.logging.logger import logger
from core.utils.status_helper import set_status
from core.config_loader import config_loader
from core.i18n.locale import locale
from core.utils.date_time_helpers import utc_now  # or other needed functions
from core.models.user import User, UserRole
````

---

## Template: Main GUI Frame (`feature_view.py`)

```python
import tkinter as tk
from core.logging.logger import logger
from core.utils.status_helper import set_status
from core.config_loader import config_loader
from core.i18n.locale import locale
from core.models.user import User

class FeatureView(tk.Frame):
    """
    Main view for the Feature module.
    All logic/UI for the feature is encapsulated here.
    """

    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        tk.Label(self, text=locale.t("feature_title")).pack()
        # ... build the feature UI ...

    def do_something(self):
        logger.info("User performed feature action.", module="Feature")
        set_status(self.controller.set_status_message, locale.t("success"), duration=3)
```

---

## Template: Settings View (`feature_settings_view.py`)

```python
import tkinter as tk
from core.config_loader import config_loader
from core.i18n.locale import locale
from core.models.user import User

class FeatureSettingsView(tk.Frame):
    """
    Settings page for the Feature.
    Use this to display and save all configurable options.
    """

    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.controller = controller
        self._build_settings_ui()

    def _build_settings_ui(self):
        tk.Label(self, text=locale.t("feature_settings")).pack()
        # ... settings UI (Label, Entry, Combobox, etc.) ...
        tk.Button(self, text=locale.t("save"), command=self.save_settings).pack()

    def save_settings(self):
        # Example: Save a setting to config
        config_loader.set_config_value("Feature", "setting_key", "setting_value")
        config_loader.save_config()
        set_status(self.controller.set_status_message, locale.t("success"), duration=3)
```

---

## Settings Storage Recommendations

* Use `config_loader` for global or per-feature config values.
* For per-user or advanced settings, store as JSON in the database (linked to user or feature).
* **Always use the central User model for user-specific settings and logic!**

---

## Contract: What Every Feature Must Provide

* Main FeatureView (Tkinter Frame)
* FeatureSettingsView (Tkinter Frame)
* Must use all core helpers (logger, status\_helper, config\_loader, locale, datetime, User)
* Must register itself with the main application/navigation

---

## Adding a New Feature: Step-by-Step

1. Create your feature directory (see above).
2. Implement `feature_view.py` and `feature_settings_view.py` using the templates.
3. Import and use core helpers and the User model in all logic.
4. Register your feature in the main navigation (e.g., MainWindow feature dictionary).
5. Write a README with a short usage description for the module.
6. Add new translation keys to `core/i18n/locale.py` if needed.
7. Test with both German and English settings.

---

## Example Feature README

```markdown
# Feature: DocumentSigner

- Provides PDF signing capability for the application.
- Uses logger, config_loader, status_helper, locale, and User model as described in the developer guide.
- All settings (such as signature image path, signing rules) are managed in `feature_settings_view.py`.
```

---

## TL;DR

* Use the provided helpers, structure, and patterns.
* Do NOT roll your own config, logger, i18n, or user model!
* Document your feature and settings.
* Ask the core maintainer for review if unsure.

---

