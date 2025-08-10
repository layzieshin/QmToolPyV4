import csv
from pathlib import Path
from core.logging.logic.logger import logger

LOCALE_TRACK_MISSING_KEYS = True

class TranslationManager:
    """
    Verwaltet Übersetzungen aus einer zentralen labels.tsv Datei.
    Unterstützt Logging von fehlenden Einträgen.
    """

    def __init__(self):
        self.translations = {}  # {lang: {label: text}}
        self.coverage = {}      # {lang: float}
        self.file_path: Path | None = None     # <— neu
        self._missing_keys_logged = set()

    def load_file(self, file_path: Path):
        """Lädt und analysiert die Übersetzungsdatei."""
        self.file_path = file_path.resolve()    # <— merken
        with open(file_path, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            langs = header[1:]
            for lang in langs:
                self.translations.setdefault(lang, {})

            row_count = 0
            for row in reader:
                if not row:
                    continue
                row_count += 1
                label = row[0]
                for i, lang in enumerate(langs):
                    text = row[i + 1] if i + 1 < len(row) else ""
                    self.translations[lang][label] = text

            # Coverage berechnen
            for lang in langs:
                translated = sum(bool(v) for v in self.translations[lang].values())
                self.coverage[lang] = translated / row_count if row_count else 1.0

    def available_languages(self) -> list[str]:
        """Gibt alle geladenen Sprachen zurück."""
        return list(self.translations.keys())

    def t(self, label: str, lang: str) -> str:
        """
        Gibt die Übersetzung zurück oder das Label selbst (als Fallback).
        Loggt fehlende Keys nur einmalig (sofern aktiviert).
        """
        value = self.translations.get(lang, {}).get(label)
        if value:
            return value

        if LOCALE_TRACK_MISSING_KEYS and (label, lang) not in self._missing_keys_logged:
            from core.common.app_context import AppContext    # noqa: WPS433
            user = AppContext.current_user
            logger.log(
                feature="Locale",
                event="MissingKey",
                user_id=user.id if user else None,
                username=user.username if user else None,
                message=f"Missing translation key '{label}' (lang={lang})",
            )
            self._missing_keys_logged.add((label, lang))

        return label

# Globale Instanz
translations = TranslationManager()

def T(label: str) -> str:
    """Global verwendbare Übersetzungsfunktion mit AppContext-Verknüpfung."""
    from core.common.app_context import AppContext  # noqa: WPS433
    lang = AppContext.settings_manager.get("app", "language", user_specific=True, fallback="de")
    return translations.t(label, lang)
