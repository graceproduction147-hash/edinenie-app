"""Настройки берутся из файла .env рядом с приложением (см. .env.example)."""
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def _load_env():
    env = BASE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def env(name, default=""):
    return os.environ.get(name, default)


BOT_TOKEN = env("BOT_TOKEN")                 # @edinenie_club_bot
TEAM_BOT_TOKEN = env("TEAM_BOT_TOKEN")       # @edinenie_team1_bot, уведомления команде
MANAGER_CHAT_IDS = [int(x) for x in env("MANAGER_CHAT_IDS").replace(" ", "").split(",") if x]
ADMIN_IDS = [int(x) for x in env("ADMIN_IDS").replace(" ", "").split(",") if x]
ADMIN_PASSWORD = env("ADMIN_PASSWORD")       # вход в кабинет
PUBLIC_URL = env("PUBLIC_URL", "https://app.edinenie-club.com").rstrip("/")
JOIN_URL = env("JOIN_URL", "https://edinenie-club.com")
WEBHOOK_SECRET = env("WEBHOOK_SECRET", "change-me")
TRIBUTE_API_KEY = env("TRIBUTE_API_KEY")
# period_id из Tribute -> число месяцев, например {"123":1,"124":3}
PERIOD_MAP = json.loads(env("PERIOD_MAP", "{}") or "{}")
# сколько месяцев оплаты дает Inside (на сайте Inside — годовой формат)
INSIDE_MONTHS = int(env("INSIDE_MONTHS", "12"))
DB_PATH = Path(env("DB_PATH", str(BASE / "data" / "club.db")))
UPLOADS = Path(env("UPLOADS", str(BASE / "data" / "uploads")))
DEV_MODE = env("DEV_MODE", "0") == "1"       # только для локальной проверки
TZ = "Europe/Moscow"
