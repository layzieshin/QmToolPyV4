import os

def create_init_files(root_dir):
    """
    Legt in jedem Ordner unter root_dir (inklusive root_dir) eine leere __init__.py an,
    sofern diese noch nicht existiert.
    """
    for dirpath, dirnames, filenames in os.walk(root_dir):
        init_path = os.path.join(dirpath, '__init__.py')
        if not os.path.exists(init_path):
            with open(init_path, 'w', encoding='utf-8') as f:
                pass  # Leere Datei erzeugen
            print(f'__init__.py erstellt in: {dirpath}')
        else:
            print(f'__init__.py existiert bereits in: {dirpath}')

if __name__ == '__main__':
    # Root-Verzeichnis ist der Ordner, in dem dieses Skript liegt
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Starte Suche und Anlegen von __init__.py ab: {script_dir}")

    create_init_files(script_dir)
    print("Fertig!")
