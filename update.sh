#!/usr/bin/env bash
# Обновление: подтянуть новую версию кода и перезапустить. Данные и настройки не трогаются.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
cd "$SRC" && git pull --ff-only
cp -r "$SRC"/app "$SRC"/static "$SRC"/requirements.txt /opt/edinenie/
/opt/edinenie/venv/bin/pip install -q -r /opt/edinenie/requirements.txt
chown -R edinenie:edinenie /opt/edinenie
systemctl restart edinenie
sleep 2 && curl -sf http://127.0.0.1:8000/health >/dev/null && echo "Обновлено, сервер работает." || echo "Сервер не отвечает: journalctl -u edinenie -n 50"
