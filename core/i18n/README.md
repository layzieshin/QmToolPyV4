
# Internationalization (i18n) – Language Support for QMToolPyV3

This folder provides the central helper for multi-language (i18n) support across the entire project.

---

## Purpose

- All UI texts in the project are managed using unique translation keys.
- Supported languages (currently): **English** (`en`) and **German** (`de`).
- Language can be changed at runtime (e.g. via settings page or config).
- New languages or texts can easily be added in one place.
- All feature modules and GUIs must use the i18n helper—**no hard-coded texts!**

---

## How it Works

- The `locale.py` module contains a `LocaleManager` class, which manages all translations.
- You get the translated version of a UI text using `locale.t("key")`.
- The language is switched with `locale.set_language("de")` or `locale.set_language("en")`.
- The default language can be set via config or at application startup.

---

## Example Usage

```python
from core.i18n.locale import locale

# Get translated text for current language
print(locale.t("login"))      # "Login" or "Anmelden"
print(locale.t("logout"))     # "Logout" or "Abmelden"

# Change language at runtime (e.g. after user changes setting)
locale.set_language("de")
label.config(text=locale.t("settings"))  # "Einstellungen"
````

* Always use the translation key as first parameter!
* If a key is missing, the key itself will be shown (easy to spot missing translations).

---

## Adding New Translations

* Add new keys (and translations) to the `_en_dict()` and `_de_dict()` methods in `locale.py`.
* To add new languages, define a new method (e.g. `_fr_dict()` for French) and add it to the `self.supported` dict.

---

## Best Practices

* Never hard-code user-facing strings in your GUI or feature modules!
* All dialogs, buttons, status messages etc. should be wrapped with `locale.t("key")`.
* Always add both English and German texts for new keys.

---

## Integration with Settings

* The user's selected language can be saved in the config or user profile.
* On app start, set language with:

  ```python
  lang = config_loader.get_config_value("General", "language", default="en")
  locale.set_language(lang)
  ```
* When the user changes the language, call `locale.set_language(new_lang)` and update all relevant UI elements.

---

## Why is this important?

* Ensures the app is accessible for both German and English-speaking users.
* Makes adding future languages or rewording messages a one-place change.
* Guarantees consistency and professionalism in all user interactions.

---

*See locale.py for all available translation keys and for further extension instructions.*

```

---

**Lege diese README.md in `core/i18n/` ab – so weiß jeder Entwickler und jedes GPT sofort, wie die Sprachunterstützung funktioniert!**
```
