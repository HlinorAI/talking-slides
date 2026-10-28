# talking-slides

**Drop in a recording — get a presentation that plays itself.**
A lecture, a seminar, or a video link → slides with takeaways, a full
transcript, and chapters. Fully local: recordings never leave your
computer — no API keys, no cloud.

![Transcriber.app window](docs/screenshot-en.png)

English | [Русский](README.ru.md) | [Español](README.es.md) | [Deutsch](README.de.md) | [中文](README.zh.md)

## What makes it different from Whisper wrappers

- **Slides that play themselves.** Every slide has timestamps — and we
  actually use them: the PPTX embeds each slide's audio fragment by
  default (it plays right inside PowerPoint), and the offline HTML player
  adds chapter navigation with a ▶ button on every slide. One click — and
  you hear the original moment of the lecture.
- **Chapters for YouTube** — `chapters.txt` in the ready-to-paste
  description format (`00:00 Introduction…`). Copy, publish, done.
- **Privacy.** Transcription runs on a local faster-whisper model. The
  network is used only to download the model during installation and to
  fetch audio from a link you provide.

## Features

- Input: audio in any format ffmpeg can read (~45 extensions, including
  sound tracks of mp4/mov/mkv), or a video link (YouTube, VK, and
  everything yt-dlp supports).
- Output: PDF, PPTX (with the recording embedded per slide — on by
  default), an HTML player, the full transcript, and YouTube chapters.
- Language: auto-detected, or picked manually (Latin and Cyrillic scripts).
- Slide themes matched to the content (midnight, ocean, …).
- A native macOS app (Swift/AppKit): drag & drop, per-stage progress,
  cancel; plus a CLI.

## Quick start

```bash
./install.sh            # venv + dependencies + (on request) the ~1.5 GB model
./install.sh --app      # same + build Transcriber.app
```

The script asks before downloading the model and needs nothing beyond
`python3` (3.10+), Homebrew/ffmpeg, and ~4 GB of disk.

### CLI

```bash
.venv/bin/python pipeline.py lecture.m4a --formats pdf,pptx,html
.venv/bin/python pipeline.py https://youtube.com/watch?v=… --lang en --beam 1
```

| Option | Meaning |
|---|---|
| `--formats pdf,pptx,html,txt` | what to render |
| `--no-pptx-audio` | don't embed audio in the PPTX (it is embedded by default) |
| `--lang auto\|ru\|en\|…` | language of the recording/output |
| `--beam N` | 5 — quality, 1 — 2–4× faster |
| `--theme auto\|NAME` | slide theme |

### Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```

25 offline tests: YouTube chapter rules, safe_stem, slide heuristics,
PDF/PPTX/HTML rendering into a temp folder (including a check of the
audio embedded in the PPTX), and localization consistency. No model
needed.

### The app

```bash
./app-sources/build_app.sh                # build build/Transcriber.app
cp -R build/Transcriber.app /Applications/
```

First launch: right-click the app → «Open» — the build is ad-hoc signed,
so Gatekeeper will warn. The app finds the project on its own (next to
the bundle or in `~/audio-transcriber`); the path can be set with the
`AUDIO_TRANSCRIBER_DIR` variable. Result buttons: PDF, PPTX, HTML and
«Open Folder» — the transcript and `chapters.txt` open from the results
folder.

## How it works

1. Audio is decoded via PyAV/ffmpeg; links are downloaded with yt-dlp.
2. faster-whisper (large-v3-turbo, int8, CPU) transcribes with timestamps.
3. An offline heuristic splits the transcript into chapters by pauses and
   volume, and picks the takeaways.
4. Renderers build PDF/PPTX/HTML; ffmpeg cuts the audio fragments by
   slide timestamps.

## Requirements

- macOS 12+ (the CLI also works on Linux; the app is macOS-only);
- python 3.10+, ffmpeg;
- ~4 GB of disk: the 1.5 GB model + dependencies;
- CPU-only: slower isn't worse — beam 1 gives acceptable quality 2–4×
  faster.

## Honest limitations

- A talking PPTX is heavier: by default it contains the entire recording
  (~43 MB per hour of audio, AAC 96k). Don't need the sound? Use
  `--no-pptx-audio`.
- CPU speed: beam 5 is roughly 4–5× realtime (a one-hour recording takes
  about 4–5 hours); beam 1 is faster but rougher.
- PDF/PPTX use Arial: Latin and Cyrillic languages; zh/ja/ar would need
  another font and text shaping — not included.
- Slides are built by an offline heuristic: titles are the first
  sentences of chapters; no LLM. Quality depends on how structured the
  speech is.
- Link downloads work as long as yt-dlp and the hosting service do.

## Privacy

Transcription and rendering run locally. In normal use the only network
traffic is the audio you explicitly provide as a link. Recordings,
transcripts and fragments stay on your machine.

## License

MIT — see [LICENSE](LICENSE).
