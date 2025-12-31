# word_meta – Feature README

## Zweck
- Utility/Viewer für Word-Metadaten & Review-Comments.

## Discovery
- `meta.json` ist die Discovery-Quelle (required keys: `id`, `label`, `version`, `main_class`).
- `id`: `word_meta`
- `main_class`: `word_meta.gui.main.WordCommentsViewer`

## Contracts (contracts.json)
### Provides
- UI `main_view`: `word_meta.gui.main.WordCommentsViewer`

### Requires
- Services: *(none detected via constructor DI)*

## Usage
1. Feature-Ordner enthält `meta.json` (und künftig auch `contracts.json`).
2. App startet über `main.py` → `framework.gui.main_window.MainWindow`.
3. Navigation lädt `main_class` über `ModuleDescriptor.safe_load_class()`.
4. DI erfolgt über Parameternamen im `__init__` (keyword-only params).

## Diagrams
### Dependencies
```mermaid
graph LR
  word_meta([word_meta])
  word_meta
```
### Load + DI
```mermaid
sequenceDiagram
  participant MW as MainWindow
  participant MD as ModuleDescriptor
  participant V as FeatureView
  participant AC as AppContext.services

  MW->>MD: safe_load_class(main_class)
  MW->>AC: resolve DI params by name
  MW->>V: instantiate(parent, **deps)
  V-->>MW: UI renders
```

## Open Points / TODOs
- Interfaces/ABCs (`core/contracts/*`) sind im Repo noch nicht vorhanden → `contracts.json` referenziert bewusst keine Interface-Pfade.
- Dieses Feature enthält Template-Platzhalter in `gui/modul_view.py` / `gui/modul_settings_view.py`.

