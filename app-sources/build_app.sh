#!/bin/zsh
# Сборка Transcriber.app: swiftc + иконка + бандл + подпись.
# Запуск из корня проекта: ./app-sources/build_app.sh
set -euo pipefail
cd "$(dirname "$0")/.."

APP=build/Transcriber.app
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# universal-бинарник (arm64 + x86_64), deployment target macOS 12.0 —
# совпадает с LSMinimumSystemVersion в Info.plist
swiftc -O -target arm64-apple-macos12.0 app-sources/main.swift -o build/Transcriber-arm64
swiftc -O -target x86_64-apple-macos12.0 app-sources/main.swift -o build/Transcriber-x86_64
lipo -create build/Transcriber-arm64 build/Transcriber-x86_64 -o "$APP/Contents/MacOS/Transcriber"
lipo -info "$APP/Contents/MacOS/Transcriber"
cp app-sources/Info.plist "$APP/Contents/Info.plist"
cp -R app-sources/en.lproj app-sources/ru.lproj "$APP/Contents/Resources/"

# иконка: генерируем, если исходного PNG нет, затем icns
if [[ ! -f app-sources/AppIcon_1024.png ]]; then
  .venv/bin/python app-sources/make_icon.py
fi
mkdir -p build/AppIcon.iconset
.venv/bin/python - <<'EOF'
import sys
sys.path.insert(0, "app-sources")
from make_icon import make_iconset
make_iconset("app-sources/AppIcon_1024.png", "build/AppIcon.iconset")
EOF
iconutil -c icns build/AppIcon.iconset -o build/AppIcon.icns
cp build/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"

codesign --force -s - "$APP"
echo "OK: $APP"
