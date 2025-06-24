QMToolPy/
├── core/                       # Alle Core-Hilfsmodule (Helpers, Logger, Config, Auth etc.)
│   ├── config_loader.py        # Konfigurationsloader
│   ├── logger.py               # Logger
│   ├── status_helper.py        # Statusleisten-Hilfe
│   ├── locale.py               # Übersetzungs-Manager
│   ├── auth_manager.py         # Authentifizierungs-Manager (noch minimal)
│   ├── license_manager.py      # Lizenzprüfer
│   ├── date_time_helper.py     # Zeitfunktionen
│   └── ...                    # ggf. weitere Core-Module
│
├── config/                     # Konfigurationsdateien (z.B. config.ini)
│   └── config.ini
│
├── features/                   # Alle Feature-Module (pro Feature ein eigener Ordner)
│   ├── usermanagement/
│   │   ├── gui/
│   │   │   └── user_view.py
│   │   ├── logic/
│   │   │   └── user_manager.py
│   │   └── api/
│   │       └── user_api.py
│   ├── documentoverview/
│   │   ├── gui/
│   │   │   └── documents_view.py
│   │   ├── logic/
│   │   │   └── documents_service.py
│   │   └── api/
│   │       └── documents_api.py
│   └── test1/
│       ├── gui/
│       │   └── test1_view.py
│       ├── logic/
│       │   └── test1_service.py
│       └── api/
│           └── test1_api.py
│
├── main.py                    # Startpunkt der Anwendung (z.B. MainWindow, GUI-Start)
└── README.md                  # Projektdokumentation