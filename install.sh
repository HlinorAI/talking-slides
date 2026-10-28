#!/usr/bin/env bash
# audio-transcriber first-run installer: venv, dependencies, model, app build.
# Установщик первого запуска: venv, зависимости, модель, сборка приложения.
# Usage:
#   ./install.sh          — venv + deps + (on request) model
#   ./install.sh --app    — same + build Transcriber.app
# Messages follow LANG / AT_UI_LANG (ru → Russian, otherwise English).
set -euo pipefail
cd "$(dirname "$0")"

UI="${AT_UI_LANG:-${LANG:-en}}"
case "${UI:0:2}" in ru) UI=ru ;; *) UI=en ;; esac
say_() { if [ "$UI" = ru ]; then echo "$1" >&2; else echo "${2:-$1}" >&2; fi }
ask_() { if [ "$UI" = ru ]; then printf '%s' "$1" >&2; else printf '%s' "${2:-$1}" >&2; fi }

say() { printf '\n\033[1;36m== %s\033[0m\n' "$1" >&2; }

PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  say_ "Нужен python3. Установите: brew install python" \
       "python3 is required. Install it: brew install python"
  exit 1
fi
if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  say_ "Нужен python 3.10+, сейчас: $($PY -V 2>&1)" \
       "python 3.10+ is required, found: $($PY -V 2>&1)"
  exit 1
fi

ask() { # ask → 0 = yes; no TTY always answers "no" (nothing installs unattended)
  local ans=""
  if [ ! -t 0 ]; then
    say_ "  (терминала нет — автоматически «нет»; запустите скрипт в терминале)" \
         "  (no terminal — automatically \"no\"; run this script in a terminal)"
    return 1
  fi
  ask_ "$1" "${2:-$1}"
  read -r ans || ans=""
  case "$ans" in
    n*|N*|н*|Н*|т*|Т*) return 1 ;;
    *) return 0 ;;
  esac
}

say "ffmpeg"
if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    if ask "ffmpeg не найден — установить через Homebrew (brew install ffmpeg)? [Y/n] " \
           "ffmpeg not found — install it via Homebrew (brew install ffmpeg)? [Y/n] "; then
      brew install ffmpeg
    else
      say_ "Без ffmpeg не работают декодирование аудио и нарезка фрагментов." \
           "Without ffmpeg, audio decoding and fragment cutting cannot work."
      say_ "Установите позже: brew install ffmpeg, затем запустите скрипт снова." \
           "Install it later: brew install ffmpeg, then run this script again."
      exit 1
    fi
  else
    say_ "ffmpeg не найден, а Homebrew нет." "ffmpeg not found and Homebrew is missing."
    say_ "Установите ffmpeg (https://ffmpeg.org/download.html или brew install ffmpeg)" \
         "Install ffmpeg (https://ffmpeg.org/download.html or brew install ffmpeg)"
    say_ "и запустите скрипт снова." "and run this script again."
    exit 1
  fi
else
  echo "ffmpeg: $(ffmpeg -version 2>/dev/null | head -1)"
fi

say_ "Виртуальное окружение" "Virtual environment"
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
say_ "Зависимости установлены." "Dependencies installed."

say_ "Модель Whisper" "Whisper model"
# Same search order as pipeline.py: $AT_MODEL_DIR → <project>/model → ~/whisper-model
if [ -n "${AT_MODEL_DIR:-}" ]; then
  MODEL_DIR="$AT_MODEL_DIR"
elif [ -f "model/model.bin" ]; then
  MODEL_DIR="model"
else
  MODEL_DIR="$HOME/whisper-model"
fi
if [ -f "$MODEL_DIR/model.bin" ]; then
  say_ "Модель уже на месте: $MODEL_DIR" "Model already in place: $MODEL_DIR"
else
  say_ "Модель не найдена (проверены AT_MODEL_DIR, <проект>/model, ~/whisper-model)." \
       "Model not found (checked AT_MODEL_DIR, <project>/model, ~/whisper-model)."
  if ask "Скачать Whisper large-v3-turbo (~1.5 ГБ, Hugging Face) в $MODEL_DIR? [Y/n] " \
         "Download Whisper large-v3-turbo (~1.5 GB, Hugging Face) to $MODEL_DIR? [Y/n] "; then
    mkdir -p "$MODEL_DIR"
    .venv/bin/python - "$MODEL_DIR" <<'EOF'
import sys
from huggingface_hub import snapshot_download
path = snapshot_download("deepdml/faster-whisper-large-v3-turbo-ct2",
                         local_dir=sys.argv[1])
print("Model downloaded:", path)
EOF
  else
    say_ "Пропускаю. Скачайте модель позже и положите model.bin в $MODEL_DIR" \
         "Skipping. Download the model later and put model.bin into $MODEL_DIR"
    say_ "(или задайте AT_MODEL_DIR). Без модели работает всё, кроме транскрибации." \
         "(or set AT_MODEL_DIR). Everything except transcription works without it."
  fi
fi

if [ "${1:-}" = "--app" ]; then
  say_ "Сборка Transcriber.app" "Building Transcriber.app"
  if ! command -v swiftc >/dev/null 2>&1; then
    say_ "Для --app нужен swiftc (Xcode Command Line Tools): xcode-select --install" \
         "--app requires swiftc (Xcode Command Line Tools): xcode-select --install"
    exit 1
  fi
  ./app-sources/build_app.sh
  say_ "Готово: build/Transcriber.app" "Done: build/Transcriber.app"
  say_ "Для установки: cp -R build/Transcriber.app /Applications/" \
       "To install: cp -R build/Transcriber.app /Applications/"
  say_ "Первый запуск: правый клик по приложению → «Открыть» (ad-hoc подпись)." \
       "First launch: right-click the app → \"Open\" (ad-hoc signature)."
fi

say_ "Проверка" "Verification"
.venv/bin/python -c "import faster_whisper, reportlab, pptx, av; print('python deps OK')"
command -v ffmpeg >/dev/null 2>&1 && echo "ffmpeg OK"
[ -f "$MODEL_DIR/model.bin" ] && say_ "модель OK: $MODEL_DIR" "model OK: $MODEL_DIR"
echo
say_ "Дальше: .venv/bin/python pipeline.py запись.m4a --formats pdf,pptx,html" \
     "Next: .venv/bin/python pipeline.py recording.m4a --formats pdf,pptx,html"
