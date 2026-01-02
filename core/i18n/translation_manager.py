import csv
from pathlib import Path
from core.qm_logging.logic.logger import logger

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

    def load_files(self, file_paths: list[Path]) -> None:
        """Lädt und analysiert mehrere Übersetzungsdateien."""
        self.translations = {}
        self.coverage = {}
        self.file_path = None
        all_labels: set[str] = set()

        for file_path in file_paths:
            if self.file_path is None:
                self.file_path = file_path.resolve()
            with open(file_path, encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                header = next(reader)
                langs = header[1:]
                for lang in langs:
                    self.translations.setdefault(lang, {})

                for row in reader:
                    if not row:
                        continue
                    label = row[0]
                    all_labels.add(label)
                    for i, lang in enumerate(langs):
                        text = row[i + 1] if i + 1 < len(row) else ""
                        self.translations[lang][label] = text

        row_count = len(all_labels)
        for lang in self.translations:
            translated = sum(bool(v) for v in self.translations[lang].values())
            self.coverage[lang] = translated / row_count if row_count else 1.0

    def load_file(self, file_path: Path) -> None:
        """Kompatibilitätsmethode für Einzeldateien."""
        self.load_files([file_path])

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
            user = AppContext.get_current_user()
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

    user_id = None
    if hasattr(AppContext, "get_current_user_id"):
        user_id = AppContext.get_current_user_id()

    lang = AppContext.settings_manager.get(
        "app",
        "language",
        fallback="de",
        user_specific=bool(user_id),
        user_id=user_id,
    )
    return translations.t(label, lang)