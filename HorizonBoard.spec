# -*- mode: python ; coding: utf-8 -*-

# Definiere die Daten (Templates und Static), die kopiert werden sollen
# Das Format ist ('Quellpfad im Projekt', 'Zielordner im Paket')
# Stelle sicher, dass die Ordner 'templates' und 'static' in demselben
# Verzeichnis wie diese .spec-Datei und app.py liegen.
app_data = [
    ('templates', 'templates'),
    ('static', 'static')
]

# --- Analysis-Sektion ---
# Hier werden die Skripte analysiert und Abhängigkeiten gefunden.
a = Analysis(
    ['app.py'], # Deine Haupt-App-Datei
    pathex=[],   # Zusätzliche Pfade für Modulsuche (normalerweise nicht nötig)
    binaries=[], # Eventuelle externe .dll oder .so Dateien
    datas=app_data, # Hier werden Templates/Static eingebunden!
    hiddenimports=[], # Liste für Module, die PyInstaller nicht automatisch findet
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[], # Module, die explizit ausgeschlossen werden sollen
    noarchive=False,
    optimize=0, # Optimierungslevel (0 ist Standard)
)

# --- PYZ-Sektion ---
# Erstellt das Python-Archiv (.pyz) mit dem kompilierten Bytecode.
pyz = PYZ(a.pure)

# --- EXE-Sektion ---
# Konfiguriert die eigentliche .exe-Datei.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries, # Binärdateien aus Analysis übernehmen
    a.zipfiles, # ZIP-Dateien aus Analysis übernehmen
    a.datas,    # WICHTIG: Daten (Templates/Static) hier erneut angeben!
    [],         # Liste von Dateien, die direkt neben der EXE liegen sollen (selten nötig)
    name='HorizonBoardApp', # Name der resultierenden EXE-Datei
    debug=False,
    bootloader_ignore_signals=False,
    strip=False, # Symbole entfernen? (Kann Größe reduzieren, Debugging erschweren)
    upx=True,    # UPX-Kompression verwenden? (Reduziert Größe, braucht UPX installiert)
    console=False, # KEIN Konsolenfenster anzeigen (wichtig für Web-Apps)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None, # Zielarchitektur (None = aktuell)
    codesign_identity=None,
    entitlements_file=None,
    # icon='pfad/zu/deinem/icon.ico' # Optional: Füge hier den Pfad zu einer .ico-Datei hinzu
)

# --- COLLECT-Sektion (nur für Ordner-Modus relevant) ---
# Sammelt alle Teile (EXE, DLLs, Daten) in einem Ausgabeordner.
# Wenn du später den --onefile Modus verwendest, wird diese Sektion ignoriert.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas, # Daten auch hier sammeln
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HorizonBoardApp', # Name des Ausgabeordners im 'dist'-Verzeichnis
)
