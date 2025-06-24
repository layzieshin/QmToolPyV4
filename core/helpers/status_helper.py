"""
status_helper.py

Hilfsfunktion für Statusleistenmeldungen in der GUI.

- Setzt eine Meldung temporär in einem Label oder einer Statuszeile.
- Meldung wird nach Ablauf einer definierten Dauer automatisch gelöscht.
"""

import threading

def set_status(setter_func, message: str, duration: int = 5):
    """
    Setzt die Statusmeldung und löscht sie ggf. nach einer Dauer.

    :param setter_func: Funktion, die den Text setzt, z.B. label.config
    :param message: Die anzuzeigende Statusmeldung
    :param duration: Wie lange die Meldung angezeigt wird (Sekunden, 0=permanent)
    """
    setter_func(text=message)
    if duration > 0:
        def clear():
            setter_func(text="")
        timer = threading.Timer(duration, clear)
        timer.daemon = True
        timer.start()
