#!/usr/bin/env bash
# Автовыкладка: если на GitHub (ветка main) появилась новая версия, делает копию базы и кода,
# запускает update.sh и проверяет, что приложение отвечает. Если нет, возвращает прошлую версию.
# Запуск раз в минуту через systemd-таймер (ставится командой install-auto-update.sh).
# Проверка без выкладки: bash auto-update.sh --check
set -uo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
APP_DIR=/opt/edinenie
BACKUPS="$APP_DIR/backups"
BRANCH="${BRANCH:-main}"
LOG=/var/log/edinenie-auto-update.log
FAILED_FILE="$APP_DIR/data/.auto-update-failed"   # коммит, который не взлетел: пока на GitHub нет нового, его не повторяем

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG" >&2; }

exec 9>/var/lock/edinenie-auto-update.lock
flock -n 9 || exit 0   # уже идет другой запуск

cd "$SRC" || exit 1
git fetch -q origin "$BRANCH" 2>>"$LOG" || { log "не удалось связаться с GitHub"; exit 0; }
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"
[ "$LOCAL" = "$REMOTE" ] && exit 0
if [ -f "$FAILED_FILE" ] && [ "$(cat "$FAILED_FILE")" = "$REMOTE" ]; then exit 0; fi

if [ "${1:-}" = "--check" ]; then
  echo "Есть новая версия: ${LOCAL:0:7} -> ${REMOTE:0:7}. Выкладка запустится сама в течение минуты."
  git log --oneline "$LOCAL..$REMOTE" | head -20
  exit 0
fi

log "новая версия ${REMOTE:0:7}, выкладываю"
mkdir -p "$BACKUPS"
STAMP="$(date +%Y%m%d-%H%M%S)"

# 1. копия базы (sqlite3 .backup безопасна при работающем приложении; если его нет, обычное копирование)
DB="$APP_DIR/data/club.db"
if [ -f "$DB" ]; then
  if command -v sqlite3 >/dev/null 2>&1; then sqlite3 "$DB" ".backup '$BACKUPS/auto-$STAMP.db'"; else cp "$DB" "$BACKUPS/auto-$STAMP.db"; fi
fi
# 2. копия текущего кода для отката
tar -czf "$BACKUPS/code-$STAMP.tar.gz" -C "$APP_DIR" app static 2>>"$LOG"
# хранить последние 20 копий
ls -1t "$BACKUPS"/auto-*.db 2>/dev/null | tail -n +21 | xargs -r rm -f
ls -1t "$BACKUPS"/code-*.tar.gz 2>/dev/null | tail -n +21 | xargs -r rm -f

# 3. выкладка
bash "$SRC/update.sh" >>"$LOG" 2>&1

# 4. проверка: до 30 секунд ждем ответ /health
ok=0
for _ in $(seq 1 15); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null; then ok=1; break; fi
  sleep 2
done

if [ "$ok" = 1 ]; then
  rm -f "$FAILED_FILE"
  log "готово: ${REMOTE:0:7}"
  exit 0
fi

# 5. откат
log "приложение не отвечает после ${REMOTE:0:7}, возвращаю прошлую версию"
tar -xzf "$BACKUPS/code-$STAMP.tar.gz" -C "$APP_DIR" 2>>"$LOG"
chown -R edinenie:edinenie "$APP_DIR/app" "$APP_DIR/static" 2>>"$LOG"
systemctl restart edinenie
echo "$REMOTE" > "$FAILED_FILE"
sleep 3
if curl -sf http://127.0.0.1:8000/health >/dev/null; then log "откат выполнен, приложение работает на прошлой версии. Версия ${REMOTE:0:7} пропущена до следующих изменений"; else log "ВНИМАНИЕ: после отката приложение тоже не отвечает: journalctl -u edinenie -n 50"; fi
exit 0
