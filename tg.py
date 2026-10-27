"""Связь с Telegram: проверка входа из мини-приложения и отправка сообщений ботами."""
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

import httpx

from .config import BOT_TOKEN, MANAGER_CHAT_IDS, PUBLIC_URL, TEAM_BOT_TOKEN

log = logging.getLogger("tg")


def check_init_data(init_data: str, max_age=86400):
    """Проверяет подпись initData, которую Telegram передает мини-приложению.
    Возвращает данные пользователя или None, если подпись неверна."""
    if not init_data or not BOT_TOKEN:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        return None
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return None
    if time.time() - int(pairs.get("auth_date", "0")) > max_age:
        return None
    try:
        return json.loads(pairs.get("user", "{}"))
    except ValueError:
        return None


async def _call(token, method, payload):
    if not token:
        log.info("нет токена, пропускаю %s: %s", method, payload.get("text", "")[:80])
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
            data = r.json()
            if not data.get("ok"):
                log.warning("Telegram %s: %s", method, data)
            return data
    except Exception as e:  # сеть не должна ронять сервер
        log.warning("Telegram %s: %s", method, e)
        return None


def app_button(text="Открыть клуб", path=""):
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": f"{PUBLIC_URL}/{path}"}}]]}


async def send(chat_id, text, button=None, token=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if button:
        payload["reply_markup"] = button
    return await _call(token or BOT_TOKEN, "sendMessage", payload)


async def notify_team(text):
    """Сообщение менеджерам от team-бота."""
    from . import db
    con = db.connect()
    try:
        chats = set(MANAGER_CHAT_IDS) | set(db.team_ids(con))
    finally:
        con.close()
    for chat in chats:
        await send(chat, text, token=TEAM_BOT_TOKEN or BOT_TOKEN)


async def set_webhook(url, secret):
    return await _call(BOT_TOKEN, "setWebhook", {"url": url, "secret_token": secret,
                                                  "allowed_updates": ["message", "callback_query"]})


async def set_menu_button():
    return await _call(BOT_TOKEN, "setChatMenuButton", {
        "menu_button": {"type": "web_app", "text": "Клуб", "web_app": {"url": f"{PUBLIC_URL}/"}}})
