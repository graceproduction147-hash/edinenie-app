#!/usr/bin/env bash
# Один раз на сервере: включает автовыкладку (проверка GitHub раз в минуту). Выключить: bash install-auto-update.sh off
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
if [ "${1:-}" = "off" ]; then
  systemctl disable --now edinenie-auto-update.timer 2>/dev/null || true
  echo "Автовыкладка выключена."; exit 0
fi
chmod +x "$SRC/auto-update.sh"
cat > /etc/systemd/system/edinenie-auto-update.service <<EOF
[Unit]
Description=Edinenie auto update from GitHub
[Service]
Type=oneshot
ExecStart=/bin/bash $SRC/auto-update.sh
EOF
cat > /etc/systemd/system/edinenie-auto-update.timer <<EOF
[Unit]
Description=Edinenie auto update every minute
[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
AccuracySec=10s
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now edinenie-auto-update.timer
echo "Автовыкладка включена. Журнал: /var/log/edinenie-auto-update.log"
