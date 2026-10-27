#!/usr/bin/env bash
# Установка сервера клуба Единение на чистый Ubuntu 24.04.
# Запуск: bash install.sh   (из папки с кодом, от root)
set -euo pipefail

APP_DIR=/opt/edinenie
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

say() { printf "\n\033[1;35m▸ %s\033[0m\n" "$1"; }
ask() { local q="$1" def="${2:-}" v; read -r -p "$q${def:+ [$def]}: " v </dev/tty; echo "${v:-$def}"; }
ask_secret() { local v; read -r -s -p "$1: " v </dev/tty; echo >&2; echo "$v"; }

[ "$(id -u)" = 0 ] || { echo "Запустите от root"; exit 1; }

say "Ставлю системные пакеты"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip caddy sqlite3 curl ufw

say "Копирую приложение в $APP_DIR"
mkdir -p "$APP_DIR"
if [ "$SRC_DIR" != "$APP_DIR" ]; then cp -r "$SRC_DIR"/. "$APP_DIR"/; fi
id -u edinenie >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin edinenie
mkdir -p "$APP_DIR/data/uploads" "$APP_DIR/backups"

say "Ставлю Python-зависимости"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
  say "Настройка. Значения можно поменять позже в файле $APP_DIR/.env"
  DOMAIN=$(ask "Адрес приложения" "app.edinenie-club.com")
  BOT_TOKEN=$(ask_secret "Токен @edinenie_club_bot из BotFather")
  TEAM_BOT_TOKEN=$(ask_secret "Токен @edinenie_team1_bot (Enter, чтобы пропустить)")
  ADMIN_IDS=$(ask "Ваш Telegram ID (несколько через запятую)")
  MANAGER_CHAT_IDS=$(ask "Telegram ID тех, кому слать уведомления" "$ADMIN_IDS")
  ADMIN_PASSWORD=$(ask_secret "Придумайте пароль для кабинета")
  TRIBUTE_API_KEY=$(ask_secret "API-ключ Tribute (Enter, чтобы пропустить)")
  WEBHOOK_SECRET=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)
  cat > "$APP_DIR/.env" <<EOF
PUBLIC_URL=https://$DOMAIN
JOIN_URL=https://edinenie-club.com
BOT_TOKEN=$BOT_TOKEN
TEAM_BOT_TOKEN=$TEAM_BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
MANAGER_CHAT_IDS=$MANAGER_CHAT_IDS
ADMIN_PASSWORD=$ADMIN_PASSWORD
TRIBUTE_API_KEY=$TRIBUTE_API_KEY
WEBHOOK_SECRET=$WEBHOOK_SECRET
PERIOD_MAP={}
INSIDE_MONTHS=12
EOF
fi
chmod 600 "$APP_DIR/.env"
chown -R edinenie:edinenie "$APP_DIR"
DOMAIN=$(grep ^PUBLIC_URL "$APP_DIR/.env" | sed 's#PUBLIC_URL=https://##')

say "Запускаю сервер как службу"
cat > /etc/systemd/system/edinenie.service <<EOF
[Unit]
Description=Edinenie club app
After=network.target

[Service]
User=edinenie
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now edinenie
systemctl restart edinenie

say "Настраиваю HTTPS для $DOMAIN"
cat > /etc/caddy/Caddyfile <<EOF
$DOMAIN {
    encode gzip
    reverse_proxy 127.0.0.1:8000
}
EOF
systemctl reload caddy || systemctl restart caddy

say "Открываю порты"
ufw allow OpenSSH >/dev/null; ufw allow 80 >/dev/null; ufw allow 443 >/dev/null; ufw --force enable >/dev/null

say "Ежедневная копия базы в 4:00"
cat > /etc/cron.d/edinenie-backup <<EOF
0 4 * * * edinenie sqlite3 $APP_DIR/data/club.db ".backup '$APP_DIR/backups/club-\$(date +\%F).db'" && find $APP_DIR/backups -name 'club-*.db' -mtime +30 -delete
EOF

say "Подключаю бота к серверу"
sleep 3
getenv() { grep "^$1=" "$APP_DIR/.env" | head -1 | cut -d= -f2-; }
BOT_TOKEN=$(getenv BOT_TOKEN); WEBHOOK_SECRET=$(getenv WEBHOOK_SECRET)
curl -s "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" \
  -d "url=https://$DOMAIN/tg/webhook" -d "secret_token=$WEBHOOK_SECRET" -d 'allowed_updates=["message"]'; echo
curl -s "https://api.telegram.org/bot$BOT_TOKEN/setChatMenuButton" -H 'Content-Type: application/json' \
  -d "{\"menu_button\":{\"type\":\"web_app\",\"text\":\"Клуб\",\"web_app\":{\"url\":\"https://$DOMAIN/\"}}}"; echo

say "Проверка"
if curl -sf "http://127.0.0.1:8000/health" >/dev/null; then echo "Сервер работает."; else echo "Сервер не отвечает: journalctl -u edinenie -n 50"; fi
cat <<EOF

Готово.
  Приложение:  https://$DOMAIN
  Кабинет:     https://$DOMAIN/admin
  Вебхук для Tribute: https://$DOMAIN/tribute/webhook
EOF
