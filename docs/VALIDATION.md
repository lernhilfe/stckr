# Validierung

Stand: 30. Oktober 2026. Die nachfolgenden Messungen beziehen sich auf die hier entwickelte Version 0.1.0. Sie sind kein Gleichwertigkeitsnachweis zu Helicon Focus.

## Tatsächlich ausgeführt

- **20 automatisierte Tests bestanden**: alle drei Fusionen gegen synthetische scharfe Zielbilder, konstante Flächen, Subpixel-Registrierung, garantiert gültiger Beschnitt, DNG-Tags und numerischer Roundtrip über LibRaw, 16-Bit-TIFF-Präzision, atomarer Export, überlappende Pinselstriche, persistentes Undo/Redo, Projekttransport, Abbruch, Größenkonflikte und Windows-kompatibler `spawn`-Worker.
- **Ruff-Prüfung bestanden** für Engine, Oberfläche, Tests und Skripte.
- **GUI-Smoke bestanden**: tatsächliche QML-Oberfläche geladen und gerendert, leere Ansicht und gefüllte Arbeitsfläche als Screenshots geprüft. Zusätzlicher GUI-Smoke mit echtem Worker-Prozess.
- **Echte EOS-M50-Daten**: `IMG_0482_raw.CR3` und `IMG_0483_craw.CR3` aus `lclevy/canon_cr3`, Commit `151c1a965775ef409ace17714c24ed491cfcf9c4`. Zusätzlich `canon_eos_m50_02.cr3` decodiert. Keine dieser Fotografien wird mit STCKR verteilt.
- RAW und C-RAW in voller Auflösung importiert, ausgerichtet, mit C gestackt und als Linear-DNG exportiert. Aufnahmegröße vor Ausrichtung: **6024 × 4020**; Ergebnis nach gemeinsamem Beschnitt: **5976 × 3984**.
- **Adobe DNG SDK 1.7.0.0** (`emmcb/adobe-dng-sdk`, Commit `962a7028efdc8f8a651cf6335c3ec53053472339`): exportierten M50-Stack vollständig validiert, ohne Warnungen oder Fehler. Der Prüfer kann trotz Fehlermeldungen mit Status 0 enden; `scripts/validate_dng.py` prüft deshalb zusätzlich die Diagnoseausgabe.
- **Unabhängiger Decoder-Roundtrip**: DNG über rawpy/LibRaw erneut geöffnet und lineare Pixel numerisch mit dem internen Stack verglichen; maximale Abweichung unter 0,001 im normierten Bereich. TIFF-Struktur und 16-Bit-Quantisierung separat mit tifffile geprüft.
- **Portables Linux-Paket** mit PyInstaller erstellt und ohne Quellcode-Import über die Anwendung getestet: TIFF-Export, Linear-DNG-Import/-Export und GUI-Worker-Smoke. Dies ersetzt keinen Windows-Pakettest.

## Lasttest

Linux-Entwicklungsumgebung mit etwa 10 GB RAM, vier OpenCV-Threads; keine erforderliche GPU.

| Test | Ergebnis |
| --- | --- |
| 100 Fusionsdurchläufe, 6000 × 4000, Methode C | 87,49 Sekunden |
| Gemessener Spitzen-RSS dieses Prozesses | 1775,7 MiB |
| Korpus | Acht vollständige synthetische Float32-Frames wiederholt gelesen |

Der Fusionslasttest misst weder CR3-Decodierung noch Ausrichtung oder den SSD-Bedarf von 100 verschiedenen Bildern. Er belegt die begrenzte Speichernutzung der Fusion. Für einen vollständigen Durchlauf mit 100 verschiedenen 24-MP-RAWs einschließlich aller Zwischenbilder fehlen in dieser Umgebung die erforderlichen mehr als 60 GB freier SSD-Speicher. Zusätzlich bestanden: zwölf unterschiedliche synthetische 24-MP-PNG-Dateien vollständig importiert, verarbeitet und als Ergebnis gespeichert (ohne Ausrichtung): 50.72 Sekunden, 2064.6 MiB Spitzen-RSS.

Reproduktion:

```sh
uv run pytest -q
uv run python scripts/smoke_gui.py --demo --screenshot studio.png
uv run python scripts/validate_raw.py /path/to/canon_cr3/samples /path/to/output --validator /path/to/dng-validate
uv run python scripts/benchmark.py --fusion-only --frames 100 --width 6000 --height 4000
uv run python scripts/benchmark.py --frames 12 --width 6000 --height 4000
```

## Plattformprüfung und offene Abnahme

Der GitHub-Actions-Workflow führt Tests auf Windows und Linux aus. Der Windows-Job erstellt das portable Paket und testet die gebündelte Anwendung einschließlich RAW/DNG und Prozessstart. Der Linux-Job wiederholt außerdem den echten M50-Stack mit Adobe-Validator. Der aktuelle Laufstatus ist im Repository unter Actions sichtbar.

Hier nicht verfügbar und deshalb nicht als bestanden behauptet:

- Sichtprüfung in Lightroom und Adobe Camera Raw, einschließlich Weißabgleich, Tonwertbearbeitung und verschiedener Adobe-Kameraprofile.
- Direkter Vergleich mit Helicon Focus auf identischen echten Makro-Fokusserien, besonders Haare, Überdeckungen, Reflexe und Bewegung.
- Vollständiger 100-RAW-Durchlauf auf einem 16-GB-Windows-Rechner.
- Codesignierung des Windows-Pakets.

Die Verfahren können bei Bewegung und Verdeckungen Artefakte erzeugen. Quellenretusche korrigiert solche Fälle; sie ersetzt keine fehlende scharfe Aufnahme. Die gespeicherte Tiefenkarte enthält Fokusebenen-Indizes und ist keine metrisch kalibrierte Entfernungskarte.
