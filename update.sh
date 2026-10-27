#!/usr/bin/env bash
# Обновление: подтянуть новую версию кода с GitHub и перезапустить. Данные и настройки не трогаются.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
APP_DIR=/opt/edinenie
cd "$SRC" && git pull --ff-only
place() { local src="$1"
  for f in "$src"/*.py; do [ -e "$f" ] && cp "$f" "$APP_DIR/app/"; done
  for f in "$src"/*.html "$src"/*.js "$src"/*.css; do [ -e "$f" ] && cp "$f" "$APP_DIR/static/"; done; return 0; }
place "$SRC"; [ -d "$SRC/app" ] && place "$SRC/app"; [ -d "$SRC/static" ] && place "$SRC/static"
cp "$SRC/requirements.txt" "$APP_DIR/"
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
chown -R edinenie:edinenie "$APP_DIR"
systemctl restart edinenie
sleep 2 && curl -sf http://127.0.0.1:8000/health >/dev/null && echo "Обновлено, сервер работает." || echo "Сервер не отвечает: journalctl -u edinenie -n 50"
