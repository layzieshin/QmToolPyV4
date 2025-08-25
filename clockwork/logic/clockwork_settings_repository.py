"""
ClockworkSettingsRepository
---------------------------
Persistence for Clockwork settings using config/config.ini without modifying
your existing config loader.

Strategy:
- Try to locate config/config.ini defensively (env var, core.config_loader,
  upward traversal).
- Read on startup; create [Clockwork] if missing.
- Write atomically (temp file + replace) to avoid partial writes.

No external dependencies are required.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Optional

from ..models.clockwork_settings import ClockworkSettings


class ClockworkSettingsRepository:
    """
    Loads and saves ClockworkSettings in the [Clockwork] section.
    """

    SECTION = "Clockwork"

    def __init__(self) -> None:
        self.config_path = self._find_config_ini()
        self._config = configparser.ConfigParser()
        self._read()

    # --- Public API ---------------------------------------------------------

    def load(self) -> ClockworkSettings:
        """
        Returns settings loaded from config.ini, or defaults if missing.
        """
        cfg = self._config
        if not cfg.has_section(self.SECTION):
            return ClockworkSettings()

        sec = cfg[self.SECTION]
        return ClockworkSettings(
            timezone=sec.get("timezone", "Europe/Berlin"),
            show_seconds=sec.getboolean("show_seconds", True),
            use_24h=sec.getboolean("use_24h", True),
            show_date=sec.getboolean("show_date", True),
            date_format=sec.get("date_format", "%Y-%m-%d"),
            blink_colon=sec.getboolean("blink_colon", False),
            update_interval_ms=sec.getint("update_interval_ms", 250),
        )

    def save(self, s: ClockworkSettings) -> None:
        """
        Persists settings atomically. Creates the [Clockwork] section if needed.
        """
        cfg = self._config
        if not cfg.has_section(self.SECTION):
            cfg.add_section(self.SECTION)

        cfg.set(self.SECTION, "timezone", s.timezone)
        cfg.set(self.SECTION, "show_seconds", str(bool(s.show_seconds)))
        cfg.set(self.SECTION, "use_24h", str(bool(s.use_24h)))
        cfg.set(self.SECTION, "show_date", str(bool(s.show_date)))
        cfg.set(self.SECTION, "date_format", s.date_format)
        cfg.set(self.SECTION, "blink_colon", str(bool(s.blink_colon)))
        cfg.set(self.SECTION, "update_interval_ms", str(int(s.update_interval_ms)))

        self._atomic_write(cfg, self.config_path)

    # --- Internal helpers ---------------------------------------------------

    def _read(self) -> None:
        self._config.read(self.config_path)

    @staticmethod
    def _atomic_write(cfg: configparser.ConfigParser, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            cfg.write(f)
        tmp.replace(path)

    @staticmethod
    def _find_config_ini() -> Path:
        """
        Tries several strategies to locate the central config.ini:

        Order:
            1) Env var QMTOOL_CONFIG_PATH (file path to config.ini)
            2) core.config_loader.get_config_file_path() if available
            3) Walk upwards from this file until a 'config/config.ini' is found
            4) Fallback to project-root-relative './config/config.ini'

        Returns:
            Path: Path to config.ini (not guaranteed to exist).
        """
        # 1) Environment
        env_p = os.environ.get("QMTOOL_CONFIG_PATH")
        if env_p:
            p = Path(env_p).expanduser().resolve()
            if p.exists() and p.is_file():
                return p

        # 2) Try your config_loader without importing symbols by name
        try:
            from core import config_loader  # type: ignore
            # try the most likely helper names
            for attr in ("get_config_file_path", "config_path", "CONFIG_FILE_PATH"):
                if hasattr(config_loader, attr):
                    candidate = getattr(config_loader, attr)
                    if callable(candidate):
                        cp = Path(candidate())
                    else:
                        cp = Path(candidate)
                    if cp.exists():
                        return cp.resolve()
        except Exception:
            pass

        # 3) Upward traversal looking for config/config.ini
        here = Path(__file__).resolve()
        for _ in range(6):
            maybe = here.parent / "config" / "config.ini"
            if maybe.exists():
                return maybe.resolve()
            here = here.parent

        # 4) Fallback (will be created on first save)
        return Path.cwd() / "config" / "config.ini"
