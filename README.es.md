# talking-slides

![tests](https://github.com/HlinorAI/talking-slides/actions/workflows/tests.yml/badge.svg)
**Suelta una grabación — obtén una presentación que se reproduce sola.**
Una clase, un seminario o un enlace de vídeo → diapositivas con ideas
clave, transcripción completa y capítulos. Todo en local: las grabaciones
nunca salen de tu ordenador — sin claves de API, sin nube.

![Ventana de Transcriber.app](docs/screenshot-en.png)

[English](README.md) | [Русский](README.ru.md) | Español | [Deutsch](README.de.md) | [中文](README.zh.md)

## Qué lo diferencia de los envoltorios de Whisper

- **Diapositivas que se reproducen solas.** Cada diapositiva tiene sus
  marcas de tiempo — y las usamos de verdad: el PPTX incluye por defecto
  el fragmento de audio de cada diapositiva (se reproduce dentro del
  propio PowerPoint), y el reproductor HTML sin conexión añade navegación
  por capítulos con un botón ▶ en cada diapositiva. Un clic — y oyes el
  momento original de la clase.
- **Capítulos para YouTube** — `chapters.txt` en el formato listo para
  pegar en la descripción (`00:00 Introducción…`). Copiar, publicar, listo.
- **Privacidad.** La transcripción usa un modelo faster-whisper local. La
  red solo se usa para descargar el modelo durante la instalación y para
  descargar audio de un enlace que tú mismo facilitas.

## Funciones

- Entrada: audio en cualquier formato que ffmpeg lea (~45 extensiones,
  incluidas las pistas de sonido de mp4/mov/mkv), o un enlace de vídeo
  (YouTube, VK y todo lo que soporta yt-dlp).
- Salida: PDF, PPTX (con el audio de la grabación en cada diapositiva —
  por defecto), reproductor HTML, transcripción completa y capítulos de
  YouTube.
- Idioma: detección automática o selección manual (alfabetos latino y
  cirílico).
- Temas de diapositivas elegidos según el contenido (midnight, ocean, …).
- App nativa de macOS (Swift/AppKit): arrastrar y soltar, progreso por
  etapas, cancelar; además de la línea de comandos.

## Inicio rápido

```bash
./install.sh            # venv + dependencias + (si quieres) el modelo de ~1,5 GB
./install.sh --app      # lo mismo + compilar Transcriber.app
```

El script pregunta antes de descargar el modelo y no necesita nada más
que `python3` (3.10+), Homebrew/ffmpeg y ~4 GB de disco.

### CLI

```bash
.venv/bin/python pipeline.py clase.m4a --formats pdf,pptx,html
.venv/bin/python pipeline.py https://youtube.com/watch?v=… --lang en --beam 1
```

| Opción | Significado |
|---|---|
| `--formats pdf,pptx,html,txt` | qué generar |
| `--no-pptx-audio` | no incrustar audio en el PPTX (por defecto se incrusta) |
| `--lang auto\|ru\|en\|…` | idioma de la grabación/salida |
| `--beam N` | 5 — calidad, 1 — 2–4× más rápido |
| `--theme auto\|NOMBRE` | tema de las diapositivas |

### Pruebas

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```

25 pruebas sin conexión: reglas de capítulos de YouTube, safe_stem,
heurística de diapositivas, generación de PDF/PPTX/HTML en una carpeta
temporal (incluida la comprobación del audio incrustado en el PPTX).
No necesita el modelo.

### La app

```bash
./app-sources/build_app.sh                # compila build/Transcriber.app
cp -R build/Transcriber.app /Applications/
```

Primer arranque: clic derecho en la app → «Abrir» — la compilación está
firmada ad-hoc y Gatekeeper avisará. La app encuentra el proyecto sola
(junto al bundle o en `~/audio-transcriber`); la ruta se puede fijar con
la variable `AUDIO_TRANSCRIBER_DIR`. Botones de resultado: PDF, PPTX,
HTML y «Abrir carpeta» — la transcripción y `chapters.txt` se abren desde
la carpeta de resultados.

## Cómo funciona

1. El audio se decodifica con PyAV/ffmpeg; los enlaces se descargan con
   yt-dlp.
2. faster-whisper (large-v3-turbo, int8, CPU) transcribe con marcas de
   tiempo.
3. Una heurística sin conexión divide la transcripción en capítulos por
   pausas y volumen, y elige las ideas clave.
4. Los renderizadores construyen PDF/PPTX/HTML; ffmpeg corta los
   fragmentos de audio según las marcas de tiempo de cada diapositiva.

## Requisitos

- macOS 12+ (el CLI funciona también en Linux; la app es solo macOS);
- python 3.10+, ffmpeg;
- ~4 GB de disco: el modelo de 1,5 GB + dependencias;
- solo CPU: más lento no significa peor — beam 1 da calidad aceptable
  2–4× más rápido.

## Limitaciones (con honestidad)

- Un PPTX con sonido pesa más: por defecto contiene toda la grabación
  (~43 MB por hora de audio, AAC 96k). ¿No necesitas el sonido?
  `--no-pptx-audio`.
- Velocidad de CPU: beam 5 es unas 4–5× el tiempo real (una hora de
  grabación tarda unas 4–5 horas); beam 1 es más rápido pero más tosco.
- PDF/PPTX usan Arial: idiomas en alfabeto latino y cirílico; para
  zh/ja/ar haría falta otra fuente y modelado de texto — no incluido.
- Las diapositivas las construye una heurística sin conexión: los títulos
  son las primeras frases de cada capítulo; sin LLM. La calidad depende
  de lo estructurado del discurso.
- La descarga por enlaces funciona mientras lo soporten yt-dlp y la
  plataforma.

## Privacidad

La transcripción y la generación se ejecutan en local. Con uso normal, lo
único que viene de la red es el audio que tú das explícitamente como
enlace. Grabaciones, transcripciones y fragmentos se quedan en tu máquina.

## Licencia

MIT — véase [LICENSE](LICENSE).
