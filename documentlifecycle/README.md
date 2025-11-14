# Document Lifecycle (Feature)

GUI-first skeleton for a document lifecycle module following the Developer Guide.
- SRP: each UI widget lives in its own file
- DI: uses SettingsManager / LicensingService via constructor param names
- i18n: uses T() with safe fallbacks
