# Единение: приложение клуба

Один сервер, одна база. К ней подключены мини-приложение для участников, кабинет команды, бот и оплаты Tribute.

- `app/` — сервер (FastAPI, база SQLite в `data/club.db`)
- `static/index.html`, `app.js`, `app.css` — мини-приложение в Telegram
- `static/admin.html` — кабинет: баллы, участники, эфиры, библиотека, оплаты
- `install.sh` — установка на чистый Ubuntu 24.04 одной командой
- `update.sh` — обновление кода без потери данных

Адреса после установки:
- приложение: `https://app.edinenie-club.com`
- кабинет: `https://app.edinenie-club.com/admin`
- вебхук Tribute: `https://app.edinenie-club.com/tribute/webhook`

Копия базы делается каждый день в 4:00 в `/opt/edinenie/backups`, хранится 30 дней.
