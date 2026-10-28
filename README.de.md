# talking-slides

**Aufnahme reinziehen — Präsentation bekommen, die sich selbst abspielt.**
Vorlesung, Seminar oder ein Video-Link → Folien mit Kernaussagen, vollständiges
Transkript und Kapitel. Komplett lokal: Aufnahmen verlassen Ihren Rechner
nie — keine API-Schlüssel, keine Cloud.

![Transcriber.app-Fenster](docs/screenshot-en.png)

[English](README.md) | [Русский](README.ru.md) | [Español](README.es.md) | Deutsch | [中文](README.zh.md)

## Was es von Whisper-Wrappern unterscheidet

- **Folien, die sich selbst abspielen.** Jede Folie hat Zeitmarken — und
  wir nutzen sie wirklich: die PPTX enthält standardmäßig in jeder Folie
  ihr Audiofragment (es spielt direkt in PowerPoint), und der
  Offline-HTML-Player ergibt eine Kapitelnavigation mit ▶-Taste pro Folie.
  Ein Klick — und Sie hören die ursprüngliche Stelle der Vorlesung.
- **Kapitel für YouTube** — `chapters.txt` im fertigen
  Beschreibungsformat (`00:00 Einführung…`). Kopieren, veröffentlichen,
  fertig.
- **Datenschutz.** Die Transkription läuft auf einem lokalen
  faster-whisper-Modell. Das Netz wird nur genutzt, um bei der Installation
  das Modell und Audio von einem Link herunterzuladen, den Sie selbst
  angeben.

## Funktionen

- Eingabe: Audio in jedem Format, das ffmpeg liest (~45 Endungen,
  einschließlich Tonspuren von mp4/mov/mkv), oder ein Video-Link
  (YouTube, VK und alles, was yt-dlp unterstützt).
- Ausgabe: PDF, PPTX (mit dem Audio der Aufnahme in jeder Folie —
  standardmäßig), HTML-Player, vollständiges Transkript und
  YouTube-Kapitel.
- Sprache: automatisch erkannt oder manuell gewählt (lateinische und
  kyrillische Schrift).
- Folien-Themen werden nach Inhalt ausgewählt (midnight, ocean, …).
- Native macOS-App (Swift/AppKit): Drag & Drop, Fortschritt pro Phase,
  Abbruch; dazu ein CLI.

## Schnellstart

```bash
./install.sh            # venv + Abhängigkeiten + (auf Nachfrage) das ~1,5-GB-Modell
./install.sh --app      # dasselbe + Transcriber.app bauen
```

Das Skript fragt vor dem Modell-Download und braucht nichts außer
`python3` (3.10+), Homebrew/ffmpeg und ~4 GB Speicher.

### CLI

```bash
.venv/bin/python pipeline.py vorlesung.m4a --formats pdf,pptx,html
.venv/bin/python pipeline.py https://youtube.com/watch?v=… --lang en --beam 1
```

| Option | Bedeutung |
|---|---|
| `--formats pdf,pptx,html,txt` | was erzeugt wird |
| `--no-pptx-audio` | kein Audio in die PPTX einbetten (standardmäßig eingebettet) |
| `--lang auto\|ru\|en\|…` | Sprache der Aufnahme/Ausgabe |
| `--beam N` | 5 — Qualität, 1 — 2–4× schneller |
| `--theme auto\|NAME` | Folien-Design |

### Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```

25 Offline-Tests: YouTube-Kapitelregeln, safe_stem, Folienheuristik,
PDF/PPTX/HTML-Erzeugung in einem Tempordner (einschließlich Prüfung des
in die PPTX eingebetteten Audios). Ohne Modell.

### Die App

```bash
./app-sources/build_app.sh                # baut build/Transcriber.app
cp -R build/Transcriber.app /Applications/
```

Erster Start: Rechtsklick auf die App → „Öffnen“ — der Build ist
ad-hoc-signiert, Gatekeeper warnt. Die App findet das Projekt selbst
(neben dem Bundle oder in `~/audio-transcriber`); der Pfad lässt sich
über `AUDIO_TRANSCRIBER_DIR` setzen. Ergebnis-Buttons: PDF, PPTX, HTML
und „Ordner öffnen“ — Transkript und `chapters.txt` öffnen sich aus dem
Ergebnisordner.

## Wie es funktioniert

1. Audio wird über PyAV/ffmpeg dekodiert; Links lädt yt-dlp herunter.
2. faster-whisper (large-v3-turbo, int8, CPU) transkribiert mit Zeitmarken.
3. Eine Offline-Heuristik teilt das Transkript nach Pausen und Umfang in
   Kapitel und wählt die Kernaussagen.
4. Die Renderer bauen PDF/PPTX/HTML; ffmpeg schneidet die Audiofragmente
   nach den Zeitmarken der Folien.

## Voraussetzungen

- macOS 12+ (das CLI läuft auch unter Linux; die App nur auf macOS);
- python 3.10+, ffmpeg;
- ~4 GB Speicher: das 1,5-GB-Modell + Abhängigkeiten;
- nur CPU: langsamer heißt nicht schlechter — beam 1 liefert akzeptable
  Qualität 2–4× schneller.

## Ehrliche Einschränkungen

- Eine PPTX mit Ton ist schwerer: standardmäßig enthält sie die gesamte
  Aufnahme (~43 MB pro Stunde Audio, AAC 96k). Kein Ton nötig?
  `--no-pptx-audio`.
- CPU-Tempo: beam 5 entspricht etwa dem 4–5-fachen der Echtzeit (eine
  Stunde Aufnahme dauert rund 4–5 Stunden); beam 1 ist schneller, aber
  grober.
- PDF/PPTX nutzen Arial: Sprachen in lateinischer und kyrillischer
  Schrift; für zh/ja/ar wären andere Schriften und Text-Shaping nötig —
  nicht enthalten.
- Die Folien entstehen mit einer Offline-Heuristik: Titel sind die ersten
  Sätze der Kapitel; ohne LLM. Die Qualität hängt davon ab, wie
  strukturiert gesprochen wird.
- Link-Downloads funktionieren, solange yt-dlp und die Plattform es
  unterstützen.

## Datenschutz

Transkription und Erzeugung laufen lokal. Bei normaler Nutzung kommt aus
dem Netz nur das Audio, das Sie ausdrücklich als Link angeben. Aufnahmen,
Transkripte und Fragmente bleiben auf Ihrem Rechner.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
