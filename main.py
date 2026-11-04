"""Сервер клуба Единение: мини-приложение, кабинет, бот и оплаты Tribute в одном месте."""
import asyncio
import base64
import hashlib
import hmac
import html
import json
import logging
import os
import re
import secrets
import urllib.request
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import card, coffee, db, tg
from .config import (ADMIN_IDS, ADMIN_PASSWORD, BASE, DEV_MODE, INSIDE_MONTHS, JOIN_URL, PERIOD_MAP,
                     PUBLIC_URL, TRIBUTE_API_KEY, UPLOADS, WEBHOOK_SECRET)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("club")


# Тексты бота. Их можно менять в кабинете (вкладка «Тексты бота»), в коде править не нужно.
# **жирный**, {name} вставит имя, {link} вставит ссылку на вступление. Эмодзи вставляйте прямо в текст.
TEXTS = {
    "welcome": {"title": "Приветствие после оплаты", "max": 1000, "hint": "Приходит сразу после оплаты. Если задана картинка, этот текст идет под ней.",
                "default": "**{name}, добрый день! Добро пожаловать в «Единение»!** ❤️\n\nБлагодарим вас, что вы с нами. Мы очень рады, что вы теперь часть Клуба — сообщества людей, которых объединяют развитие, сильное окружение и желание создавать большее вместе.\n\nВсего два шага, чтобы начать:\n\n. **Шаг 1. Заполните анкету.** Расскажите немного о себе, своих интересах и намерениях. Так нам будет проще познакомить вас с нужными людьми.\n\n. **Шаг 2. Откройте Клуб.** Заходите в наше пространство, знакомьтесь с участниками и присоединяйтесь к событиям.\n\nМы рядом, если появятся вопросы ❤️"},
    "member_start": {"title": "Участнику, когда он нажимает Start", "max": 3000, "hint": "",
                     "default": "**{name}, добрый день!** ❤️\n\nРады видеть вас в Клубе. Свои люди и ваши результаты ждут внутри."},
    "guest_start": {"title": "Тому, кто еще не оплатил", "max": 3000, "hint": "{link} вставит ссылку на вступление.",
                    "default": "**Единение**\n\nОкружение, которое двигает вперед.\n\nПриложение откроется, как только пройдет оплата участия. Будем рады видеть вас в Клубе.\n\nВступить: {link}"},
    "anketa": {"title": "Команда /anketa", "max": 3000, "hint": "",
               "default": "**Анкета участника**\n\nДесять минут о себе — и Клуб сможет знакомить вас с теми людьми, с которыми действительно интересно. Профиль в Клубе заполнится из анкеты сам.\n\nБлагодарим вас за время."},
    "monthly": {"title": "Команда /monthly", "max": 3000, "hint": "",
                "default": "**Итоги месяца**\n\nПара минут, чтобы увидеть, что сдвинулось, и выбрать, куда идти дальше. Нам очень важно знать, как у вас дела."},
    "btn_form": {"title": "Кнопка анкеты", "max": 60, "plain": True, "hint": "", "default": "Заполнить анкету"},
    "btn_club": {"title": "Кнопка клуба", "max": 60, "plain": True, "hint": "", "default": "Открыть Клуб"},
    "btn_monthly": {"title": "Кнопка итогов месяца", "max": 60, "plain": True, "hint": "", "default": "Заполнить итоги"},
    "bot_about": {"title": "Описание бота (в пустом чате до Start)", "max": 512, "plain": True, "hint": "Только текст, без жирного. Обновляется в Telegram после сохранения.",
                  "default": "Единение — Клуб, где окружение работает на ваш рост.\n\nЗдесь можно найти своих людей, знакомиться по запросу, а не наугад, и каждый месяц видеть, что сдвинулось: в деньгах, смыслах, знакомствах, возможностях, практиках и впечатлениях.\n\nНажмите «Старт». Если вы уже в Клубе, он откроется сразу."},
    "bot_short": {"title": "Подпись под именем бота", "max": 120, "plain": True, "hint": "Короткая строка, до 120 знаков. Обновляется в Telegram после сохранения.",
                  "default": "Окружение, которое двигает вперед: свои люди, живые встречи и результаты."},
    "card_ask_name": {"title": "Вопрос: как подписать карточку месяца", "group": "members", "max": 700, "vars": "", "hint": "Приходит один раз, когда у человека еще нет имени для карточки. Ответ человека сохраняется как подпись на картинке.",
                      "default": "**Ваша карточка месяца почти готова**\n\nКак ее подписать? Напишите имя и фамилию так, как хотите видеть на картинке."},
    "card_ready": {"title": "Подпись к карточке месяца", "group": "members", "max": 700, "vars": "", "hint": "Приходит вместе с картинкой.",
                   "default": "**Ваша карточка месяца**\n\nМожно выкладывать в Stories и отмечать клуб. Изменить подпись: команда /cardname."},
    "card_wait": {"title": "Карточка пока недоступна", "group": "members", "max": 700, "vars": "", "hint": "Если человек просит карточку, а итоги месяца еще не заполнены.",
                  "default": "Карточка появится сразу после итогов месяца. Заполнить их можно командой /monthly."},
    # ---- участникам ----
    "inside_on": {"title": "Inside получен", "group": "members", "max": 1000, "vars": "{days} (сколько дней действует)", "hint": "Когда участник закрыл норму месяца.",
                  "default": "**{name}, поздравляем, вы в Inside!**\n\nБлагодарим вас за вклад в Клуб. Вы закрыли норму месяца, и теперь вам открыты закрытые эфиры, записи и материалы. Статус действует еще {days} дн.\n\nРады за ваше проявление."},
    "inside_off": {"title": "Inside на паузе", "group": "members", "max": 1000, "vars": "", "hint": "Когда норма месяца не закрыта.",
                   "default": "Inside пока на паузе: норма месяца еще не закрыта.\n\nЧтобы вернуть его, можно пригласить друга, провести встречу Random Coffee или рассказать о Клубе и своих результатах. Мы будем рады вам."},
    "points_ok": {"title": "Баллы подтверждены", "group": "members", "max": 1000, "vars": "{points}", "hint": "Когда команда подтвердила заявку на баллы.",
                  "default": "Команда Клуба подтвердила +{points} баллов.\n\nБлагодарим вас за вклад и рады за ваше проявление."},
    "recap_record": {"title": "Запись эфира готова", "group": "members", "max": 1000, "vars": "{title} (название эфира), {points}", "hint": "Приходит, когда в кабинете появилась ссылка на запись.",
                     "default": "Запись эфира «{title}» готова.\n\nПосмотрите, когда будет время, и нажмите «Смотрел». А главную мысль напишите в чате Клуба с хештегом #инсайт: бот ее зафиксирует, команда подтвердит, и придет +{points} баллов.\n\nНам очень важно узнать, что откликнулось."},
    "recap_nudge": {"title": "Напоминание про запись (через 48 часов)", "group": "members", "max": 1000, "vars": "{title}, {points}", "hint": "Только тем, кто не нажал «Смотрел».",
                    "default": "Добрый день! Напоминаем про запись эфира «{title}»\n\nЕсли уже смотрели, нажмите «Смотрел» и напишите свой инсайт в чат с хештегом #инсайт: придет +{points} баллов.\n\nБудем рады услышать, что вам откликнулось."},
    "recap_closed": {"title": "Запись закрытого эфира, не Inside", "group": "members", "max": 1000, "vars": "{title}", "hint": "Тем, у кого нет Inside. Приходит один раз.",
                     "default": "Вышла запись закрытого эфира «{title}»\n\nОна доступна на уровне Inside. Inside открывается за вклад в Клуб: за месяц привести друга, провести встречу Random Coffee и рассказать о Клубе или о своих результатах. Как это сделать, смотрите в профиле приложения.\n\nБудем рады видеть вас внутри."},
    "insight_ok": {"title": "Инсайт записан", "group": "members", "max": 1000, "vars": "{points}", "hint": "Участник написал #инсайт в чате клуба.",
                   "default": "**Записали ваш инсайт**\n\nЗа него назначено **{points} баллов**. Инсайт передан менеджеру Клуба: если все в порядке, мы начислим вам {points} баллов.\n\nБлагодарим вас за включенность и рады за ваше проявление."},
    "insight_dup": {"title": "Инсайт по эфиру уже был", "group": "members", "max": 1000, "vars": "", "hint": "Второй инсайт по тому же эфиру.",
                    "default": "Инсайт по этому эфиру уже записан.\n\nОдного на эфир достаточно: баллы начисляются за него один раз. Благодарим вас."},
    "match": {"title": "Взаимный интерес в Знакомствах", "group": "members", "max": 1000, "vars": "{peer} (имя), {nick} (например @ivan или пусто)", "hint": "Обоим, когда они отметили друг друга.",
              "default": ". **Это взаимно!**\n\nВы и **{peer}** отметили друг друга в Знакомствах. Мы рады за вас! {nick}\n\nНапишите друг другу — пусть это будет началом хорошей истории."},
    "offer_live": {"title": "Предложение опубликовано", "group": "members", "max": 1000, "vars": "{title}", "hint": "Автору, когда команда одобрила предложение.",
                   "default": "Ваше предложение «{title}» опубликовано в разделе «События», вкладка «Предложения», на 30 дней.\n\nКогда придет заявка, мы сразу напишем вам здесь. Благодарим вас, что делитесь своим."},
    "offer_request": {"title": "Заявка на ваше предложение", "group": "members", "max": 1000, "vars": "{title}, {who} (имя и ссылка), {what} (хочет купить или предлагает бартер), {message} (текст человека)", "hint": "Автору предложения.",
                      "default": ". Добрый день! По вашему предложению «{title}» есть отклик: {who} {what}.\n\n{message}\n\nНапишите человеку в Telegram и договоритесь напрямую. Рады, что в Клубе происходит такое."},
    "coffee_pair": {"title": "Random Coffee: пара на неделю", "group": "members", "max": 1000, "vars": "{pair} (имя и ник), {reason} (почему вы подходите)", "hint": "Каждому из пары, по понедельникам.",
                    "default": ". **Random Coffee на эту неделю**\n\nВаша пара: **{pair}**\n\n{reason}\n\nДоговоритесь о созвоне на 30 минут. В пятницу мы спросим, как прошло. Хорошей встречи."},
    "coffee_none": {"title": "Random Coffee: не хватило пары", "group": "members", "max": 1000, "vars": "", "hint": "Тому, кто остался без пары.",
                    "default": "На этой неделе пары не нашлось.\n\nВы остаетесь в очереди на следующую неделю. Благодарим вас за терпение."},
    "coffee_ask": {"title": "Random Coffee: как прошла встреча", "group": "members", "max": 1000, "vars": "", "hint": "По пятницам, тем, кто еще не ответил.",
                   "default": "Добрый день! Как прошла встреча Random Coffee?\n\nРасскажите в двух словах, что получилось. Нам очень важно знать, а за отзыв начисляются баллы."},
    "event_day": {"title": "Напоминание об эфире за сутки", "group": "members", "max": 1000, "vars": "{title}, {link} (строка с ссылкой или пусто)", "hint": "Записавшимся на эфир.",
                  "default": "Добрый день! Завтра эфир Клуба: **{title}**{link}\n\nБудем рады вас видеть."},
    "event_hour": {"title": "Напоминание об эфире за час", "group": "members", "max": 1000, "vars": "{title}, {link}", "hint": "Записавшимся на эфир.",
                   "default": "Через час эфир Клуба: **{title}**{link}\n\nЖдем вас, будет живо."},
    "r_anketa_1": {"title": "Напоминание про анкету: 1-й день", "group": "reminders", "max": 1000, "vars": "{name}", "hint": "Через сутки после оплаты, если анкета не заполнена.",
                   "default": "{name}, добрый день!\n\nРады, что вы в Клубе. Заполните, пожалуйста, анкету: десять минут — и мы сможем знакомить вас с нужными людьми."},
    "r_anketa_3": {"title": "Напоминание про анкету: 3-й день", "group": "reminders", "max": 1000, "vars": "{name}", "hint": "На третий день, если анкета все еще не заполнена.",
                   "default": "{name}, добрый день!\n\nБез анкеты нам сложно понять, с кем вас познакомить. Это займет десять минут, а профиль заполнится сам. Будем благодарны."},
    "r_anketa_7": {"title": "Напоминание про анкету: 7-й день", "group": "reminders", "max": 1000, "vars": "{name}", "hint": "На седьмой день, последнее напоминание.",
                   "default": "{name}, добрый день!\n\nУже неделя в Клубе, а анкеты пока нет. Если что-то мешает, просто напишите нам, мы поможем."},
    "r_renew_7": {"title": "Продление: за 7 дней", "group": "reminders", "max": 1000, "vars": "{name}, {date} (до какого числа оплачено), {link}", "hint": "За неделю до конца оплаты.",
                  "default": "{name}, добрый день!\n\nВаше участие в Клубе оплачено до {date}. Если подписка продлевается автоматически, ничего делать не нужно. Если нет, продлить можно по ссылке: {link}\n\nБлагодарим вас, что вы с нами."},
    "r_renew_1": {"title": "Продление: за 1 день", "group": "reminders", "max": 1000, "vars": "{name}, {date}, {link}", "hint": "За сутки до конца оплаты.",
                  "default": "{name}, добрый день!\n\nЗавтра ({date}) заканчивается оплата участия в Клубе. Чтобы остаться с нами, продлите, пожалуйста, по ссылке: {link}\n\nБудем очень рады, если вы продолжите путь вместе с нами."},
    "r_quiet": {"title": "Давно не заходили", "group": "reminders", "max": 1000, "vars": "{name}", "hint": "Если участник не открывал приложение 21 день. Не чаще раза в 30 дней.",
                "default": "{name}, добрый день!\n\nДавно не слышали вас, и нам вас не хватает. Загляните в Клуб: на неделе есть эфир, а в Random Coffee вас ждет новая пара. Как вы?"},
    # ---- команде ----
    "t_stats": {"title": "Недельная сводка для собственника", "group": "team", "max": 1500, "vars": "{period}, {items} (цифры собираются сами)", "route0": "none",
                "hint": "По понедельникам. По умолчанию не приходит никому: выберите получателя ниже.",
                "default": "📊 **Сводка клуба за неделю ({period})**\n\n{items}"},
    "t_pay_new": {"title": "Новая оплата", "group": "team", "max": 2000, "vars": "{who}, {id}, {level}, {months}, {amount}, {name}", "hint": "Команде, сразу после первой оплаты.",
                  "default": "💳 Новая оплата: {who} (id {id})\n{level}-level, {months} мес., {amount} ₽\n\nПриветствие для отправки:\n«{name}, добро пожаловать в Единение! Я ваш менеджер. Расскажите, с каким запросом пришли в клуб, и я помогу найти своих людей.»"},
    "t_pay_renew": {"title": "Продление", "group": "team", "max": 1000, "vars": "{who}, {id}, {months}, {amount}, {until}", "hint": "Команде.",
                    "default": "🔁 Продление: {who} (id {id}), {months} мес., {amount} ₽. Доступ продлен до {until}."},
    "t_donation": {"title": "Донат", "group": "team", "max": 1000, "vars": "{event}, {id}, {amount}", "hint": "Команде.",
                   "default": "Донат через Tribute ({event}): id {id}, {amount} ₽. Доступ в клуб не выдан."},
    "t_cancel": {"title": "Отмена подписки", "group": "team", "max": 1000, "vars": "{id}", "hint": "Команде.",
                 "default": "Отмена подписки: id {id}. Доступ сохранится до конца оплаченного периода."},
    "t_badsign": {"title": "Оплата с неверной подписью", "group": "team", "max": 1000, "vars": "", "hint": "Команде.",
                  "default": "Пришла оплата Tribute с неверной подписью. Проверьте в кабинете, раздел «Оплаты»."},
    "t_birthday": {"title": "День рождения участника, сегодня", "group": "team", "max": 1000, "vars": "{who}, {age} (возраст или пусто), {wish} (готовое поздравление)", "hint": "Команде, утром в день рождения. Поздравить лично.",
                   "default": "🎂 Сегодня день рождения: **{who}**{age}\n\nПоздравьте лично. Готовый текст:\n\n{wish}"},
    "t_birthday_soon": {"title": "День рождения участника, через 3 дня", "group": "team", "max": 1000, "vars": "{who}, {date}", "hint": "Команде, за 3 дня: время выбрать и отправить подарок.",
                        "default": "🎁 Через 3 дня ({date}) день рождения: **{who}**\n\nВремя придумать подарок и подготовить поздравление."},
    "birthday_wish": {"title": "Поздравление с днем рождения (готовый текст)", "group": "team", "max": 700, "vars": "{name}", "hint": "Подставляется в уведомление команде, чтобы скопировать и отправить лично.",
                      "default": "{name}, с днем рождения! ❤️\n\nРады, что вы с нами в Клубе. Пусть этот год будет ярким, смелым и очень вашим.\n\nМы приготовили для вас небольшой подарок."},
    "t_digest": {"title": "Утренний дайджест", "group": "team", "max": 1500, "vars": "{date}, {items} (список дел, собирается сам)", "hint": "Каждое утро, только если есть что решить. Под ним отдельные заявки на баллы с кнопками.",
                 "default": "☀️ **Дайджест на {date}**\n\n{items}"},
    "t_digest_claim": {"title": "Дайджест: заявка на баллы", "group": "team", "max": 1000, "vars": "{rule}, {points}, {who}, {text}", "hint": "Под ним кнопки «Подтвердить» и «Отклонить».",
                       "default": "Заявка: **{rule}** +{points} от {who}\n\n{text}"},
    "t_notsaved": {"title": "Оплата не записана в таблицу", "group": "team", "max": 1000, "vars": "{id}", "hint": "Команде, если таблица не ответила.",
                   "default": "Оплата принята сервером, но не записана в таблицу (id {id}). Строку можно добавить вручную."},
    "t_form": {"title": "Новая анкета", "group": "team", "max": 1000, "vars": "{kind} (Стартовая или Ежемесячная), {who}, {id}, {tail}", "hint": "Команде.",
               "default": "📝 {kind} анкета: {who}, id {id}{tail}. Смотрите в кабинете, вкладка «Анкеты»."},
    "t_claim": {"title": "Заявка на баллы", "group": "team", "max": 1500, "vars": "{rule}, {points}, {who}, {text}, {link}", "hint": "Команде, когда участник отправил задание из приложения.",
                "default": "Новая заявка на баллы: **{rule}** +{points} от {who}\n\n{text}\n\nПодтвердить в кабинете: {link}"},
    "t_insight": {"title": "Инсайт из чата", "group": "team", "max": 1500, "vars": "{who}, {event} (по эфиру «...» или пусто), {text}", "hint": "Команде, под сообщением кнопки «Подтвердить» и «Отклонить».",
                  "default": "Инсайт от {who}{event}:\n\n{text}"},
    "t_redeem": {"title": "Обмен баллов", "group": "team", "max": 1000, "vars": "{item}, {cost}, {who}", "hint": "Команде.",
                 "default": "Обмен баллов: **{item}** ({cost}) — {who}. Свяжитесь с участником."},
    "t_offer_new": {"title": "Новое предложение на проверку", "group": "team", "max": 1000, "vars": "{title}, {who}", "hint": "Команде.",
                    "default": "🛍 Новое предложение на проверку: «{title}» от {who}. Откройте кабинет, вкладка «Предложения»."},
    "t_offer_req": {"title": "Заявка на предложение", "group": "team", "max": 1000, "vars": "{title}, {who}, {kind} (покупка или бартер)", "hint": "Команде.",
                    "default": "🛍 Заявка на предложение «{title}»: {who}, {kind}."},
    "t_guest": {"title": "Гость на эфир", "group": "team", "max": 1000, "vars": "{who}, {guest}, {event}", "hint": "Команде.",
                "default": "🎟 {who} (годовой тариф) зовет гостя «{guest}» на эфир «{event}»."},
    "t_coffee": {"title": "Random Coffee: итоги", "group": "team", "max": 1000, "vars": "{pairs}, {left}", "hint": "Команде, в понедельник.",
                 "default": "Random Coffee: составлено пар {pairs}, без пары {left}."},
    "t_team_added": {"title": "Новый человек в команде", "group": "team", "max": 1000, "vars": "{who}, {id}", "hint": "Команде.",
                     "default": "В команду клуба добавлен(а) {who} (id {id})."},
    "team_welcome": {"title": "Новому члену команды", "group": "team", "max": 1500, "vars": "", "hint": "Тому, кого только что добавили в команду.",
                     "default": "Вы в команде клуба Единение. Приложение открыто полностью, уведомления об оплатах и заявках на баллы будут приходить от team-бота: нажмите /start в @edinenie_team1_bot."},
    "photo_saved": {"title": "Картинка приветствия сохранена", "group": "team", "max": 1000, "vars": "", "hint": "Менеджеру, который прислал фото боту.",
                    "default": "Картинка сохранена: теперь ее увидит каждый новый участник в приветствии после оплаты. Чтобы заменить, пришлите другое фото."},
}


def text_raw(con, key):
    v = db.get_setting(con, "text:" + key, None)
    return v if v and v.strip() else TEXTS[key]["default"]


def md_html(t):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(t, quote=False), flags=re.S)


def get_text(con, key, name="", link=""):
    """Текст сообщения из настроек (или стандартный): имя и ссылка подставлены, **жирный** превращен в HTML."""
    raw = text_raw(con, key)
    if name:
        raw = raw.replace("{name}", name)
    else:
        raw = re.sub(r"\{name\}[,\s]*(\S)", lambda m: m.group(1).upper(), raw).replace("{name}", "")
    return md_html(raw.replace("{link}", link))


def get_plain(con, key):
    return text_raw(con, key)


class Raw(str):
    """Кусок, который уже безопасен для HTML (ссылка, например): его не экранируем."""


def render(con, key, **v):
    """Текст из «Тексты бота» с подставленными значениями: {title}, {points} и так далее. **жирный** становится HTML."""
    out = md_html(text_raw(con, key))
    for k, val in v.items():
        sv = str(val) if isinstance(val, Raw) else html.escape("" if val is None else str(val), quote=False)
        out = out.replace("{" + k + "}", sv)
    out = re.sub(r"[ \t]+\n", "\n", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


BOTPICS = UPLOADS.parent / "botpics"
PIC_LIMIT = 1024  # длиннее подпись под картинкой Telegram не принимает


def pic_url(con, key):
    n = db.get_setting(con, "pic:" + key, "")
    return f"{PUBLIC_URL}/botpic/{n}" if n and (BOTPICS / n).exists() else ""


def auto_on(con):
    """Общий выключатель автоматических рассылок участникам (по умолчанию выключен, включается в кабинете)."""
    return db.get_setting(con, "auto_on", "0") == "1"


# ---------------- журнал всех сообщений бота ----------------
import contextvars
_CUR_KEY = contextvars.ContextVar("cur_key", default="")
_orig_send = tg.send


def _msg_log(chat_id, text, key, ok, bot):
    try:
        c = db.connect()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS msg_log(id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, bot TEXT, key TEXT, text TEXT, ok INTEGER, created_at TEXT)")
            c.execute("INSERT INTO msg_log(tg_id,bot,key,text,ok,created_at) VALUES(?,?,?,?,?,?)",
                      (chat_id, bot, key or "", (text or "")[:4000], 1 if ok else 0, db.now()))
            c.execute("DELETE FROM msg_log WHERE id < (SELECT MAX(id) FROM msg_log) - 20000")
            c.commit()
        finally:
            c.close()
    except Exception:
        log.exception("журнал сообщений")


async def _logged_send(chat_id, text, button=None, token=None):
    ok = False
    try:
        r = await _orig_send(chat_id, text, button, token=token)
        ok = bool(r) and (not isinstance(r, dict) or r.get("ok", True))
        return r
    finally:
        _msg_log(chat_id, text, _CUR_KEY.get(), ok, "team" if (token and token == tg.TEAM_BOT_TOKEN) else "main")
        _CUR_KEY.set("")


tg.send = _logged_send


async def send_text(chat_id, text, kb=None, key=None, con=None, token=None):
    """Сообщение бота. Если для него в кабинете задана картинка, она идет сверху (подпись до 1024 знаков, длиннее: картинка и текст отдельно)."""
    _CUR_KEY.set(key or "")
    url = ""
    if key:
        c = con or db.connect()
        try:
            url = pic_url(c, key)
        finally:
            if not con:
                c.close()
    if url:
        tok = token or tg.BOT_TOKEN
        try:
            if len(text) <= 1024:
                payload = {"chat_id": chat_id, "photo": url, "caption": text, "parse_mode": "HTML"}
                if kb:
                    payload["reply_markup"] = kb
                r = await tg._call(tok, "sendPhoto", payload)
                if r and r.get("ok"):
                    _msg_log(chat_id, "[картинка] " + text, key, True, "team" if (token and token == tg.TEAM_BOT_TOKEN) else "main")
                    return r
            else:
                log.warning("текст «%s» длиннее 1024 знаков, отправлен без картинки", key)
        except Exception:
            log.exception("не удалось отправить картинку")
    return await tg.send(chat_id, text, kb, token=token)


async def team_notify(text, key=None):
    """Сообщение менеджерам от team-бота (с картинкой, если она задана)."""
    con = db.connect()
    try:
        chats = team_targets(con, key) if key else team_chat_ids(con)
    finally:
        con.close()
    await asyncio.gather(*(send_text(c, text, key=key, token=tg.TEAM_BOT_TOKEN or tg.BOT_TOKEN) for c in chats),
                         return_exceptions=True)


BOT_COMMANDS = [
    {"command": "start", "description": "Войти в клуб"},
    {"command": "anketa", "description": "Анкета участника"},
    {"command": "monthly", "description": "Итоги месяца"},
    {"command": "card", "description": "Карточка месяца"},
]


async def setup_bot(delay=3):
    """Описание, короткая подпись и меню команд бота ставятся при запуске и после правки в кабинете."""
    await asyncio.sleep(delay)
    con = db.connect()
    try:
        about, short = get_plain(con, "bot_about"), get_plain(con, "bot_short")
    finally:
        con.close()
    for method, payload in (("setMyDescription", {"description": about}),
                            ("setMyShortDescription", {"short_description": short}),
                            ("setMyCommands", {"commands": BOT_COMMANDS})):
        try:
            await tg._call(tg.BOT_TOKEN, method, payload)
        except Exception:
            log.exception("не удалось настроить бота: %s", method)


@asynccontextmanager
async def lifespan(app):
    db.init()
    ensure_norm()
    ensure_recap()
    task = asyncio.create_task(coffee.scheduler())
    setup = asyncio.create_task(setup_bot())
    norm = asyncio.create_task(norm_loop())
    recap = asyncio.create_task(recap_loop())
    digest = asyncio.create_task(digest_loop())
    yield
    digest.cancel()
    task.cancel()
    setup.cancel()
    norm.cancel()
    recap.cancel()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


def get_con():
    con = db.connect()
    try:
        yield con
    finally:
        con.close()


# ---------------- участники ----------------

def upsert_member(con, u, **extra):
    tg_id = int(u["id"])
    r = con.execute("SELECT tg_id FROM members WHERE tg_id=?", (tg_id,)).fetchone()
    fields = {"username": u.get("username"), "first_name": u.get("first_name"), "last_name": u.get("last_name"), **extra}
    fields = {k: v for k, v in fields.items() if v is not None}
    if r and not fields:
        return tg_id
    if r:
        sets = ", ".join(f"{k}=?" for k in fields)
        con.execute(f"UPDATE members SET {sets}, updated_at=? WHERE tg_id=?", (*fields.values(), db.now(), tg_id))
    else:
        cols = ", ".join(["tg_id", *fields, "created_at", "updated_at"])
        q = ", ".join("?" * (len(fields) + 3))
        con.execute(f"INSERT INTO members({cols}) VALUES({q})", (tg_id, *fields.values(), db.now(), db.now()))
    con.commit()
    return tg_id


def is_team(m):
    return m["tg_id"] in ADMIN_IDS or (m.get("role") or "") == "team"


def refresh_status(con, m):
    """Подписка закончилась — статус expired. Команда клуба всегда активна."""
    if is_team(m):
        return "active"
    if m["status"] == "active" and m["paid_until"]:
        try:
            if datetime.fromisoformat(m["paid_until"]) < datetime.now(timezone.utc):
                con.execute("UPDATE members SET status='expired' WHERE tg_id=?", (m["tg_id"],)); con.commit()
                return "expired"
        except ValueError:
            pass
    return m["status"]


def current_user(x_init_data: str = Header(""), x_dev_user: str = Header(""), con=Depends(get_con)):
    u = tg.check_init_data(x_init_data)
    if not u and DEV_MODE and x_dev_user:
        u = {"id": int(x_dev_user), "first_name": "Тест"}
    if not u:
        raise HTTPException(401, "Откройте приложение через бота клуба")
    exists = con.execute("SELECT 1 FROM members WHERE tg_id=?", (int(u["id"]),)).fetchone()
    # имя из Telegram берем только при первом входе, дальше человек правит его в анкете
    tg_id = upsert_member(con, {"id": u["id"], "username": u.get("username")} if exists else u)
    m = db.row(con.execute("SELECT * FROM members WHERE tg_id=?", (tg_id,)).fetchone())
    m["status"] = refresh_status(con, m)
    return m


def member(m=Depends(current_user)):
    if m["status"] != "active":
        raise HTTPException(403, json.dumps({"reason": m["status"], "join": JOIN_URL}, ensure_ascii=False))
    return m


def is_inside(m):
    return m["level"] == "inside" or is_team(m)


# ---------------- норма месяца: Inside за вклад, а не за баллы ----------------
NORM_DAYS = 30
NORM_PARTS = (("invite", ("invite",)), ("coffee", ("coffee",)), ("story", ("story", "result")))


def ensure_norm():
    con = db.connect()
    cols = {r[1] for r in con.execute("PRAGMA table_info(members)")}
    if "inside_auto" not in cols:
        con.execute("ALTER TABLE members ADD COLUMN inside_auto INTEGER DEFAULT 0")
    if "birthday" not in cols:
        con.execute("ALTER TABLE members ADD COLUMN birthday TEXT")
        try:  # дату из уже заполненных анкет переносим один раз
            ensure_forms(con)
            for r in con.execute("SELECT tg_id, data FROM forms WHERE kind='start' AND tg_id IS NOT NULL ORDER BY id").fetchall():
                bd = str((json.loads(r["data"] or "{}") or {}).get("birthday") or "").strip()
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", bd):
                    con.execute("UPDATE members SET birthday=? WHERE tg_id=?", (bd, r["tg_id"]))
        except Exception:
            log.exception("перенос дат рождения")
    if "card_name" not in cols:
        con.execute("ALTER TABLE members ADD COLUMN card_name TEXT")
    if "card_ask" not in cols:
        con.execute("ALTER TABLE members ADD COLUMN card_ask INTEGER DEFAULT 0")
    if "last_seen" not in cols:
        con.execute("ALTER TABLE members ADD COLUMN last_seen TEXT")
        con.execute("UPDATE members SET last_seen=?", (db.now(),))  # точка отсчета: «давно не заходили» считается с момента обновления
    con.execute("CREATE TABLE IF NOT EXISTS crm_kv(k TEXT PRIMARY KEY, v TEXT, updated_at TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS reminder_log(tg_id INTEGER, kind TEXT, ref TEXT, sent_at TEXT, PRIMARY KEY(tg_id, kind, ref))")
    con.commit()
    con.close()


def norm_state(con, tg_id):
    """За последние 30 дней подтверждены: приглашенный и оплативший участник, встреча Random Coffee,
    рассказ о клубе или о своих результатах. Все три пункта = Inside до тех пор, пока самый старый из них не выйдет из окна."""
    since = (datetime.now(timezone.utc) - timedelta(days=NORM_DAYS)).isoformat()
    last = {}
    for key, codes in NORM_PARTS:
        q = ("SELECT MAX(decided_at) FROM claims WHERE tg_id=? AND status='approved' AND rule_code IN (%s) AND decided_at>=?"
             % ",".join("?" * len(codes)))
        last[key] = con.execute(q, (tg_id, *codes, since)).fetchone()[0]
    done = all(last.values())
    until, days_left = None, 0
    if done:
        try:
            until_dt = min(datetime.fromisoformat(v) for v in last.values()) + timedelta(days=NORM_DAYS)
            until = until_dt.isoformat()
            days_left = max(0, (until_dt - datetime.now(timezone.utc)).days + 1)
        except ValueError:
            done = False
    return {"invite": bool(last["invite"]), "coffee": bool(last["coffee"]), "story": bool(last["story"]),
            "done": done, "until": until, "days_left": days_left, "days": NORM_DAYS}


async def recalc_inside(con, tg_id):
    """Выдает или снимает Inside по норме месяца. Inside, выданный командой вручную, не трогает."""
    m = con.execute("SELECT level, inside_auto, status FROM members WHERE tg_id=?", (tg_id,)).fetchone()
    if not m or m["status"] != "active":
        return
    st = norm_state(con, tg_id)
    if st["done"] and m["level"] != "inside":
        con.execute("UPDATE members SET level='inside', inside_auto=1 WHERE tg_id=?", (tg_id,))
        con.commit()
        if auto_on(con):
            await send_text(tg_id, render(con, "inside_on", days=st["days_left"]), tg.app_button("Открыть клуб", "#profile"), key="inside_on", con=con)
    elif not st["done"] and m["level"] == "inside" and m["inside_auto"]:
        con.execute("UPDATE members SET level='club', inside_auto=0 WHERE tg_id=?", (tg_id,))
        con.commit()
        if auto_on(con):
            await send_text(tg_id, render(con, "inside_off"), tg.app_button("Что осталось", "#profile"), key="inside_off", con=con)


# ---------------- после эфира: запись, «смотрел», инсайты по хештегу ----------------
INSIGHT_TAG = re.compile(r"#инсайт\w*", re.I)


def ensure_recap():
    con = db.connect()
    first = not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_notice'").fetchone()
    con.execute("CREATE TABLE IF NOT EXISTS event_watch(tg_id INTEGER, event_id INTEGER, created_at TEXT, PRIMARY KEY(tg_id, event_id))")
    con.execute("CREATE TABLE IF NOT EXISTS event_notice(event_id INTEGER, kind TEXT, sent_at TEXT, PRIMARY KEY(event_id, kind))")
    if first:  # при первом запуске старые записи не рассылаем: напоминания только для новых
        for r in con.execute("SELECT id FROM events WHERE recording_url!=''").fetchall():
            for kind in ("record", "nudge"):
                con.execute("INSERT OR IGNORE INTO event_notice(event_id,kind,sent_at) VALUES(?,?,?)", (r[0], kind, db.now()))
    con.commit()
    con.close()


def team_chat_ids(con):
    return set(tg.MANAGER_CHAT_IDS) | set(db.team_ids(con))


def team_targets(con, key):
    """Кому из команды уходит это сообщение. Ничего не выбрано: всем, как раньше."""
    v = db.get_setting(con, "route:" + key, None)
    if v is None or v == "":
        return set() if (TEXTS.get(key, {}).get("route0") == "none") else team_chat_ids(con)
    try:
        ids = json.loads(v)
    except ValueError:
        return team_chat_ids(con)
    if ids is None:
        return team_chat_ids(con)
    return {int(i) for i in ids} & team_chat_ids(con)


async def decide_claim(con, cid, approve, points=None):
    """Единое решение по заявке на баллы: из кабинета и из кнопок в боте."""
    c = con.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
    if not c or c["status"] != "pending":
        return None
    status = "approved" if approve else "rejected"
    pts = int(points) if points is not None else c["points"]
    con.execute("UPDATE claims SET status=?, points=?, decided_at=? WHERE id=?", (status, pts, db.now(), cid))
    con.commit()
    if approve:
        await send_text(c["tg_id"], render(con, "points_ok", points=pts), tg.app_button("Мои баллы", "#profile"), key="points_ok", con=con)
        await recalc_inside(con, c["tg_id"])
    return status, pts, c


def _recap_audience(con, e):
    rows = con.execute("SELECT * FROM members WHERE status='active' AND bot_started=1").fetchall()
    return [db.row(r) for r in rows]


async def _send_recap(con, e, kind):
    pts = con.execute("SELECT points FROM point_rules WHERE code='insight'").fetchone()
    pts = pts["points"] if pts else 10
    watched = {r[0] for r in con.execute("SELECT tg_id FROM event_watch WHERE event_id=?", (e["id"],))}
    for m in _recap_audience(con, e):
        if kind == "nudge" and m["tg_id"] in watched:
            continue
        if e["inside_only"] and not is_inside(m):
            if kind == "nudge":
                continue  # повторно закрытый эфир тем, у кого нет Inside, не напоминаем
            text = render(con, "recap_closed", title=e["title"])
            try:
                await send_text(m["tg_id"], text, tg.app_button("Как перейти на Inside", "#profile"), key="recap_closed", con=con)
            except Exception:
                log.exception("напоминание о закрытом эфире")
            await asyncio.sleep(0.15)
            continue
        rk = "recap_record" if kind == "record" else "recap_nudge"
        text = render(con, rk, title=e["title"], points=pts)
        kb = {"inline_keyboard": [[{"text": "Смотреть запись", "url": e["recording_url"]}],
                                  [{"text": "Смотрел", "callback_data": f"w:{e['id']}"}]]}
        try:
            await send_text(m["tg_id"], text, kb, key=rk, con=con)
        except Exception:
            log.exception("напоминание о записи")
        await asyncio.sleep(0.15)


async def recap_loop():
    while True:
        try:
            con = db.connect()
            try:
                since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                for e in ([] if not auto_on(con) else con.execute("SELECT * FROM events WHERE recording_url!='' AND starts_at>=?", (since,)).fetchall()):
                    done = {r[0] for r in con.execute("SELECT kind FROM event_notice WHERE event_id=?", (e["id"],))}
                    if "record" not in done:
                        con.execute("INSERT OR IGNORE INTO event_notice(event_id,kind,sent_at) VALUES(?,?,?)", (e["id"], "record", db.now()))
                        con.commit()
                        await _send_recap(con, e, "record")
                    elif "nudge" not in done:
                        sent = con.execute("SELECT sent_at FROM event_notice WHERE event_id=? AND kind='record'", (e["id"],)).fetchone()[0]
                        if datetime.fromisoformat(sent) < datetime.now(timezone.utc) - timedelta(hours=48):
                            con.execute("INSERT OR IGNORE INTO event_notice(event_id,kind,sent_at) VALUES(?,?,?)", (e["id"], "nudge", db.now()))
                            con.commit()
                            await _send_recap(con, e, "nudge")
            finally:
                con.close()
        except Exception:
            log.exception("напоминания о записи")
        await asyncio.sleep(1800)


QUIET_DAYS = 21


def quiet_members(con):
    """Активные участники, которые не открывали приложение 21 день (и давно в клубе)."""
    lim = (datetime.now(timezone.utc) - timedelta(days=QUIET_DAYS)).isoformat()
    return con.execute("SELECT * FROM members WHERE status='active' AND role IS NOT 'team' AND created_at<? AND COALESCE(last_seen,'')<?", (lim, lim)).fetchall()


def _first_name(m):
    return (m["first_name"] or "").strip() or "Здравствуйте"


async def reminders_run(con):
    """Напоминания участникам: анкета (1, 3, 7 день), продление (за 7 и 1 день), «давно не заходили». Каждое уходит один раз."""
    nowm = datetime.now(MSK)
    if not auto_on(con) or not (10 <= nowm.hour < 20):
        return 0
    now = datetime.now(timezone.utc)
    sent = 0

    async def once(m, kind, ref, key, kb, **v):
        nonlocal sent
        if con.execute("SELECT 1 FROM reminder_log WHERE tg_id=? AND kind=? AND ref=?", (m["tg_id"], kind, ref)).fetchone():
            return
        con.execute("INSERT OR IGNORE INTO reminder_log VALUES(?,?,?,?)", (m["tg_id"], kind, ref, db.now()))
        con.commit()
        try:
            await send_text(m["tg_id"], render(con, key, name=_first_name(m), **v), kb, key=key, con=con)
            sent += 1
        except Exception:
            log.exception("напоминание %s", kind)
        await asyncio.sleep(0.15)

    members = [db.row(r) for r in con.execute("SELECT * FROM members WHERE status='active' AND bot_started=1 AND role IS NOT 'team'")]
    # анкета: только новым (до 10 дней в клубе), у кого ее нет
    for m in members:
        try:
            created = datetime.fromisoformat(str(m["created_at"]).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        age = (now - created).days
        if age > 9 or m.get("profile_done"):
            continue
        try:
            has_form = con.execute("SELECT 1 FROM forms WHERE tg_id=? AND kind='start'", (m["tg_id"],)).fetchone()
        except Exception:
            has_form = None
        if has_form:
            continue
        for day in (7, 3, 1):
            if age >= day:
                await once(m, f"anketa{day}", "", f"r_anketa_{day}", tg.app_button(get_plain(con, "btn_form"), "static/anketa.html"))
                break
    # продление
    for m in members:
        pu = str(m.get("paid_until") or "")
        if not pu:
            continue
        try:
            left = datetime.fromisoformat(pu.replace("Z", "+00:00")) - now
        except ValueError:
            continue
        if timedelta(0) < left <= timedelta(days=7):
            day = 1 if left <= timedelta(days=1) else 7
            date = pu[8:10] + "." + pu[5:7]
            kb = {"inline_keyboard": [[{"text": "Продлить участие", "url": JOIN_URL}]]} if JOIN_URL else None
            await once(m, f"renew{day}", pu[:10], f"r_renew_{day}", kb, date=date, link=JOIN_URL or "")
    # давно не заходили: не чаще раза в 30 дней
    for r in quiet_members(con):
        m = db.row(r)
        if not m.get("bot_started"):
            continue
        last = con.execute("SELECT MAX(sent_at) FROM reminder_log WHERE tg_id=? AND kind='quiet'", (m["tg_id"],)).fetchone()[0]
        if last and last > (now - timedelta(days=30)).isoformat():
            continue
        ref = now.strftime("%Y-%m-%d")
        await once(m, "quiet", ref, "r_quiet", tg.app_button("Открыть клуб"))
    return sent


def stats_items(con, days=7):
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()
    q = lambda sql, *a: con.execute(sql, a).fetchone()[0] or 0
    pays = con.execute("SELECT event,amount FROM payments WHERE verified=1 AND created_at>=? AND event NOT IN ('new_donation','recurrent_donation','cancelled_donation','cancelled_subscription','subscription_cancelled')", (since,)).fetchall()
    new_n = sum(1 for p in pays if p["event"] in NEW_SUB)
    sum_all = int(sum((p["amount"] or 0) for p in pays))
    items = [f"Оплат: {len(pays)} на {sum_all} ₽ (новых участников {new_n}, продлений {len(pays) - new_n})"]
    items.append(f"Участников сейчас: {q('SELECT COUNT(*) FROM members WHERE status=?', 'active')}, из них в Inside {q('SELECT COUNT(*) FROM members WHERE status=? AND level=?', 'active', 'inside')}")
    soon = q("SELECT COUNT(*) FROM members WHERE status='active' AND paid_until BETWEEN ? AND ?", now.isoformat(), (now + timedelta(days=14)).isoformat())
    items.append(f"Оплата заканчивается в ближайшие 14 дней: {soon}")
    items.append(f"Подтверждено заявок на баллы: {q('SELECT COUNT(*) FROM claims WHERE status=? AND decided_at>=?', 'approved', since)}, баллов начислено {q('SELECT SUM(points) FROM claims WHERE status=? AND decided_at>=?', 'approved', since)}")
    items.append(f"Эфиров прошло: {q('SELECT COUNT(*) FROM events WHERE starts_at BETWEEN ? AND ?', since, now.isoformat())}, записей на эфиры {q('SELECT COUNT(*) FROM rsvp WHERE created_at>=?', since)}")
    items.append(f"Встреч Random Coffee состоялось: {q('SELECT COUNT(*) FROM coffee_pairs WHERE created_at>=? AND (met_a=1 OR met_b=1)', since)}, новых взаимных симпатий {q('SELECT COUNT(*) FROM matches WHERE created_at>=?', since)}")
    items.append(f"Открывали приложение за неделю: {q('SELECT COUNT(*) FROM members WHERE status=? AND last_seen>=?', 'active', since)}; давно не заходили: {len(quiet_members(con))}")
    return items


async def send_stats(con):
    chats = team_targets(con, "t_stats")
    if not chats:
        return 0
    now = datetime.now(MSK)
    period = f"{(now - timedelta(days=7)).strftime('%d.%m')} - {now.strftime('%d.%m')}"
    text = md_html(text_raw(con, "t_stats")).replace("{period}", period).replace("{items}", "\n".join("• " + html.escape(i) for i in stats_items(con)))
    for chat in chats:
        await send_text(chat, text, key="t_stats", con=con)
    return len(chats)


def digest_items(con):
    """Что сегодня требует решения менеджера. Пустой список: сообщение не отправляем."""
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(hours=24)).isoformat()
    items, claims = [], con.execute("SELECT * FROM claims WHERE status='pending' ORDER BY id").fetchall()
    if claims:
        items.append(f"Заявок на баллы ждет решения: {len(claims)} (ниже, с кнопками)")
    try:
        n = con.execute("SELECT COUNT(*) FROM offers WHERE status='pending'").fetchone()[0]
    except Exception:
        n = 0
    if n:
        items.append(f"Предложений на проверку: {n} (кабинет, вкладка «Предложения»)")
    try:
        n = con.execute("SELECT COUNT(*) FROM forms WHERE created_at>=?", (day_ago,)).fetchone()[0]
    except Exception:
        n = 0
    if n:
        items.append(f"Новых анкет за сутки: {n} (кабинет, вкладка «Анкеты»)")
    n = con.execute("SELECT COUNT(*) FROM members WHERE status='active' AND created_at>=?", (day_ago,)).fetchone()[0]
    if n:
        items.append(f"Новых участников за сутки: {n}")
    soon = con.execute("SELECT first_name,last_name,username,paid_until FROM members WHERE status='active' AND paid_until!='' AND paid_until BETWEEN ? AND ? ORDER BY paid_until LIMIT 15",
                       (now.isoformat(), (now + timedelta(days=7)).isoformat())).fetchall()
    if soon:
        names = ", ".join(((r["first_name"] or "") + " " + (r["last_name"] or "")).strip() + (f" @{r['username']}" if r["username"] else "") + f" (до {str(r['paid_until'])[8:10]}.{str(r['paid_until'])[5:7]})" for r in soon)
        items.append(f"Оплата заканчивается в ближайшие 7 дней: {names}. Напишите им лично")
    n = len(quiet_members(con))
    if n:
        items.append(f"Давно не заходили (21 день и больше): {n}. Участникам уже ушло напоминание, посмотрите список в кабинете")
    ev = con.execute("SELECT title,starts_at FROM events WHERE starts_at BETWEEN ? AND ? ORDER BY starts_at", (now.isoformat(), (now + timedelta(hours=36)).isoformat())).fetchall()
    for e in ev:
        items.append(f"Скоро эфир: {e['title']} ({e['starts_at'][:16].replace('T', ' ')} UTC)")
    return items, claims


async def send_digest(con):
    items, claims = digest_items(con)
    if not items:
        return 0
    chats = team_targets(con, "t_digest")
    # список уже экранирован построчно, поэтому подставляем как готовый HTML
    head = md_html(text_raw(con, "t_digest")).replace("{date}", datetime.now(MSK).strftime("%d.%m")).replace("{items}", "\n".join("• " + html.escape(i) for i in items))
    for chat in chats:
        await send_text(chat, head, key="t_digest", con=con)
        for c in claims[:8]:
            mem = con.execute("SELECT first_name,username FROM members WHERE tg_id=?", (c["tg_id"],)).fetchone()
            who = ((mem["first_name"] or "") + (" @" + mem["username"] if mem and mem["username"] else "")).strip() if mem else str(c["tg_id"])
            rule = con.execute("SELECT title FROM point_rules WHERE code=?", (c["rule_code"],)).fetchone()
            kb = {"inline_keyboard": [[{"text": f"Подтвердить +{c['points']}", "callback_data": f"c:{c['id']}:1"},
                                       {"text": "Отклонить", "callback_data": f"c:{c['id']}:0"}]]}
            await send_text(chat, render(con, "t_digest_claim", rule=(rule["title"] if rule else c["rule_code"]), points=c["points"], who=who,
                                         text=(c["text"] or "")[:500]), kb, key="t_digest_claim", con=con)
    return len(items)


async def birthday_run(con):
    """Дни рождения: утром в день рождения и за 3 дня команде приходит уведомление. Анкета -> members.birthday."""
    nowm = datetime.now(MSK)
    if nowm.hour < int(db.get_setting(con, "digest_hour", "9") or 9):
        return
    for delta, key in ((0, "t_birthday"), (3, "t_birthday_soon")):
        day = (nowm + timedelta(days=delta)).date()
        mmdd = day.strftime("-%m-%d")
        rows = con.execute("SELECT * FROM members WHERE status='active' AND birthday LIKE ?", ("%" + mmdd,)).fetchall()
        for m in rows:
            ref = day.isoformat()
            if con.execute("SELECT 1 FROM reminder_log WHERE tg_id=? AND kind=? AND ref=?", (m["tg_id"], key, ref)).fetchone():
                continue
            con.execute("INSERT OR IGNORE INTO reminder_log VALUES(?,?,?,?)", (m["tg_id"], key, ref, db.now()))
            con.commit()
            who = ((m["first_name"] or "") + (" @" + m["username"] if m["username"] else "")).strip() or f"id {m['tg_id']}"
            try:
                born = int(str(m["birthday"])[:4])
                age = f", исполняется {day.year - born}" if 1900 < born < day.year else ""
            except ValueError:
                age = ""
            wish = render(con, "birthday_wish", name=_first_name(m))
            await team_notify(render(con, key, who=who, age=age, wish=Raw(wish), date=day.strftime("%d.%m")), key)


async def digest_loop():
    while True:
        try:
            con = db.connect()
            try:
                if db.get_setting(con, "digest_on", "1") == "1":
                    nowm = datetime.now(MSK)
                    hour = int(db.get_setting(con, "digest_hour", "9") or 9)
                    today = nowm.strftime("%Y-%m-%d")
                    if nowm.hour >= hour and db.get_setting(con, "digest_last", "") != today:
                        db.set_setting(con, "digest_last", today)
                        con.commit()
                        await send_digest(con)
                    if nowm.weekday() == 0 and nowm.hour >= hour and db.get_setting(con, "stats_last", "") != today:
                        db.set_setting(con, "stats_last", today)
                        con.commit()
                        await send_stats(con)
                await reminders_run(con)
                await birthday_run(con)
            finally:
                con.close()
        except Exception:
            log.exception("дайджест")
        await asyncio.sleep(600)


async def handle_callback(con, cq):
    u, data = cq.get("from") or {}, cq.get("data") or ""
    cid_q = cq.get("id")
    async def answer(text=""):
        await tg._call(tg.BOT_TOKEN, "answerCallbackQuery", {"callback_query_id": cid_q, "text": text})
    if data.startswith("w:") and data[2:].isdigit():
        con.execute("INSERT OR IGNORE INTO event_watch(tg_id,event_id,created_at) VALUES(?,?,?)", (u.get("id"), int(data[2:]), db.now()))
        con.commit()
        await answer("Отметила. Теперь напишите инсайт в чат с хештегом #инсайт")
        msg = cq.get("message") or {}
        kb = (msg.get("reply_markup") or {}).get("inline_keyboard") or []
        if msg.get("chat") and kb:
            await tg._call(tg.BOT_TOKEN, "editMessageReplyMarkup", {"chat_id": msg["chat"]["id"], "message_id": msg["message_id"],
                                                                     "reply_markup": {"inline_keyboard": kb[:1]}})
        return
    if data.startswith("c:"):
        parts = data.split(":")
        if len(parts) == 3 and parts[1].isdigit() and u.get("id") in team_chat_ids(con):
            res = await decide_claim(con, int(parts[1]), parts[2] == "1")
            await answer("Готово" if res else "Заявка уже обработана")
            msg = cq.get("message") or {}
            if msg.get("chat"):
                label = "Подтверждено" if res and res[0] == "approved" else ("Отклонено" if res else "Уже обработана")
                await tg._call(tg.BOT_TOKEN, "editMessageReplyMarkup", {"chat_id": msg["chat"]["id"], "message_id": msg["message_id"],
                                                                         "reply_markup": {"inline_keyboard": [[{"text": label, "callback_data": "x"}]]}})
            return
    await answer()


async def handle_chat_insight(con, msg):
    """Сообщение в чате клуба с хештегом #инсайт: бот фиксирует его как заявку на баллы и отправляет команде."""
    u, text = msg.get("from") or {}, (msg.get("text") or msg.get("caption") or "")
    if not u or u.get("is_bot") or not INSIGHT_TAG.search(text):
        return
    row = con.execute("SELECT * FROM members WHERE tg_id=?", (int(u["id"]),)).fetchone()
    if not row:
        return
    m = db.row(row)
    if refresh_status(con, m) != "active":
        return
    ev = con.execute("SELECT id,title FROM events WHERE recording_url!='' AND starts_at<=? AND starts_at>=? ORDER BY starts_at DESC LIMIT 1",
                     (datetime.now(timezone.utc).isoformat(), (datetime.now(timezone.utc) - timedelta(days=21)).isoformat())).fetchone()
    ref = f"event:{ev['id']}" if ev else f"tg:{msg['chat']['id']}:{msg['message_id']}"
    if con.execute("SELECT 1 FROM claims WHERE tg_id=? AND ref=? AND status!='rejected'", (m["tg_id"], ref)).fetchone():
        await send_text(m["tg_id"], render(con, "insight_dup"), key="insight_dup", con=con)
        return
    clean = INSIGHT_TAG.sub("", text).strip()[:1000]
    cid, rule = add_claim(con, m["tg_id"], "insight", clean, ref=ref)
    con.commit()
    await send_text(m["tg_id"], render(con, "insight_ok", points=rule["points"]), tg.app_button("Мои баллы", "#profile"), key="insight_ok", con=con)
    who = (m.get("first_name") or "") + (f" @{m['username']}" if m.get("username") else "")
    kb = {"inline_keyboard": [[{"text": f"Подтвердить +{rule['points']}", "callback_data": f"c:{cid}:1"},
                               {"text": "Отклонить", "callback_data": f"c:{cid}:0"}]]}
    head = render(con, "t_insight", who=who.strip(), event=(f" по эфиру «{ev['title']}»" if ev else ""), text=clean)
    for chat in team_targets(con, "t_insight"):
        try:
            await send_text(chat, head, kb, key="t_insight", con=con)
        except Exception:
            log.exception("инсайт команде")


async def norm_loop():
    while True:
        try:
            con = db.connect()
            try:
                for r in con.execute("SELECT tg_id FROM members WHERE inside_auto=1").fetchall():
                    await recalc_inside(con, r[0])
            finally:
                con.close()
        except Exception:
            log.exception("пересчет Inside")
        await asyncio.sleep(6 * 3600)


YEAR_MONTHS = 12   # годовой тариф
GUEST_PASSES = 2   # гостевых пропусков на эфиры в год у участника годового тарифа


def is_year(m):
    """Годовой тариф: активная подписка на 12 месяцев. Уровень Inside он не дает, только особые бонусы."""
    try:
        return m.get("status") == "active" and int(m.get("period_months") or 0) >= YEAR_MONTHS
    except (TypeError, ValueError):
        return False


def public_card(m):
    d = {k: m.get(k) for k in ("tg_id", "first_name", "last_name", "sphere", "project", "city", "seek", "give", "tags", "offline", "level")}
    d["year"] = is_year(m)
    return d


@app.get("/api/me")
def me(m=Depends(current_user), con=Depends(get_con)):
    try:  # когда человек последний раз открывал приложение (не чаще раза в час)
        ls = m.get("last_seen") or ""
        if not ls or ls < (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat():
            con.execute("UPDATE members SET last_seen=? WHERE tg_id=?", (db.now(), m["tg_id"]))
            con.commit()
    except Exception:
        log.exception("last_seen")
    stats = {
        "matches": con.execute("SELECT COUNT(*) FROM matches WHERE a=? OR b=?", (m["tg_id"], m["tg_id"])).fetchone()[0],
        "insights": con.execute("SELECT COUNT(*) FROM claims WHERE tg_id=? AND rule_code='insight'", (m["tg_id"],)).fetchone()[0],
        "coffee": con.execute("SELECT COUNT(*) FROM coffee_pairs WHERE (a=? AND met_a=1) OR (b=? AND met_b=1)", (m["tg_id"], m["tg_id"])).fetchone()[0],
    }
    return {"me": m, "points": db.balance(con, m["tg_id"]), "stats": stats, "join": JOIN_URL,
            "is_admin": is_team(m), "year": is_year(m), "norm": norm_state(con, m["tg_id"])}


# ---------------- мои запросы: что человек хочет сейчас ----------------
SPHERES = ("Деньги", "Смыслы", "Знакомства", "Возможности", "Практики", "Впечатления")


def ensure_wants(con):
    con.execute("CREATE TABLE IF NOT EXISTS wants(tg_id INTEGER PRIMARY KEY, focus TEXT DEFAULT '', goal TEXT DEFAULT '', updated_at TEXT)")


@app.get("/api/wants")
def wants_get(m=Depends(member), con=Depends(get_con)):
    """Кого ищу и чем могу помочь живут в профиле (по ним строятся знакомства), сфера и цель месяца здесь.
    Пока человек ничего не менял, подставляем ответы из последней ежемесячной анкеты."""
    ensure_wants(con); ensure_forms(con)
    r = con.execute("SELECT focus, goal, updated_at FROM wants WHERE tg_id=?", (m["tg_id"],)).fetchone()
    focus, goal, upd = (r["focus"], r["goal"], r["updated_at"]) if r else ("", "", None)
    if not r:
        f = con.execute("SELECT data FROM forms WHERE tg_id=? AND kind='monthly' ORDER BY id DESC LIMIT 1", (m["tg_id"],)).fetchone()
        if f:
            try:
                d = json.loads(f["data"] or "{}")
                focus = d.get("focus") if isinstance(d.get("focus"), str) else ""
                goal = d.get("next_goal") if isinstance(d.get("next_goal"), str) else ""
            except ValueError:
                pass
    return {"focus": focus if focus in SPHERES else "", "goal": goal or "", "seek": m.get("seek") or "",
            "give": m.get("give") or "", "updated_at": upd}


@app.put("/api/wants")
async def wants_put(req: Request, m=Depends(member), con=Depends(get_con)):
    ensure_wants(con)
    d = await req.json()
    focus = str(d.get("focus") or "")
    if focus and focus not in SPHERES:
        raise HTTPException(400, "Выберите сферу из списка")
    goal, seek, give = (str(d.get(k) or "").strip()[:1000] for k in ("goal", "seek", "give"))
    now = db.now()
    con.execute("INSERT INTO wants(tg_id,focus,goal,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(tg_id) DO UPDATE SET focus=excluded.focus, goal=excluded.goal, updated_at=excluded.updated_at",
                (m["tg_id"], focus, goal, now))
    con.execute("UPDATE members SET seek=?, give=?, updated_at=? WHERE tg_id=?", (seek, give, now, m["tg_id"]))
    con.commit()
    return {"ok": True, "updated_at": now}


@app.put("/api/me")
async def update_me(req: Request, m=Depends(current_user), con=Depends(get_con)):
    data = await req.json()
    allowed = {"first_name", "last_name", "sphere", "project", "city", "seek", "give", "offline", "coffee", "tags"}
    upd = {k: v for k, v in data.items() if k in allowed}
    if "tags" in upd:
        upd["tags"] = json.dumps(upd["tags"][:8], ensure_ascii=False)
    for k in ("offline", "coffee"):
        if k in upd:
            upd[k] = 1 if upd[k] else 0
    if data.get("consent") and not m["consent_at"]:
        upd["consent_at"] = db.now()
    merged = {**m, **upd}
    upd["profile_done"] = 1 if all((merged.get(k) or "").strip() for k in ("sphere", "city", "seek", "give")) else 0
    if upd:
        sets = ", ".join(f"{k}=?" for k in upd)
        con.execute(f"UPDATE members SET {sets}, updated_at=? WHERE tg_id=?", (*upd.values(), db.now(), m["tg_id"]))
        con.commit()
    return {"ok": True, "profile_done": upd["profile_done"]}


# ---------------- знакомства ----------------

@app.get("/api/feed")
def feed(f: str = "all", m=Depends(member), con=Depends(get_con)):
    q = """SELECT * FROM members WHERE status='active' AND profile_done=1 AND tg_id!=?
           AND tg_id NOT IN (SELECT to_id FROM likes WHERE from_id=?)"""
    args = [m["tg_id"], m["tg_id"]]
    if f == "city" and m["city"]:
        q += " AND lower(city)=lower(?)"; args.append(m["city"])
    if f == "offline":
        q += " AND offline=1"
    q += " ORDER BY updated_at DESC LIMIT 50"
    return [public_card(r) for r in db.rows(con.execute(q, args))]


@app.post("/api/like")
async def like(req: Request, m=Depends(member), con=Depends(get_con)):
    data = await req.json()
    to_id, val = int(data["to_id"]), 1 if data.get("like") else 0
    if to_id == m["tg_id"]:
        raise HTTPException(400, "Нельзя отметить себя")
    con.execute("INSERT OR REPLACE INTO likes VALUES(?,?,?,?)", (m["tg_id"], to_id, val, db.now()))
    matched = None
    if val and con.execute("SELECT 1 FROM likes WHERE from_id=? AND to_id=? AND value=1", (to_id, m["tg_id"])).fetchone():
        a, b = sorted((m["tg_id"], to_id))
        if not con.execute("SELECT 1 FROM matches WHERE a=? AND b=?", (a, b)).fetchone():
            con.execute("INSERT INTO matches VALUES(?,?,?)", (a, b, db.now()))
            other = db.row(con.execute("SELECT * FROM members WHERE tg_id=?", (to_id,)).fetchone())
            matched = {**public_card(other), "username": other["username"]}
            for who, peer in ((m, other), (other, m)):
                await send_text(who["tg_id"],
                                render(con, "match", peer=peer["first_name"] or "", nick=("Напишите: @" + peer["username"] if peer["username"] else "")),
                                tg.app_button("Открыть знакомства", "#matches"), key="match", con=con)
    con.commit()
    return {"match": matched}


@app.get("/api/matches")
def matches(m=Depends(member), con=Depends(get_con)):
    ids = [r[0] for r in con.execute("SELECT CASE WHEN a=? THEN b ELSE a END FROM matches WHERE a=? OR b=? ORDER BY created_at DESC",
                                     (m["tg_id"], m["tg_id"], m["tg_id"]))]
    out = []
    for i in ids:
        r = db.row(con.execute("SELECT * FROM members WHERE tg_id=?", (i,)).fetchone())
        if r:
            out.append({**public_card(r), "username": r["username"]})
    hidden = con.execute("""SELECT COUNT(*) FROM likes WHERE to_id=? AND value=1
                            AND from_id NOT IN (SELECT to_id FROM likes WHERE from_id=?)""", (m["tg_id"], m["tg_id"])).fetchone()[0]
    return {"matches": out, "liked_you": hidden}


@app.get("/api/coffee")
def my_coffee(m=Depends(member), con=Depends(get_con)):
    r = con.execute("SELECT * FROM coffee_pairs WHERE (a=? OR b=?) ORDER BY id DESC LIMIT 1", (m["tg_id"], m["tg_id"])).fetchone()
    if not r or r["week"] != coffee.week_key():
        return {"pair": None, "week": coffee.week_key(), "enabled": bool(m["coffee"]), "profile_done": bool(m["profile_done"])}
    mine_a = r["a"] == m["tg_id"]
    other = db.row(con.execute("SELECT * FROM members WHERE tg_id=?", (r["b"] if mine_a else r["a"],)).fetchone())
    return {"pair": {**public_card(other), "username": other["username"]}, "id": r["id"], "week": r["week"],
            "reason": r["reason_a"] if mine_a else r["reason_b"], "met": r["met_a"] if mine_a else r["met_b"]}


@app.post("/api/coffee/{pair_id}/feedback")
async def coffee_feedback(pair_id: int, req: Request, m=Depends(member), con=Depends(get_con)):
    data = await req.json()
    r = con.execute("SELECT * FROM coffee_pairs WHERE id=?", (pair_id,)).fetchone()
    if not r or m["tg_id"] not in (r["a"], r["b"]):
        raise HTTPException(404, "Пара не найдена")
    col = "met_a" if r["a"] == m["tg_id"] else "met_b"
    met = 1 if data.get("met") else 0
    con.execute(f"UPDATE coffee_pairs SET {col}=? WHERE id=?", (met, pair_id))
    if met and (data.get("text") or "").strip():
        add_claim(con, m["tg_id"], "coffee", data["text"].strip(), ref=f"coffee:{pair_id}")
    con.commit()
    return {"ok": True}


# ---------------- эфиры и библиотека ----------------

def ensure_guests(con):
    con.execute("""CREATE TABLE IF NOT EXISTS guest_passes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, event_id INTEGER, guest_name TEXT, created_at TEXT)""")


def guest_left(con, m):
    if not is_year(m):
        return 0
    ensure_guests(con)
    cut = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    used = con.execute("SELECT COUNT(*) FROM guest_passes WHERE tg_id=? AND created_at>=?", (m["tg_id"], cut)).fetchone()[0]
    return max(0, GUEST_PASSES - used)


@app.post("/api/events/{eid}/guest")
async def event_guest(eid: int, req: Request, m=Depends(member), con=Depends(get_con)):
    if not is_year(m):
        raise HTTPException(403, "Гостевые пропуска есть на годовом тарифе")
    ensure_guests(con)
    d = await req.json()
    name = str(d.get("name", "")).strip()[:80]
    if not name:
        raise HTTPException(400, "Напишите имя друга")
    e = con.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
    if not e or e["starts_at"] < (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat():
        raise HTTPException(404, "Эфир уже прошел")
    if e["inside_only"] and not is_inside(m):
        raise HTTPException(403, "Это закрытый эфир для Inside")
    if not con.execute("SELECT 1 FROM rsvp WHERE event_id=? AND tg_id=?", (eid, m["tg_id"])).fetchone():
        raise HTTPException(400, "Сначала отметьте, что придете сами: нажмите «Буду»")
    if guest_left(con, m) < 1:
        raise HTTPException(400, "Гостевые пропуска на этот год закончились")
    con.execute("INSERT INTO guest_passes(tg_id,event_id,guest_name,created_at) VALUES(?,?,?,?)", (m["tg_id"], eid, name, db.now()))
    con.commit()
    spawn(team_notify(render(con, "t_guest", who=person_name(m), guest=name, event=e["title"]), "t_guest"))
    return {"left": guest_left(con, m), "join_url": e["join_url"]}


@app.get("/api/events")
def events(m=Depends(member), con=Depends(get_con)):
    now_iso = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    soon = db.rows(con.execute("SELECT * FROM events WHERE starts_at>=? ORDER BY starts_at", (now_iso,)))
    recs = db.rows(con.execute("SELECT * FROM events WHERE starts_at<? AND recording_url!='' ORDER BY starts_at DESC LIMIT 50", (now_iso,)))
    going = {r[0] for r in con.execute("SELECT event_id FROM rsvp WHERE tg_id=?", (m["tg_id"],))}
    inside = is_inside(m)
    for e in soon + recs:
        e["going"] = e["id"] in going
        e["locked"] = bool(e["inside_only"]) and not inside
        if e["locked"] or not e["going"]:
            e["join_url"] = ""  # ссылку на Zoom видят только записавшиеся
        if e["locked"]:
            e["recording_url"] = e["podcast_url"] = ""
    return {"soon": soon, "records": recs, "guest": {"year": is_year(m), "left": guest_left(con, m), "total": GUEST_PASSES}}


@app.post("/api/events/{eid}/rsvp")
def rsvp(eid: int, m=Depends(member), con=Depends(get_con)):
    e = con.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
    if not e:
        raise HTTPException(404, "Эфир не найден")
    if e["inside_only"] and not is_inside(m):
        raise HTTPException(403, "Только для Inside-level")
    if con.execute("SELECT 1 FROM rsvp WHERE event_id=? AND tg_id=?", (eid, m["tg_id"])).fetchone():
        con.execute("DELETE FROM rsvp WHERE event_id=? AND tg_id=?", (eid, m["tg_id"])); going = False
    else:
        con.execute("INSERT INTO rsvp VALUES(?,?,?)", (eid, m["tg_id"], db.now())); going = True
    con.commit()
    return {"going": going, "join_url": e["join_url"] if going else ""}


@app.get("/api/library")
def library(type: str = "all", q: str = "", m=Depends(member), con=Depends(get_con)):
    sql, args = "SELECT * FROM library WHERE 1=1", []
    if type != "all":
        sql += " AND type=?"; args.append(type)
    if q.strip():
        sql += " AND (lower(title) LIKE ? OR lower(author) LIKE ? OR lower(body) LIKE ?)"
        args += [f"%{q.strip().lower()}%"] * 3
    items = db.rows(con.execute(sql + " ORDER BY created_at DESC LIMIT 200", args))
    inside = is_inside(m)
    for it in items:
        it["locked"] = bool(it["inside_only"]) and not inside
        if it["locked"]:
            it["url"] = it["body"] = ""
    return items


# ---------------- баллы ----------------

def add_claim(con, tg_id, code, text="", file=None, ref=None):
    rule = con.execute("SELECT * FROM point_rules WHERE code=? AND active=1", (code,)).fetchone()
    if not rule:
        raise HTTPException(400, "Нет такого действия")
    cur = con.execute("INSERT INTO claims(tg_id,rule_code,points,text,file,ref,created_at) VALUES(?,?,?,?,?,?,?)",
                      (tg_id, code, rule["points"], text, file, ref, db.now()))
    return cur.lastrowid, rule


@app.get("/api/points")
def points(m=Depends(member), con=Depends(get_con)):
    rules = db.rows(con.execute("SELECT * FROM point_rules WHERE active=1 ORDER BY sort"))
    claims = db.rows(con.execute("SELECT id,rule_code,points,status,created_at FROM claims WHERE tg_id=? ORDER BY id DESC LIMIT 50", (m["tg_id"],)))
    ensure_shop(con)
    shop = db.rows(con.execute("SELECT * FROM shop WHERE active=1 ORDER BY cost"))
    for _it in shop:
        _it["img_url"] = shop_img_url(_it)
    return {"rules": rules, "claims": claims, "shop": shop, **db.balance(con, m["tg_id"]),
            "invite_link": f"https://t.me/edinenie_club_bot?start=ref_{m['tg_id']}"}


@app.post("/api/claims")
async def create_claim(rule_code: str = Form(...), text: str = Form(""), ref: str = Form(""),
                       file: UploadFile | None = File(None), m=Depends(member), con=Depends(get_con)):
    saved = None
    if file and file.filename:
        ext = (file.filename.rsplit(".", 1)[-1] or "jpg").lower()[:5]
        if ext not in ("jpg", "jpeg", "png", "webp", "heic"):
            raise HTTPException(400, "Нужна картинка: jpg, png или webp")
        body = await file.read()
        if len(body) > 10 * 1024 * 1024:
            raise HTTPException(400, "Файл больше 10 МБ")
        saved = f"{uuid.uuid4().hex}.{ext}"
        (UPLOADS / saved).write_bytes(body)
    if not text.strip() and not saved:
        raise HTTPException(400, "Напишите пару слов")
    cid, rule = add_claim(con, m["tg_id"], rule_code, text.strip(), saved, ref or None)
    con.commit()
    await team_notify(render(con, "t_claim", rule=rule["title"], points=rule["points"],
                             who=((m["first_name"] or "") + (" @" + m["username"] if m["username"] else "")).strip(), text=text[:500],
                             link=f"{PUBLIC_URL}/admin"), "t_claim")
    return {"ok": True, "id": cid, "points": rule["points"]}


@app.post("/api/shop/{code}")
async def redeem(code: str, m=Depends(member), con=Depends(get_con)):
    item = con.execute("SELECT * FROM shop WHERE code=? AND active=1", (code,)).fetchone()
    if not item:
        raise HTTPException(404, "Нет такой награды")
    if item["inside_only"] and not is_inside(m):
        raise HTTPException(403, "Только для Inside-level")
    if db.balance(con, m["tg_id"])["balance"] < item["cost"]:
        raise HTTPException(400, "Пока не хватает баллов")
    con.execute("INSERT INTO redemptions(tg_id,code,cost,created_at) VALUES(?,?,?,?)", (m["tg_id"], code, item["cost"], db.now()))
    con.commit()
    await team_notify(render(con, "t_redeem", item=item["title"], cost=item["cost"],
                             who=((m["first_name"] or "") + (" @" + m["username"] if m["username"] else "")).strip()), "t_redeem")
    return {"ok": True}


# ---------------- Random Coffee и напоминания: тексты из кабинета ----------------
# Эти функции подменяют одноименные из coffee.py, чтобы тексты брались из «Тексты бота» (файл coffee.py трогать не нужно).

async def _coffee_announce(pairs, left):
    con = db.connect()
    if not auto_on(con):
        con.close()
        return
    try:
        for a, b, ra, rb in pairs:
            for me, other, why in ((a, b, ra), (b, a, rb)):
                pair = f"{other['first_name'] or ''} {other['last_name'] or ''}".strip() + (f" (@{other['username']})" if other["username"] else "")
                await send_text(me["tg_id"], render(con, "coffee_pair", pair=pair, reason=why), tg.app_button("Открыть пару", "#coffee"),
                                key="coffee_pair", con=con)
        # тем, кому пары не хватило, ничего не отправляем: они остаются в очереди на следующую неделю
        if pairs:
            await team_notify(render(con, "t_coffee", pairs=len(pairs), left=len(left)), "t_coffee")
    finally:
        con.close()


async def _coffee_remind_feedback(con):
    if not auto_on(con):
        return
    week = coffee.week_key()
    for r in con.execute("SELECT * FROM coffee_pairs WHERE week=?", (week,)).fetchall():
        for who, met in ((r["a"], r["met_a"]), (r["b"], r["met_b"])):
            if met is None:
                await send_text(who, render(con, "coffee_ask"), tg.app_button("Оставить отзыв", "#coffee"), key="coffee_ask", con=con)


async def _event_reminders(con):
    """Напоминания записавшимся: за сутки и за час до эфира."""
    if not auto_on(con):
        return
    now = datetime.now(timezone.utc)
    for kind, delta, key in (("day", timedelta(hours=24), "event_day"), ("hour", timedelta(hours=1), "event_hour")):
        lo, hi = (now + delta - timedelta(minutes=5)).isoformat(), (now + delta + timedelta(minutes=5)).isoformat()
        for e in con.execute("SELECT * FROM events WHERE starts_at BETWEEN ? AND ?", (lo, hi)).fetchall():
            mark = f"rem:{e['id']}:{kind}"
            if db.get_setting(con, mark):
                continue
            db.set_setting(con, mark, "1")
            con.commit()
            link = Raw(f"\n\nПодключиться: {html.escape(e['join_url'])}") if e["join_url"] else ""
            text = render(con, key, title=e["title"], link=link)
            for (tg_id,) in con.execute("SELECT tg_id FROM rsvp WHERE event_id=?", (e["id"],)).fetchall():
                await send_text(tg_id, text, key=key, con=con)


_orig_make_pairs = coffee.make_pairs


def _make_pairs(con, week=None):
    if not auto_on(con):
        return []  # пока рассылки выключены, пары не составляем и ничего не отправляем
    return _orig_make_pairs(con, week)


coffee.make_pairs = _make_pairs
coffee.announce = _coffee_announce
coffee.remind_feedback = _coffee_remind_feedback
coffee.event_reminders = _event_reminders


# ---------------- запись оплат в таблицу (Google Apps Script) ----------------

try:
    from .config import env as _cfg_env
except ImportError:
    _cfg_env = os.environ.get

MSK = timezone(timedelta(hours=3))


def _post_json(url, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(r, timeout=20) as resp:
        return resp.read().decode("utf-8", "replace")


_BG = set()


def spawn(coro):
    """Запускает задачу в фоне, чтобы Tribute получил ответ сразу (он ждет не больше 10 секунд)."""
    t = asyncio.create_task(coro)
    _BG.add(t)
    t.add_done_callback(_BG.discard)


async def push_sheet(payload):
    """Отправляет строку в скрипт таблицы. Адрес скрипта хранится в .env (SHEET_WEBHOOK_URL).
    Сбой записи в таблицу не мешает выдаче доступа: команда получит предупреждение."""
    url = (_cfg_env("SHEET_WEBHOOK_URL", "") or "").strip()
    if not url:
        return
    try:
        res = await asyncio.wait_for(asyncio.to_thread(_post_json, url, payload), 30)
        if '"ok":true' not in res.replace(" ", ""):
            raise RuntimeError(f"таблица ответила: {res[:200]}")
    except Exception:
        log.exception("не удалось записать оплату в таблицу")
        try:
            _c = db.connect()
            try:
                _t = render(_c, "t_notsaved", id=payload.get("tg_id"))
            finally:
                _c.close()
            await team_notify(_t, "t_notsaved")
        except Exception:
            pass


async def send_welcome(chat_id, text, kb, photo=""):
    """Приветствие с картинкой, если команда ее задала (прислать фото боту), иначе обычным сообщением."""
    if photo:
        r = await tg._call(tg.BOT_TOKEN, "sendPhoto", {"chat_id": chat_id, "photo": photo, "caption": text,
                                                       "parse_mode": "HTML", "reply_markup": kb})
        if r and r.get("ok"):
            return
    await tg.send(chat_id, text, kb)


# ---------------- оплаты Tribute ----------------

def months_from(payload):
    pid = str(payload.get("period_id", ""))
    if pid in PERIOD_MAP:
        return int(PERIOD_MAP[pid])
    p = str(payload.get("period", "")).lower()
    for key, val in (("year", 12), ("annual", 12), ("half", 6), ("quarter", 3), ("month", 1)):
        if key in p:
            return val
    return None


def sig_ok(key, raw, sig):
    """Подпись Tribute: HMAC-SHA256 тела запроса вашим API-ключом.
    Формат записи (hex или base64) в документации не указан, поэтому принимаем оба.
    Если ключ не задан, запрос не считается подлинным."""
    if not key or not sig:
        return False
    mac = hmac.new(key.encode(), raw, hashlib.sha256).digest()
    s = sig.strip()
    if s.lower().startswith("sha256="):
        s = s[7:]
    ok_hex = hmac.compare_digest(mac.hex().encode(), s.lower().encode())
    ok_b64 = hmac.compare_digest(base64.b64encode(mac), s.encode())
    ok_b64u = hmac.compare_digest(base64.urlsafe_b64encode(mac), s.encode())
    return ok_hex or ok_b64 or ok_b64u


NEW_SUB = ("new_subscription",)
RENEW_SUB = ("renewed_subscription", "subscription_renewed")
DONATIONS = ("new_donation", "recurrent_donation", "cancelled_donation")


@app.post("/tribute/webhook")
async def tribute(req: Request, con=Depends(get_con)):
    raw = await req.body()
    sig = req.headers.get("trbt-signature", "")
    verified = 1 if sig_ok(TRIBUTE_API_KEY, raw, sig) else 0
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, "Неверный формат запроса")
    if not isinstance(data, dict):
        data = {}
    event = data.get("name", "")
    p = data.get("payload", {}) or {}
    tg_id = p.get("telegram_user_id") or p.get("user_telegram_id")
    months = months_from(p)
    price = p.get("price", p.get("amount"))  # price: сколько заплатил участник; amount: после комиссии Tribute
    amount = (price / 100) if isinstance(price, (int, float)) else None  # Tribute присылает копейки
    expires = p.get("expires_at")
    if months is None and expires:  # тариф не опознан по названию: считаем срок по дате окончания
        try:
            days = (datetime.fromisoformat(str(expires).replace("Z", "+00:00")) - datetime.now(timezone.utc)).days
            months = max(1, round(days / 30)) if days > 0 else None
        except ValueError:
            pass
    # Tribute повторяет доставку, если не получил ответ: то же событие второй раз не обрабатываем
    if verified and tg_id and expires and con.execute(
            "SELECT 1 FROM payments WHERE tg_id=? AND event=? AND expires_at=? AND verified=1",
            (tg_id, event, expires)).fetchone():
        return {"ok": True, "note": "уже обработано"}
    con.execute("INSERT INTO payments(tg_id,event,amount,currency,period_months,expires_at,verified,raw,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (tg_id, event, amount, p.get("currency"), months, expires, verified, raw.decode("utf-8", "replace"), db.now()))
    con.commit()
    if not verified:
        log.warning("Tribute: подпись не подошла (или не задан TRIBUTE_API_KEY), оплата записана, но доступ не выдан")
        spawn(team_notify(render(con, "t_badsign"), "t_badsign"))
        return JSONResponse({"ok": False}, status_code=401)
    if not tg_id:
        return {"ok": True, "note": "нет telegram_user_id"}
    tg_id = int(tg_id)
    if event in NEW_SUB or event in RENEW_SUB:
        until = expires or (datetime.now(timezone.utc) + timedelta(days=31 * (months or 1))).isoformat()
        # Inside не продается: уровень остается прежним, новый участник начинает с club
        exists = con.execute("SELECT level FROM members WHERE tg_id=?", (tg_id,)).fetchone()
        level = (exists["level"] if exists and exists["level"] else "club")
        upsert_member(con, {"id": tg_id}, status="active", paid_until=until, period_months=months,
                      last_amount=amount, level=level)
        m = db.row(con.execute("SELECT * FROM members WHERE tg_id=?", (tg_id,)).fetchone())
        # пригласивший получает заявку на баллы (решение по ней принимаете вы в кабинете)
        if m.get("source", "") and m["source"].startswith("ref_") and not con.execute(
                "SELECT 1 FROM claims WHERE ref=?", (f"invite:{tg_id}",)).fetchone():
            try:
                add_claim(con, int(m["source"][4:]), "invite", f"Пригласил(а) участника {tg_id}", ref=f"invite:{tg_id}")
                con.commit()
            except Exception:
                log.exception("не удалось начислить приглашение")
        name = html.escape(m.get("first_name") or "")
        who = f"{name} {'@' + html.escape(m['username']) if m.get('username') else ''}".strip()
        try:
            created = datetime.fromisoformat(str(data.get("created_at", "")).replace("Z", "+00:00"))
        except ValueError:
            created = datetime.now(timezone.utc)
        spawn(push_sheet({"op": "paid", "tg_id": tg_id, "username": m.get("username") or p.get("telegram_username") or "",
                          "name": name, "level": level.capitalize(), "period": p.get("period") or "", "amount": amount,
                          "paid_at": created.astimezone(MSK).strftime("%d.%m.%Y %H:%M"), "status": "активен",
                          "bot_started": bool(m.get("bot_started"))}))
        if event in NEW_SUB:
            spawn(send_welcome(tg_id, get_text(con, "welcome", m.get("first_name") or ""),
                          {"inline_keyboard": tg.app_button(get_plain(con, "btn_form"), "static/anketa.html")["inline_keyboard"]
                           + tg.app_button(get_plain(con, "btn_club"))["inline_keyboard"]},
                          pic_url(con, "welcome") or db.get_setting(con, "welcome_photo", "")))
            spawn(team_notify(render(con, "t_pay_new", who=Raw(who), id=tg_id, level=level.capitalize(), months=months or "?",
                                     amount=amount or "?", name=(m.get("first_name") or "Привет")), "t_pay_new"))
        else:
            # продление: участнику ничего не пишем, команде сообщаем коротко
            spawn(team_notify(render(con, "t_pay_renew", who=Raw(who), id=tg_id, months=months or "?", amount=amount or "?",
                                     until=str(until)[:10]), "t_pay_renew"))
    elif event in DONATIONS:
        # донат доступ в клуб не открывает
        spawn(team_notify(render(con, "t_donation", event=event, id=tg_id, amount=amount or "?"), "t_donation"))
    elif event in ("cancelled_subscription", "subscription_cancelled"):
        spawn(push_sheet({"op": "cancel", "tg_id": tg_id, "status": "отмена"}))
        spawn(team_notify(render(con, "t_cancel", id=tg_id), "t_cancel"))
    return {"ok": True}


# ---------------- бот ----------------

@app.post("/tg/webhook")
async def bot_update(req: Request):
    """Telegram ждет ответ недолго, поэтому сразу отвечаем «принято», а сообщение разбираем в фоне."""
    if req.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        raise HTTPException(403)
    upd = await req.json()
    spawn(_run_update(upd))
    return {"ok": True}


async def _run_update(upd):
    con = db.connect()
    try:
        await _handle_update(con, upd)
    except Exception:
        log.exception("сообщение боту")
    finally:
        con.close()


async def _handle_update(con, upd):
    if upd.get("callback_query"):
        try:
            await handle_callback(con, upd["callback_query"])
        except Exception:
            log.exception("кнопка в боте")
        return {"ok": True}
    msg = upd.get("message") or {}
    u, text = msg.get("from"), (msg.get("text") or "")
    if msg.get("chat", {}).get("type") in ("group", "supergroup"):
        try:
            await handle_chat_insight(con, msg)
        except Exception:
            log.exception("инсайт из чата")
        return {"ok": True}
    if not u or msg.get("chat", {}).get("type") != "private":
        return {"ok": True}
    if msg.get("photo"):
        me_row = con.execute("SELECT * FROM members WHERE tg_id=?", (int(u["id"]),)).fetchone()
        if me_row and is_team(db.row(me_row)):
            db.set_setting(con, "welcome_photo", msg["photo"][-1]["file_id"])
            con.commit()
            await tg.send(u["id"], render(con, "photo_saved"))
        return {"ok": True}
    if text.startswith("/cardname"):
        con.execute("UPDATE members SET card_ask=1 WHERE tg_id=?", (int(u["id"]),))
        con.commit()
        await send_text(u["id"], render(con, "card_ask_name"), key="card_ask_name", con=con)
        return {"ok": True}
    if text.startswith("/card"):
        try:
            await send_card(con, int(u["id"]))
        except Exception:
            log.exception("карточка месяца")
        return {"ok": True}
    if text and not text.startswith("/"):
        ask = con.execute("SELECT card_ask FROM members WHERE tg_id=?", (int(u["id"]),)).fetchone()
        if ask and ask["card_ask"]:
            nm = re.sub(r"\s+", " ", text).strip()[:60]
            if len(nm) >= 2:
                con.execute("UPDATE members SET card_name=?, card_ask=0 WHERE tg_id=?", (nm, int(u["id"])))
                con.commit()
                try:
                    await send_card(con, int(u["id"]))
                except Exception:
                    log.exception("карточка месяца")
                return {"ok": True}
    if text.startswith("/anketa") or text.startswith("/monthly"):
        monthly = text.startswith("/monthly")
        await send_text(u["id"], get_text(con, "monthly" if monthly else "anketa"),
                        tg.app_button(get_plain(con, "btn_monthly" if monthly else "btn_form"),
                                      "static/monthly.html" if monthly else "static/anketa.html"),
                        key=("monthly" if monthly else "anketa"), con=con)
        return {"ok": True}
    if text.startswith("/start"):
        arg = text.split(maxsplit=1)[1] if " " in text else ""
        exists = con.execute("SELECT source,status FROM members WHERE tg_id=?", (u["id"],)).fetchone()
        extra = {"bot_started": 1}
        if arg.startswith("ref_") and (not exists or not exists["source"]) and arg[4:] != str(u["id"]):
            extra["source"] = arg
        joined_team = False
        if arg.startswith("team_") and secrets.compare_digest(arg[5:].encode(), db.team_code(con).encode()):
            extra["role"] = "team"
            joined_team = True
        upsert_member(con, u, **extra)
        m = db.row(con.execute("SELECT * FROM members WHERE tg_id=?", (u["id"],)).fetchone())
        status = refresh_status(con, m)
        if joined_team:
            await send_text(u["id"], render(con, "team_welcome"), tg.app_button("Открыть клуб"), key="team_welcome", con=con)
            await team_notify(render(con, "t_team_added", who=((u.get("first_name") or "") + (" @" + u["username"] if u.get("username") else "")).strip(), id=u["id"]), "t_team_added")
            return {"ok": True}
        if status == "active":
            await send_text(u["id"], get_text(con, "member_start", u.get("first_name") or ""),
                            tg.app_button(get_plain(con, "btn_club")), key="member_start", con=con)
        else:
            await send_text(u["id"], get_text(con, "guest_start", link=JOIN_URL), key="guest_start", con=con)
    return {"ok": True}


# ---------------- кабинет (для вас и менеджера) ----------------

TOKENS = {}


def admin(authorization: str = Header("")):
    tok = authorization.removeprefix("Bearer ").strip()
    if not tok or tok not in TOKENS:
        raise HTTPException(401, "Войдите в кабинет")
    return TOKENS[tok]


def _pw_hash(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200000).hex()


def _pw_ok(con, pw: str) -> bool:
    """Пароль кабинета: если его меняли в кабинете, берем новый, иначе из файла настроек сервера."""
    stored = db.get_setting(con, "admin_pw_hash", "")
    if stored and "$" in stored:
        salt, hh = stored.split("$", 1)
        return hmac.compare_digest(_pw_hash(pw, salt), hh)
    return bool(ADMIN_PASSWORD) and secrets.compare_digest(pw.encode(), ADMIN_PASSWORD.strip().encode())


@app.post("/admin/api/login")
async def admin_login(req: Request, con=Depends(get_con)):
    data = await req.json()
    if not _pw_ok(con, str(data.get("password", "")).strip()):
        raise HTTPException(401, "Неверный пароль")
    tok = secrets.token_urlsafe(32)
    TOKENS[tok] = data.get("name") or "команда"
    return {"token": tok}


@app.post("/admin/api/password")
async def admin_password(req: Request, authorization: str = Header(""), _=Depends(admin), con=Depends(get_con)):
    d = await req.json()
    if not _pw_ok(con, str(d.get("old", "")).strip()):
        raise HTTPException(400, "Текущий пароль неверный")
    new = str(d.get("new", "")).strip()
    if len(new) < 8:
        raise HTTPException(400, "Новый пароль: не короче 8 знаков")
    salt = secrets.token_hex(8)
    db.set_setting(con, "admin_pw_hash", salt + "$" + _pw_hash(new, salt))
    con.commit()
    keep = authorization.removeprefix("Bearer ").strip()
    for t in [t for t in TOKENS if t != keep]:
        TOKENS.pop(t, None)
    return {"ok": True}


@app.get("/admin/api/overview")
def admin_overview(_=Depends(admin), con=Depends(get_con)):
    c = lambda q, *a: con.execute(q, a).fetchone()[0]
    return {
        "members": c("SELECT COUNT(*) FROM members WHERE status='active'"),
        "inside": c("SELECT COUNT(*) FROM members WHERE status='active' AND level='inside'"),
        "no_profile": c("SELECT COUNT(*) FROM members WHERE status='active' AND profile_done=0"),
        "pending_claims": c("SELECT COUNT(*) FROM claims WHERE status='pending'"),
        "matches": c("SELECT COUNT(*) FROM matches"),
        "coffee_week": coffee.week_key(),
        "coffee_pairs": c("SELECT COUNT(*) FROM coffee_pairs WHERE week=?", coffee.week_key()),
    }


CRM_SHARDS = ("people", "hist", "work", "cfg")


@app.get("/admin/api/crm")
def admin_crm(since: str = "", _=Depends(admin), con=Depends(get_con)):
    """Рабочие данные менеджера (люди, история, задачи, контент-план): общие для всей команды."""
    out = {}
    for r in con.execute("SELECT k,v,updated_at FROM crm_kv").fetchall():
        if r["k"] in CRM_SHARDS and (not since or r["updated_at"] > since):
            try:
                out[r["k"]] = {"data": json.loads(r["v"]), "ts": r["updated_at"]}
            except ValueError:
                pass
    return {"shards": out, "now": db.now()}


@app.put("/admin/api/crm/{shard}")
async def admin_crm_save(shard: str, req: Request, _=Depends(admin), con=Depends(get_con)):
    if shard not in CRM_SHARDS:
        raise HTTPException(404, "Нет такого раздела")
    body = await req.body()
    if len(body) > 6_000_000:
        raise HTTPException(400, "Слишком много данных")
    json.loads(body)  # убеждаемся, что это JSON
    ts = db.now()
    con.execute("INSERT INTO crm_kv(k,v,updated_at) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, updated_at=excluded.updated_at",
                (shard, body.decode("utf-8"), ts))
    con.commit()
    return {"ok": True, "ts": ts}


async def fill_names(limit=25):
    """Подтягиваем имена из Telegram тем, у кого в базе только числовой ID (например, оплатили, но еще не запускали бота)."""
    con = db.connect()
    try:
        rows = con.execute("SELECT tg_id FROM members WHERE COALESCE(first_name,'')='' AND COALESCE(username,'')='' AND COALESCE(role,'')!='team' LIMIT ?", (limit,)).fetchall()
        for r in rows:
            key = "nt:%s" % r["tg_id"]
            last = db.get_setting(con, key, "")
            try:
                if last and datetime.fromisoformat(last) > datetime.now(timezone.utc) - timedelta(hours=12):
                    continue
            except ValueError:
                pass
            db.set_setting(con, key, datetime.now(timezone.utc).isoformat())
            con.commit()
            res = await tg._call(tg.BOT_TOKEN, "getChat", {"chat_id": r["tg_id"]})
            c = (res or {}).get("result") if isinstance(res, dict) and res.get("ok") else None
            if c and (c.get("first_name") or c.get("username")):
                con.execute("UPDATE members SET first_name=?, last_name=?, username=?, updated_at=? WHERE tg_id=?",
                            (c.get("first_name") or "", c.get("last_name") or "", c.get("username") or "", db.now(), r["tg_id"]))
                con.commit()
    except Exception as e:
        log.warning("fill_names: %s", repr(e)[:200])
    finally:
        con.close()


@app.get("/admin/api/members")
async def admin_members(_=Depends(admin), con=Depends(get_con)):
    out = db.rows(con.execute("SELECT * FROM members ORDER BY created_at DESC"))
    if any(not (m.get("first_name") or m.get("username")) for m in out):
        spawn(fill_names())
    last = _last_active(con)
    for m in out:
        m["points"] = db.balance(con, m["tg_id"])
        m["last_active"] = last.get(m["tg_id"], "")
    return out


def _last_active(con):
    """Дата последнего действия участника: заявка на баллы, анкета, эфир, кофе, знакомство, обмен."""
    best = {}
    qs = ["SELECT tg_id, MAX(created_at) FROM claims GROUP BY tg_id",
          "SELECT tg_id, MAX(created_at) FROM forms GROUP BY tg_id",
          "SELECT tg_id, MAX(created_at) FROM rsvp GROUP BY tg_id",
          "SELECT tg_id, MAX(created_at) FROM event_watch GROUP BY tg_id",
          "SELECT tg_id, MAX(created_at) FROM redemptions GROUP BY tg_id",
          "SELECT a, MAX(created_at) FROM coffee_pairs GROUP BY a",
          "SELECT b, MAX(created_at) FROM coffee_pairs GROUP BY b",
          "SELECT a, MAX(created_at) FROM matches GROUP BY a",
          "SELECT b, MAX(created_at) FROM matches GROUP BY b"]
    for q in qs:
        try:
            for tg, d in con.execute(q).fetchall():
                if tg and d and d > best.get(tg, ""):
                    best[tg] = d
        except Exception:
            pass
    return best


@app.get("/admin/api/timeline/{tg_id}")
def admin_timeline(tg_id: int, _=Depends(admin), con=Depends(get_con)):
    """Автоматический журнал участника: все, что система знает о нем."""
    ev = []

    def add(d, kind, text):
        if d:
            ev.append({"d": str(d), "kind": kind, "text": text})

    def q(sql, args=()):
        try:
            return con.execute(sql, args).fetchall()
        except Exception:
            return []

    m = con.execute("SELECT * FROM members WHERE tg_id=?", (tg_id,)).fetchone()
    if m:
        add(m["created_at"], "вход", "Вошел в Клуб")
    for r in q("SELECT event, amount, currency, period_months, created_at FROM payments WHERE tg_id=? ORDER BY id", (tg_id,)):
        per = f", {r['period_months']} мес." if r["period_months"] else ""
        amt = f" {int(r['amount'])} {r['currency'] or ''}".rstrip() if r["amount"] else ""
        add(r["created_at"], "оплата", f"Оплата{amt}{per}" if "cancel" not in str(r["event"]) else "Отмена подписки")
    for r in q("SELECT kind, created_at FROM forms WHERE tg_id=?", (tg_id,)):
        add(r["created_at"], "анкета", "Заполнил(а) " + ("ежемесячную анкету" if r["kind"] == "monthly" else "анкету участника"))
    for r in q("SELECT c.points, c.status, c.created_at, c.text, p.title FROM claims c LEFT JOIN point_rules p ON p.code=c.rule_code WHERE c.tg_id=?", (tg_id,)):
        st = {"approved": "подтверждено", "rejected": "отклонено"}.get(r["status"], "ждет подтверждения")
        add(r["created_at"], "баллы", f"Баллы: {r['title'] or 'действие'}, +{r['points']} ({st})")
    for r in q("SELECT r.status, r.created_at, r.cost, s.title FROM redemptions r LEFT JOIN shop s ON s.code=r.code WHERE r.tg_id=?", (tg_id,)):
        add(r["created_at"], "подарок", f"Обмен баллов на подарок «{r['title'] or ''}», {r['cost']}")
    for r in q("SELECT created_at FROM rsvp WHERE tg_id=?", (tg_id,)):
        add(r["created_at"], "эфир", "Записался(ась) на эфир")
    for r in q("SELECT w.created_at, e.title FROM event_watch w LEFT JOIN events e ON e.id=w.event_id WHERE w.tg_id=?", (tg_id,)):
        add(r["created_at"], "эфир", f"Посмотрел(а) запись эфира «{r['title'] or ''}»")
    for r in q("SELECT created_at, week FROM coffee_pairs WHERE a=? OR b=?", (tg_id, tg_id)):
        add(r["created_at"], "кофе", f"Random Coffee: пара на неделю {r['week']}")
    for r in q("SELECT created_at FROM matches WHERE a=? OR b=?", (tg_id, tg_id)):
        add(r["created_at"], "знакомство", "Взаимная симпатия в Знакомствах")
    for r in q("SELECT title, status, created_at FROM offers WHERE tg_id=?", (tg_id,)):
        add(r["created_at"], "витрина", f"Предложение «{r['title']}»")
    ev.sort(key=lambda x: x["d"], reverse=True)
    return ev[:120]


@app.patch("/admin/api/members/{tg_id}")
async def admin_member_update(tg_id: int, req: Request, _=Depends(admin), con=Depends(get_con)):
    data = await req.json()
    allowed = {"level", "status", "paid_until", "manager", "engagement", "note", "sphere", "project", "city", "seek", "give"}
    upd = {k: v for k, v in data.items() if k in allowed}
    if upd:
        con.execute(f"UPDATE members SET {', '.join(k + '=?' for k in upd)}, updated_at=? WHERE tg_id=?", (*upd.values(), db.now(), tg_id))
        con.commit()
    return {"ok": True}


@app.get("/admin/api/claims")
def admin_claims(status: str = "pending", _=Depends(admin), con=Depends(get_con)):
    return db.rows(con.execute("""SELECT c.*, r.title, m.first_name, m.last_name, m.username FROM claims c
        LEFT JOIN point_rules r ON r.code=c.rule_code LEFT JOIN members m ON m.tg_id=c.tg_id
        WHERE c.status=? ORDER BY c.id DESC LIMIT 300""", (status,)))


@app.post("/admin/api/claims/{cid}")
async def admin_decide(cid: int, req: Request, _=Depends(admin), con=Depends(get_con)):
    data = await req.json()
    c = con.execute("SELECT points FROM claims WHERE id=?", (cid,)).fetchone()
    res = await decide_claim(con, cid, bool(data.get("approve")), int(data.get("points", c["points"])) if c else None)
    if not res:
        raise HTTPException(400, "Заявка уже обработана")
    return {"ok": True}


@app.get("/admin/api/uploads/{name}")
def admin_upload(name: str, _=Depends(admin)):
    p = (UPLOADS / name).resolve()
    if p.parent != UPLOADS.resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.post("/admin/api/events")
async def admin_event(req: Request, _=Depends(admin), con=Depends(get_con)):
    d = await req.json()
    cols = ["title", "rubric", "speaker", "starts_at", "place", "inside_only", "join_url", "description",
            "recording_url", "podcast_url", "summary", "timecodes", "clips"]
    vals = [json.dumps(d[k], ensure_ascii=False) if k in ("summary", "timecodes") and k in d else d.get(k) for k in cols]
    if d.get("id"):
        sets = ", ".join(f"{k}=COALESCE(?,{k})" for k in cols)
        con.execute(f"UPDATE events SET {sets} WHERE id=?", (*vals, d["id"])); eid = d["id"]
    else:
        vals = [v if v is not None else ("" if k not in ("inside_only", "clips") else 0) for k, v in zip(cols, vals)]
        if not vals[cols.index("place")]:
            vals[cols.index("place")] = "Zoom"
        eid = con.execute(f"INSERT INTO events({', '.join(cols)}, created_at) VALUES({', '.join('?' * len(cols))}, ?)",
                          (*vals, db.now())).lastrowid
    con.commit()
    return {"id": eid}


@app.get("/admin/api/team")
def admin_team(_=Depends(admin), con=Depends(get_con)):
    people = db.rows(con.execute("SELECT tg_id, first_name, last_name, username FROM members WHERE role='team' ORDER BY updated_at"))
    return {"link": f"https://t.me/edinenie_club_bot?start=team_{db.team_code(con)}", "people": people,
            "fixed": ADMIN_IDS}


@app.post("/admin/api/team/regenerate")
def admin_team_regen(_=Depends(admin), con=Depends(get_con)):
    return {"link": f"https://t.me/edinenie_club_bot?start=team_{db.team_code(con, regenerate=True)}"}


@app.delete("/admin/api/team/{tg_id}")
def admin_team_remove(tg_id: int, _=Depends(admin), con=Depends(get_con)):
    con.execute("UPDATE members SET role='' WHERE tg_id=?", (tg_id,))
    con.commit()
    return {"ok": True}


@app.get("/admin/api/events-list")
def admin_events_list(_=Depends(admin), con=Depends(get_con)):
    evs = db.rows(con.execute("SELECT * FROM events ORDER BY starts_at DESC LIMIT 200"))
    for e in evs:
        e["going"] = con.execute("SELECT COUNT(*) FROM rsvp WHERE event_id=?", (e["id"],)).fetchone()[0]
    return evs


@app.post("/admin/api/library")
async def admin_library(req: Request, _=Depends(admin), con=Depends(get_con)):
    d = await req.json()
    cols = ["type", "title", "author", "meta", "url", "body", "inside_only", "event_id"]
    vals = [d.get(k, 0 if k == "inside_only" else ("" if k != "event_id" else None)) for k in cols]
    lid = con.execute(f"INSERT INTO library({', '.join(cols)}, created_at) VALUES({', '.join('?' * len(cols))}, ?)", (*vals, db.now())).lastrowid
    con.commit()
    return {"id": lid}


@app.get("/admin/api/auto")
def admin_auto_get(_=Depends(admin), con=Depends(get_con)):
    return {"on": auto_on(con)}


@app.post("/admin/api/auto")
async def admin_auto_set(req: Request, _=Depends(admin), con=Depends(get_con)):
    d = await req.json()
    db.set_setting(con, "auto_on", "1" if d.get("on") else "0")
    con.commit()
    return {"on": auto_on(con)}


@app.get("/admin/api/messages")
def admin_messages(who: str = "all", q: str = "", limit: int = 300, _=Depends(admin), con=Depends(get_con)):
    con.execute("CREATE TABLE IF NOT EXISTS msg_log(id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, bot TEXT, key TEXT, text TEXT, ok INTEGER, created_at TEXT)")
    sql = ("SELECT l.*, m.first_name, m.last_name, m.username, m.role FROM msg_log l LEFT JOIN members m ON m.tg_id=l.tg_id WHERE 1=1")
    args = []
    if who == "members":
        sql += " AND (m.role IS NULL OR m.role!='team')"
    elif who == "team":
        sql += " AND m.role='team'"
    if q.strip():
        sql += " AND (lower(l.text) LIKE ? OR lower(COALESCE(m.first_name,'')||' '||COALESCE(m.last_name,'')||' '||COALESCE(m.username,'')) LIKE ?)"
        like = "%" + q.strip().lower() + "%"
        args += [like, like]
    sql += " ORDER BY l.id DESC LIMIT ?"
    args.append(max(1, min(int(limit), 1000)))
    out = []
    for r in con.execute(sql, args).fetchall():
        d = dict(r)
        d["name"] = (((d.get("first_name") or "") + " " + (d.get("last_name") or "")).strip()) or (("@" + d["username"]) if d.get("username") else f"id {d['tg_id']}")
        d["title"] = (TEXTS.get(d["key"]) or {}).get("title") or (d["key"] or "")
        out.append(d)
    return out


@app.post("/admin/api/coffee/run")
async def admin_coffee(_=Depends(admin), con=Depends(get_con)):
    if not auto_on(con):
        return {"ok": False, "note": "Автоматические рассылки выключены"}
    res = coffee.make_pairs(con)
    if not res:
        return {"ok": False, "note": "Пары на эту неделю уже составлены"}
    if not res[0]:
        return {"ok": False, "note": f"Пар не получилось: подходящих участников с анкетой пока мало ({len(res[1])}). Никому ничего не отправлено."}
    await coffee.announce(*res)
    return {"ok": True, "pairs": len(res[0]), "left": len(res[1])}


@app.get("/admin/api/payments")
def admin_payments(_=Depends(admin), con=Depends(get_con)):
    return db.rows(con.execute("SELECT id,tg_id,event,amount,period_months,expires_at,verified,created_at FROM payments ORDER BY id DESC LIMIT 300"))


# ---------------- анкеты ----------------

FORMS_SQL = """CREATE TABLE IF NOT EXISTS forms(
  id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, kind TEXT, data TEXT,
  verified INTEGER DEFAULT 0, created_at TEXT)"""


def ensure_forms(con):
    con.execute(FORMS_SQL)
    con.execute("CREATE INDEX IF NOT EXISTS forms_tg ON forms(tg_id)")


def clean_form(data):
    """Оставляем простые значения и режем длину: анкету может отправить кто угодно."""
    out = {}
    for k, v in list(data.items())[:150]:
        if isinstance(v, bool):
            out[str(k)[:60]] = v
        elif isinstance(v, (int, float)):
            out[str(k)[:60]] = v
        elif v is not None:
            out[str(k)[:60]] = str(v)[:4000]
    return out


def apply_start_form(con, u, d):
    """Перенос ответов стартовой анкеты в профиль участника (знакомства и Random Coffee берут данные оттуда)."""
    upsert_member(con, {"id": u["id"], "username": u.get("username"), "first_name": u.get("first_name"),
                        "last_name": u.get("last_name")})
    cur = db.row(con.execute("SELECT * FROM members WHERE tg_id=?", (int(u["id"]),)).fetchone())
    upd = {}
    for dst, src in (("sphere", "sphere_work"), ("project", "project"), ("city", "city"),
                     ("seek", "looking_for"), ("give", "can_give")):
        v = str(d.get(src) or "").strip()
        if v:
            upd[dst] = v
    nm = str(d.get("name") or "").strip()
    if nm and not (cur.get("first_name") or "").strip():
        parts = nm.split(None, 1)
        upd["first_name"] = parts[0]
        if len(parts) > 1:
            upd["last_name"] = parts[1]
    bd = str(d.get("birthday") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", bd):
        upd["birthday"] = bd
    rc = str(d.get("random_coffee") or "").strip()
    if rc:
        upd["coffee"] = 0 if rc.startswith("Пока без") else 1
    mf = str(d.get("meet_format") or "").strip()
    if mf:
        upd["offline"] = 0 if mf == "Онлайн" else 1
    if d.get("consent_data") in (True, "да") and not cur.get("consent_at"):
        upd["consent_at"] = db.now()
    merged = {**cur, **upd}
    upd["profile_done"] = 1 if all((str(merged.get(k) or "")).strip() for k in ("sphere", "city", "seek", "give")) else 0
    sets = ", ".join(f"{k}=?" for k in upd)
    con.execute(f"UPDATE members SET {sets}, updated_at=? WHERE tg_id=?", (*upd.values(), db.now(), int(u["id"])))
    con.commit()


@app.post("/api/form")
async def submit_form(req: Request, x_init_data: str = Header(""), con=Depends(get_con)):
    ensure_forms(con)
    raw = await req.body()
    if len(raw) > 200_000:
        raise HTTPException(413, "Слишком длинный ответ")
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, "Неверный формат запроса")
    if not isinstance(data, dict):
        raise HTTPException(400, "Неверный формат запроса")
    u = tg.check_init_data(x_init_data, max_age=86400 * 3)
    kind = "monthly" if data.get("form_type") == "monthly" else "start"
    if u:
        tg_id = int(u["id"])
    else:
        t = str(data.get("telegram_id") or "")
        tg_id = int(t) if t.isdigit() else None
    d = clean_form(data)
    con.execute("INSERT INTO forms(tg_id,kind,data,verified,created_at) VALUES(?,?,?,?,?)",
                (tg_id, kind, json.dumps(d, ensure_ascii=False), 1 if u else 0, db.now()))
    con.commit()
    if u and kind == "start":
        try:
            apply_start_form(con, u, d)
        except Exception:
            log.exception("не удалось перенести анкету в профиль")
    who = str(d.get("name") or (u or {}).get("first_name") or "без имени")
    tail = "" if u else " (без подтверждения Telegram, в профиль не перенесена)"
    spawn(team_notify(render(con, "t_form", kind=("Ежемесячная" if kind == "monthly" else "Стартовая"), who=who, id=tg_id or "?", tail=tail), "t_form"))
    if u and kind in ("monthly", "start"):
        spawn(send_card_bg(tg_id))
    return {"ok": True}


@app.get("/admin/api/forms")
def admin_forms(_=Depends(admin), con=Depends(get_con)):
    ensure_forms(con)
    out = []
    for r in con.execute("SELECT f.*, m.username, m.first_name, m.last_name, m.level, m.status FROM forms f LEFT JOIN members m ON m.tg_id=f.tg_id "
                         "ORDER BY f.id DESC LIMIT 500").fetchall():
        x = dict(r)
        try:
            x["data"] = json.loads(x["data"] or "{}")
        except ValueError:
            x["data"] = {}
        out.append(x)
    return out


def _route_value(con, key):
    v = db.get_setting(con, "route:" + key, None)
    if v is None or v == "":
        return [] if TEXTS.get(key, {}).get("route0") == "none" else None
    try:
        return json.loads(v)
    except ValueError:
        return None


@app.put("/admin/api/texts/{key}/route")
async def admin_text_route(key: str, req: Request, _=Depends(admin), con=Depends(get_con)):
    if key not in TEXTS or TEXTS[key].get("group") != "team":
        raise HTTPException(404, "Для этого сообщения получателей выбрать нельзя")
    d = await req.json()
    to = d.get("to")
    db.set_setting(con, "route:" + key, json.dumps(None if to is None else [int(i) for i in to]))
    con.commit()
    return {"ok": True}


@app.get("/admin/api/texts")
def admin_texts(_=Depends(admin), con=Depends(get_con)):
    out = []
    for k, t in TEXTS.items():
        cur = db.get_setting(con, "text:" + k, None)
        pic = db.get_setting(con, "pic:" + k, "")
        out.append({"key": k, "title": t["title"], "hint": t["hint"], "max": t["max"], "plain": bool(t.get("plain")),
                    "group": t.get("group") or ("bot" if t.get("plain") or k in ("welcome", "member_start", "guest_start", "anketa", "monthly") else "members"),
                    "vars": t.get("vars", ""), "can_pic": not t.get("plain"), "limit": (PIC_LIMIT if pic and (BOTPICS / pic).exists() else t["max"]),
                    "route": (None if t.get("group") != "team" else _route_value(con, k)), "route_own": t.get("group") == "team" and k != "t_digest_claim",
                    "pic": (f"/botpic/{pic}" if pic and (BOTPICS / pic).exists() else ""),
                    "value": cur if cur and cur.strip() else t["default"], "default": t["default"], "custom": bool(cur and cur.strip())})
    return out


@app.put("/admin/api/texts/{key}")
async def admin_text_save(key: str, req: Request, _=Depends(admin), con=Depends(get_con)):
    if key not in TEXTS:
        raise HTTPException(404, "Нет такого текста")
    data = await req.json()
    v = str(data.get("value", "")).replace("\r\n", "\n").strip()
    if len(v) > TEXTS[key]["max"]:
        raise HTTPException(400, f"Слишком длинно: {len(v)} знаков, можно до {TEXTS[key]['max']}")
    if db.get_setting(con, "pic:" + key, "") and len(v.replace("**", "")) > PIC_LIMIT:
        raise HTTPException(400, f"С картинкой текст должен быть не длиннее {PIC_LIMIT} знаков, сейчас {len(v.replace('**', ''))}. Сократите текст или уберите картинку.")
    db.set_setting(con, "text:" + key, v)
    con.commit()
    if key in ("bot_about", "bot_short"):
        spawn(setup_bot(0))
    return {"ok": True}


@app.get("/admin/api/digest")
def admin_digest(_=Depends(admin), con=Depends(get_con)):
    return {"on": db.get_setting(con, "digest_on", "1") == "1", "hour": int(db.get_setting(con, "digest_hour", "9") or 9)}


@app.put("/admin/api/digest")
async def admin_digest_save(req: Request, _=Depends(admin), con=Depends(get_con)):
    d = await req.json()
    hour = max(0, min(23, int(d.get("hour", 9))))
    db.set_setting(con, "digest_on", "1" if d.get("on") else "0")
    db.set_setting(con, "digest_hour", str(hour))
    con.commit()
    return {"ok": True}


@app.post("/admin/api/stats/send")
async def admin_stats_send(_=Depends(admin), con=Depends(get_con)):
    return {"sent": await send_stats(con)}


@app.post("/admin/api/digest/send")
async def admin_digest_send(_=Depends(admin), con=Depends(get_con)):
    n = await send_digest(con)
    return {"sent": n}


# ---------------- карточка месяца ----------------
CARDS = UPLOADS.parent / "cards"


def _monthly_scores(con, tg_id):
    """Две последние ежемесячные анкеты с полными оценками (новая, предыдущая) и оценки стартовой анкеты."""
    ensure_forms(con)
    mon = []
    for r in con.execute("SELECT data FROM forms WHERE tg_id=? AND kind='monthly' ORDER BY id DESC LIMIT 8", (tg_id,)).fetchall():
        sc = card.scores_from_form(json.loads(r["data"] or "{}"))
        if sc:
            mon.append(sc)
    base = None
    for r in con.execute("SELECT data FROM forms WHERE tg_id=? AND kind='start' ORDER BY id DESC LIMIT 3", (tg_id,)).fetchall():
        base = card.scores_from_form(json.loads(r["data"] or "{}"))
        if base:
            break
    if not mon:  # после стартовой анкеты карточка собирается по ее оценкам, это точка отсчета
        return base, None, base
    prev = mon[1] if len(mon) > 1 else base
    return mon[0], prev, base


def _month_no(m):
    try:
        c = datetime.fromisoformat(str(m.get("created_at") or "")[:19])
        n = datetime.now()
        return max(1, (n.year - c.year) * 12 + n.month - c.month + 1)
    except ValueError:
        return 1


async def send_card(con, tg_id):
    """Собирает карточку месяца участника и отправляет ее в бот. Если имя для подписи еще не задано, сначала спрашивает его."""
    row = con.execute("SELECT * FROM members WHERE tg_id=?", (tg_id,)).fetchone()
    if not row:
        return False
    m = db.row(row)
    cur, prev, base = _monthly_scores(con, tg_id)
    if not cur:
        await send_text(tg_id, render(con, "card_wait"), key="card_wait", con=con)
        return False
    if not (m.get("card_name") or "").strip():
        con.execute("UPDATE members SET card_ask=1 WHERE tg_id=?", (tg_id,))
        con.commit()
        await send_text(tg_id, render(con, "card_ask_name"), key="card_ask_name", con=con)
        return True
    data = card.build_card_data(cur, prev, m.get("level") or "club", _month_no(m), m["card_name"], base=base)
    png = await asyncio.to_thread(card.render_card, data)
    CARDS.mkdir(parents=True, exist_ok=True)
    fn = f"{tg_id}-{secrets.token_urlsafe(12)}.png"
    (CARDS / fn).write_bytes(png)
    for old in sorted(CARDS.glob(f"{tg_id}-*.png"), key=lambda p: p.stat().st_mtime)[:-5]:
        old.unlink(missing_ok=True)
    caption = render(con, "card_ready")
    # 1) картинка уходит через скрипт Google файлом (если скрипт обновлен), 2) иначе Telegram скачивает ее по ссылке
    r = await tg._call(tg.BOT_TOKEN, "sendPhoto", {"chat_id": tg_id, "caption": caption, "parse_mode": "HTML"}, file=("photo", png))
    if not (r and r.get("ok")):
        for attempt in range(2):
            r = await tg._call(tg.BOT_TOKEN, "sendPhoto", {"chat_id": tg_id, "photo": f"{PUBLIC_URL}/cardpic/{fn}",
                                                            "caption": caption, "parse_mode": "HTML"})
            if r and r.get("ok"):
                break
            log.warning("карточка: отправка по ссылке %s не удалась: %s", attempt + 1, str(r)[:200])
            await asyncio.sleep(3)
    ok = bool(r and r.get("ok"))
    if not ok:
        # Telegram не смог сам скачать картинку: даем кнопку, по ней карточка открывается в приложении и сохраняется
        kb = {"inline_keyboard": [[{"text": "Открыть карточку", "web_app": {"url": f"{PUBLIC_URL}/cardview/{fn}"}}]]}
        r2 = await tg.send(tg_id, caption, button=kb)
        ok = bool(r2 and r2.get("ok"))
    _msg_log(tg_id, "[картинка] " + caption, "card_ready", ok, "main")
    return ok


async def send_card_bg(tg_id):
    con = db.connect()
    try:
        await send_card(con, tg_id)
    except Exception:
        log.exception("карточка месяца")
    finally:
        con.close()


@app.api_route("/cardpic/{name}", methods=["GET", "HEAD"])
def cardpic(name: str):
    p = (CARDS / name).resolve()
    if p.parent != CARDS.resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png")


@app.get("/cardview/{name}")
def cardview(name: str):
    """Страница с карточкой: открывается из бота, картинку можно сохранить (нажать и удерживать)."""
    p = (CARDS / name).resolve()
    if p.parent != CARDS.resolve() or not p.exists():
        raise HTTPException(404)
    html = ("<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'><title>Карточка месяца</title>"
            "<style>body{margin:0;background:#fff;font-family:system-ui,sans-serif;text-align:center;color:#222}"
            "img{display:block;width:100%;max-width:460px;margin:0 auto}"
            "p{margin:14px 20px;font-size:15px;line-height:1.4}"
            "a{display:inline-block;margin:6px 0 24px;padding:12px 22px;border-radius:12px;background:#222;color:#fff;text-decoration:none}</style></head><body>"
            f"<img src='/cardpic/{name}' alt='Карточка месяца'>"
            "<p>Чтобы сохранить: нажмите на картинку и удерживайте, затем выберите «Сохранить».</p>"
            f"<a href='/cardpic/{name}' target='_blank'>Открыть картинку отдельно</a></body></html>")
    return HTMLResponse(html)


@app.get("/botpic/{name}")
def botpic(name: str):
    p = (BOTPICS / name).resolve()
    if p.parent != BOTPICS.resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


@app.put("/admin/api/texts/{key}/pic")
async def admin_text_pic(key: str, req: Request, _=Depends(admin), con=Depends(get_con)):
    if key not in TEXTS or TEXTS[key].get("plain"):
        raise HTTPException(404, "К этому тексту картинку прикрепить нельзя")
    cur = text_raw(con, key)
    if len(cur.replace("**", "")) > PIC_LIMIT:
        raise HTTPException(400, f"Сначала сократите текст до {PIC_LIMIT} знаков (сейчас {len(cur.replace('**', ''))}): с картинкой он должен уместиться в одно сообщение.")
    data = await req.json()
    raw = str(data.get("image", ""))
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        body = base64.b64decode(raw, validate=False)
    except Exception:
        raise HTTPException(400, "Не получилось прочитать картинку")
    if len(body) < 200 or len(body) > 8_000_000:
        raise HTTPException(400, "Картинка пустая или слишком большая (до 8 МБ)")
    BOTPICS.mkdir(parents=True, exist_ok=True)
    name = f"{key}-{secrets.token_hex(4)}.jpg"
    (BOTPICS / name).write_bytes(body)
    old = db.get_setting(con, "pic:" + key, "")
    db.set_setting(con, "pic:" + key, name)
    con.commit()
    if old and old != name:
        try:
            (BOTPICS / old).unlink()
        except OSError:
            pass
    return {"ok": True, "pic": f"/botpic/{name}"}


@app.delete("/admin/api/texts/{key}/pic")
async def admin_text_pic_del(key: str, _=Depends(admin), con=Depends(get_con)):
    old = db.get_setting(con, "pic:" + key, "")
    db.set_setting(con, "pic:" + key, "")
    con.commit()
    if old:
        try:
            (BOTPICS / old).unlink()
        except OSError:
            pass
    return {"ok": True}


@app.delete("/admin/api/texts/{key}")
async def admin_text_reset(key: str, _=Depends(admin), con=Depends(get_con)):
    if key not in TEXTS:
        raise HTTPException(404, "Нет такого текста")
    db.set_setting(con, "text:" + key, "")
    con.commit()
    if key in ("bot_about", "bot_short"):
        spawn(setup_bot(0))
    return {"ok": True}


# ---------------- календарь событий ----------------

CAL_SQL = """CREATE TABLE IF NOT EXISTS cal_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, icon TEXT DEFAULT '', title TEXT, date_from TEXT, date_to TEXT DEFAULT '',
  when_text TEXT DEFAULT '', place TEXT DEFAULT '', body TEXT DEFAULT '', perk TEXT DEFAULT '', promo TEXT DEFAULT '',
  link TEXT DEFAULT '', contact TEXT DEFAULT '', active INTEGER DEFAULT 1, own INTEGER DEFAULT 0, created_at TEXT)"""

CAL_INTRO = ("Друзья, собрали ближайшие эфиры, встречи, вечеринки, ретриты и путешествия от наших друзей, "
             "которые мы рекомендуем участникам клуба. Сохраняйте даты и выбирайте, где встречаемся!")
CAL_OUTRO = ("EDINENIE становится больше, чем клубом и отдельными мероприятиями. Мы собираем среду, в которой можно "
             "встречаться со своими, путешествовать вместе, развиваться, танцевать, создавать новые связи, проекты "
             "и проживать сильные события рядом с людьми, с которыми хочется идти дальше. По каждому событию будем "
             "отдельно публиковать подробности, программу и специальные условия для участников клуба.")

# icon, title, date_from, date_to, when_text, place, body, perk, promo, link, contact
CAL_SEED = [
    ("🔥", "Эфир с Владом Митьковским", "2026-11-10", "", "10 ноября", "Онлайн | EDINENIE",
     "Новая встреча с Владом Митьковским для участников клуба. Тему и подробности эфира расскажем совсем скоро.", "", "", "", ""),
    ("🌿", "«ВЫДОХ» с Игорем Будниковым", "2026-11-19", "2026-11-23", "19–23 ноября", "Подмосковье",
     "Несколько дней тишины, медитации и перезагрузки с Игорем Будниковым. Формат для тех, кому хочется остановиться, "
     "выдохнуть, восстановиться и вернуться к себе.", "", "", "", "@darodionova"),
    ("🔥", "Будниковы: DANA DANCE", "2026-11-24", "", "24 ноября", "Москва",
     "Повторяем нашу большую совместную вечеринку, и в этот раз готовим формат еще мощнее и масштабнее! Новый музыкальный "
     "сет, танец, много живого общения, знакомств и встреч двух сообществ.\n\nЕсли по вашей рекомендации придут +2 человека, "
     "вы получите в подарок книгу Игоря Будникова «Возвращение Домой». Подарок вручат прямо на вечеринке.",
     "Скидка 500 ₽ для участников клуба", "DANCE", "https://welcomebackhome.academy/dana-dance-november", ""),
    ("🌎", "PERUKUA «Голос Матери Земли»", "2026-11-25", "", "25 ноября", "Москва | Центр исполнительских искусств",
     "Уникальный живой интерактивный концерт-семинар PERUKUA. «Голос Матери Земли» это соединение музыки, песен, "
     "целительных саундтреков и коротких практик, возвращающих в тело, спокойствие и контакт с собой.",
     "Скидка 10% на билеты для участников клуба", "Edin10", "https://peruquois.ru/mother", ""),
    ("✈️", "«Загадочная Бирма»", "2026-11-25", "2026-12-04", "25 ноября – 4 декабря", "Мьянма | экспедиция с Джеффри Оливером",
     "Большое путешествие в Бирму с Джеффри Оливером. Новый для нас формат: не просто мероприятие, а настоящее совместное "
     "исследование страны, культуры и себя. Добавляем его в направление путешествий EDINENIE.", "", "", "", "@darodionova"),
    ("❤️", "«Лаборатория близости»", "2027-02-18", "2027-02-25", "18–25 февраля", "Панган | Игорь и Наташа Будниковы",
     "Отдельная программа, посвященная близости, отношениям и более глубокому контакту с собой и другим человеком.", "", "", "", "@darodionova"),
    ("🏔", "Шерегеш с Будниковыми", "2027-03-06", "2027-03-13", "6–13 марта", "Alpen Club, сектор А",
     "Неделя вместе в горах. В программе: лыжи и сноуборд, практики с Игорем и Натальей, мастермайнды, знакомства и сильное "
     "окружение, баня, après-ski, Dana Dance, совместный отдых и много живого общения.", "", "", "", "@darodionova"),
]


def ensure_cal(con):
    con.execute(CAL_SQL)
    if db.get_setting(con, "cal_seeded", "") != "1":
        for it in CAL_SEED:
            con.execute("INSERT INTO cal_events(icon,title,date_from,date_to,when_text,place,body,perk,promo,link,contact,created_at) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (*it, db.now()))
        con.execute("UPDATE cal_events SET own=1 WHERE title LIKE 'Эфир с Владом%'")
        db.set_setting(con, "cal_seeded", "1")
        con.commit()


def msk_today():
    return datetime.now(timezone(timedelta(hours=3))).date().isoformat()


@app.get("/api/calendar")
def calendar_public(m=Depends(member), con=Depends(get_con)):
    ensure_cal(con)
    today = msk_today()
    items = db.rows(con.execute(
        "SELECT * FROM cal_events WHERE active=1 AND COALESCE(NULLIF(date_to,''),date_from)>=? ORDER BY date_from, id", (today,)))
    marks = []
    y0 = int(today[:4])
    lo, hi = f"{y0}-01-01", f"{y0 + 1}-12-31"
    for r in db.rows(con.execute("SELECT id,title,date_from,date_to,own FROM cal_events WHERE active=1 AND date_from<=? AND COALESCE(NULLIF(date_to,''),date_from)>=?", (hi, lo))):
        try:
            a = datetime.strptime(r["date_from"], "%Y-%m-%d").date()
            b = datetime.strptime(r["date_to"] or r["date_from"], "%Y-%m-%d").date()
        except Exception:
            continue
        for i in range(min((b - a).days, 60) + 1):
            marks.append({"d": (a + timedelta(days=i)).isoformat(), "k": "cal", "id": r["id"], "t": r["title"], "own": 1 if r.get("own") else 0})
    for r in db.rows(con.execute("SELECT id,title,starts_at FROM events WHERE substr(starts_at,1,10)>=? AND substr(starts_at,1,10)<=?", (lo, hi))):
        marks.append({"d": str(r["starts_at"])[:10], "k": "ev", "id": r["id"], "t": r["title"], "own": 1})
    return {"intro": db.get_setting(con, "cal_intro", "") or CAL_INTRO,
            "outro": db.get_setting(con, "cal_outro", "") or CAL_OUTRO, "items": items, "marks": marks}


@app.get("/admin/api/calendar")
def admin_calendar(_=Depends(admin), con=Depends(get_con)):
    ensure_cal(con)
    return {"intro": db.get_setting(con, "cal_intro", "") or CAL_INTRO,
            "outro": db.get_setting(con, "cal_outro", "") or CAL_OUTRO,
            "today": msk_today(),
            "items": db.rows(con.execute("SELECT * FROM cal_events ORDER BY date_from DESC, id DESC LIMIT 300"))}


def _day(v):
    v = str(v or "").strip()
    if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise HTTPException(400, "Дата должна быть в формате ГГГГ-ММ-ДД")
    return v


@app.post("/admin/api/calendar")
async def admin_calendar_save(req: Request, _=Depends(admin), con=Depends(get_con)):
    ensure_cal(con)
    d = await req.json()
    title = str(d.get("title", "")).strip()[:200]
    date_from = _day(d.get("date_from"))
    if not title or not date_from:
        raise HTTPException(400, "Нужны название и дата начала")
    link = str(d.get("link", "")).strip()[:500]
    if link and not re.match(r"https?://", link):
        raise HTTPException(400, "Ссылка должна начинаться с https://")
    vals = (str(d.get("icon", "")).strip()[:8], title, date_from, _day(d.get("date_to")),
            str(d.get("when_text", "")).strip()[:80], str(d.get("place", "")).strip()[:160],
            str(d.get("body", "")).replace("\r\n", "\n").strip()[:3000], str(d.get("perk", "")).strip()[:200],
            str(d.get("promo", "")).strip()[:60], link, str(d.get("contact", "")).strip()[:60],
            0 if d.get("active") in (0, False, "0") else 1, 1 if str(d.get("own")) in ("1", "True", "true") else 0)
    cols = "icon=?,title=?,date_from=?,date_to=?,when_text=?,place=?,body=?,perk=?,promo=?,link=?,contact=?,active=?,own=?"
    if d.get("id"):
        con.execute(f"UPDATE cal_events SET {cols} WHERE id=?", (*vals, int(d["id"])))
        eid = int(d["id"])
    else:
        eid = con.execute("INSERT INTO cal_events(icon,title,date_from,date_to,when_text,place,body,perk,promo,link,contact,active,own,created_at) "
                          "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*vals, db.now())).lastrowid
    con.commit()
    return {"id": eid}


@app.delete("/admin/api/calendar/{eid}")
def admin_calendar_delete(eid: int, _=Depends(admin), con=Depends(get_con)):
    ensure_cal(con)
    con.execute("DELETE FROM cal_events WHERE id=?", (eid,))
    con.commit()
    return {"ok": True}


@app.put("/admin/api/calendar-texts")
async def admin_calendar_texts(req: Request, _=Depends(admin), con=Depends(get_con)):
    d = await req.json()
    for k in ("intro", "outro"):
        v = str(d.get(k, "")).replace("\r\n", "\n").strip()
        if len(v) > 1500:
            raise HTTPException(400, "Слишком длинный текст")
        db.set_setting(con, "cal_" + k, v)
    con.commit()
    return {"ok": True}


# ---------------- предложения участников ----------------

OFFERS_SQL = ["""CREATE TABLE IF NOT EXISTS offers(
  id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, title TEXT, body TEXT DEFAULT '', price TEXT DEFAULT '',
  barter INTEGER DEFAULT 0, barter_for TEXT DEFAULT '', status TEXT DEFAULT 'pending', approved_at TEXT, slot TEXT DEFAULT 'invite', created_at TEXT)""",
              """CREATE TABLE IF NOT EXISTS offer_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT, offer_id INTEGER, from_tg INTEGER, kind TEXT, message TEXT DEFAULT '', created_at TEXT)"""]


def ensure_offers(con):
    for q in OFFERS_SQL:
        con.execute(q)


def person_name(m):
    n = " ".join(x for x in (m.get("first_name"), m.get("last_name")) if x).strip()
    return n or (("@" + m["username"]) if m.get("username") else str(m.get("tg_id") or ""))


OFFER_DAYS = 30  # один приглашенный участник = 30 дней размещения одного предложения


def offer_cutoff():
    return (datetime.now(timezone.utc) - timedelta(days=OFFER_DAYS)).isoformat()


def offer_slots(con, m):
    """Места на витрине: 1 приглашенный и оплативший участник = 1 предложение на месяц.
    Годовой тариф дает еще одно постоянное место без приглашений. Команда не ограничена."""
    if is_team(m):
        return {"invited": 0, "used": 0, "free": 99, "team": True, "year": False, "year_free": False}
    invited = con.execute("SELECT COUNT(*) FROM claims WHERE tg_id=? AND rule_code='invite' AND status!='rejected'", (m["tg_id"],)).fetchone()[0]
    used = con.execute("SELECT COUNT(*) FROM offers WHERE tg_id=? AND COALESCE(slot,'invite')!='year' AND (status='pending' OR approved_at IS NOT NULL)", (m["tg_id"],)).fetchone()[0]
    year = is_year(m)
    busy = con.execute("SELECT COUNT(*) FROM offers WHERE tg_id=? AND slot='year' AND status IN ('pending','active')", (m["tg_id"],)).fetchone()[0]
    year_free = bool(year and not busy)
    return {"invited": invited, "used": used, "free": max(0, invited - used) + (1 if year_free else 0), "team": False,
            "year": year, "year_free": year_free}


def offer_until(approved_at):
    try:
        return (datetime.fromisoformat(approved_at) + timedelta(days=OFFER_DAYS)).astimezone(timezone(timedelta(hours=3))).date().isoformat()
    except Exception:
        return ""


@app.get("/api/offers")
def offers_list(m=Depends(member), con=Depends(get_con)):
    ensure_offers(con)
    rows = db.rows(con.execute(
        "SELECT o.*, m.first_name, m.last_name, m.sphere, m.city, m.status AS a_status, m.period_months AS a_pm FROM offers o LEFT JOIN members m ON m.tg_id=o.tg_id "
        "WHERE o.status IN ('active','pending') OR o.tg_id=? ORDER BY o.id DESC LIMIT 300", (m["tg_id"],)))
    asked = {(r[0], r[1]) for r in con.execute("SELECT offer_id, kind FROM offer_requests WHERE from_tg=?", (m["tg_id"],))}
    cut = offer_cutoff()
    out = []
    for o in rows:
        mine = o["tg_id"] == m["tg_id"]
        if o["status"] == "hidden":
            continue
        st = o["status"]
        yr = (o.get("slot") == "year")
        if st == "active":
            if yr:
                if not is_year({"status": o["a_status"], "period_months": o["a_pm"]}):
                    st = "expired"
            elif not o["approved_at"] or o["approved_at"] < cut:
                st = "expired"
        if not mine and st != "active":
            continue
        out.append({"id": o["id"], "title": o["title"], "body": o["body"], "price": o["price"], "barter": bool(o["barter"]),
                    "barter_for": o["barter_for"], "status": st, "mine": mine, "year": yr,
                    "until": "" if yr else (offer_until(o["approved_at"]) if o["approved_at"] else ""),
                    "author": person_name(o), "sphere": o["sphere"] or "", "city": o["city"] or "",
                    "asked_buy": (o["id"], "buy") in asked, "asked_barter": (o["id"], "barter") in asked})
    return {"items": out, "slots": offer_slots(con, m), "days": OFFER_DAYS}


@app.post("/api/offers")
async def offer_create(req: Request, m=Depends(member), con=Depends(get_con)):
    ensure_offers(con)
    d = await req.json()
    title = str(d.get("title", "")).strip()[:100]
    body = str(d.get("body", "")).replace("\r\n", "\n").strip()[:800]
    price = str(d.get("price", "")).strip()[:120]
    barter = 1 if d.get("barter") else 0
    barter_for = str(d.get("barter_for", "")).strip()[:300] if barter else ""
    if not title or not body:
        raise HTTPException(400, "Напишите название и что именно вы предлагаете")
    if not price and not barter:
        raise HTTPException(400, "Укажите специальную цену для клуба или отметьте, что открыты к бартеру")
    if offer_slots(con, m)["free"] < 1:
        raise HTTPException(400, "Нет свободного места на витрине. Пригласите в клуб друга: один оплативший участник дает месяц размещения одного предложения.")
    slot = "year" if offer_slots(con, m)["year_free"] else "invite"
    oid = con.execute("INSERT INTO offers(tg_id,title,body,price,barter,barter_for,status,slot,created_at) VALUES(?,?,?,?,?,?,'pending',?,?)",
                      (m["tg_id"], title, body, price, barter, barter_for, slot, db.now())).lastrowid
    con.commit()
    spawn(team_notify(render(con, "t_offer_new", title=title, who=person_name(m)), "t_offer_new"))
    return {"id": oid}


@app.delete("/api/offers/{oid}")
def offer_hide(oid: int, m=Depends(member), con=Depends(get_con)):
    ensure_offers(con)
    con.execute("UPDATE offers SET status='hidden' WHERE id=? AND tg_id=?", (oid, m["tg_id"]))
    con.commit()
    return {"ok": True}


@app.post("/api/offers/{oid}/request")
async def offer_request(oid: int, req: Request, m=Depends(member), con=Depends(get_con)):
    ensure_offers(con)
    d = await req.json()
    kind = "barter" if d.get("kind") == "barter" else "buy"
    msg = str(d.get("message", "")).strip()[:500]
    o = con.execute("SELECT * FROM offers WHERE id=? AND status='active' AND (slot='year' OR approved_at>=?)", (oid, offer_cutoff())).fetchone()
    if not o:
        raise HTTPException(404, "Предложение уже недоступно")
    if o["tg_id"] == m["tg_id"]:
        raise HTTPException(400, "Это ваше предложение")
    if kind == "barter" and not o["barter"]:
        raise HTTPException(400, "Автор не рассматривает бартер")
    if kind == "barter" and not msg:
        raise HTTPException(400, "Напишите, что можете предложить взамен")
    if con.execute("SELECT 1 FROM offer_requests WHERE offer_id=? AND from_tg=? AND kind=?", (oid, m["tg_id"], kind)).fetchone():
        raise HTTPException(400, "Вы уже отправили заявку")
    con.execute("INSERT INTO offer_requests(offer_id,from_tg,kind,message,created_at) VALUES(?,?,?,?,?)", (oid, m["tg_id"], kind, msg, db.now()))
    con.commit()
    who = f'<a href="tg://user?id={m["tg_id"]}">{html.escape(person_name(m))}</a>' + (f' (@{html.escape(m["username"])})' if m.get("username") else "")
    what = "хочет купить по специальной цене" if kind == "buy" else "предлагает бартер"
    text = render(con, "offer_request", title=o["title"], who=Raw(who), what=what, message=msg or "")
    spawn(send_text(o["tg_id"], text, key="offer_request"))
    spawn(team_notify(render(con, "t_offer_req", title=o["title"], who=person_name(m), kind=("покупка" if kind == "buy" else "бартер")), "t_offer_req"))
    return {"ok": True}


def ensure_shop(con):
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(shop)").fetchall()]
        if "img" not in cols:
            con.execute("ALTER TABLE shop ADD COLUMN img TEXT DEFAULT ''")
            con.commit()
    except Exception:
        pass


def shop_img_url(it):
    n = it.get("img") or ""
    return f"/botpic/{n}" if n and (BOTPICS / n).exists() else ""


SHOP_ICONS = ["gift", "house", "talk", "rec", "note", "pod", "guide", "case", "clip"]


@app.get("/admin/api/shop")
def admin_shop(_=Depends(admin), con=Depends(get_con)):
    ensure_shop(con)
    items = db.rows(con.execute("SELECT * FROM shop ORDER BY active DESC, cost, title"))
    cnt = {r["code"]: r["n"] for r in con.execute("SELECT code, COUNT(*) AS n FROM redemptions GROUP BY code")}
    for it in items:
        it["requests"] = cnt.get(it["code"], 0)
        it["img_url"] = shop_img_url(it)
    return items


@app.post("/admin/api/shop")
async def admin_shop_save(req: Request, _=Depends(admin), con=Depends(get_con)):
    ensure_shop(con)
    d = await req.json()
    title = (d.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "Напишите название подарка")
    try:
        cost = int(d.get("cost") or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "Стоимость должна быть числом")
    if cost < 0:
        raise HTTPException(400, "Стоимость не может быть отрицательной")
    icon = d.get("icon") if d.get("icon") in SHOP_ICONS else "gift"
    code = (d.get("code") or "").strip() or "g" + uuid.uuid4().hex[:8]
    vals = (title, (d.get("hint") or "").strip(), cost, 1 if d.get("inside_only") else 0, icon, 0 if d.get("active") is False or d.get("active") == 0 else 1)
    if con.execute("SELECT 1 FROM shop WHERE code=?", (code,)).fetchone():
        con.execute("UPDATE shop SET title=?, hint=?, cost=?, inside_only=?, icon=?, active=? WHERE code=?", vals + (code,))
    else:
        con.execute("INSERT INTO shop(title,hint,cost,inside_only,icon,active,code) VALUES(?,?,?,?,?,?,?)", vals + (code,))
    con.commit()
    return {"ok": True, "code": code}


@app.put("/admin/api/shop/{code}/img")
async def admin_shop_img(code: str, req: Request, _=Depends(admin), con=Depends(get_con)):
    ensure_shop(con)
    row = con.execute("SELECT img FROM shop WHERE code=?", (code,)).fetchone()
    if not row:
        raise HTTPException(404, "Нет такого подарка")
    raw = str((await req.json()).get("image", ""))
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        body = base64.b64decode(raw, validate=False)
    except Exception:
        raise HTTPException(400, "Не получилось прочитать картинку")
    if len(body) < 200 or len(body) > 8_000_000:
        raise HTTPException(400, "Картинка пустая или слишком большая (до 8 МБ)")
    BOTPICS.mkdir(parents=True, exist_ok=True)
    name = f"shop-{secrets.token_hex(6)}.jpg"
    (BOTPICS / name).write_bytes(body)
    old = row["img"] or ""
    con.execute("UPDATE shop SET img=? WHERE code=?", (name, code))
    con.commit()
    if old and old != name:
        try:
            (BOTPICS / old).unlink()
        except OSError:
            pass
    return {"ok": True, "img_url": f"/botpic/{name}"}


@app.delete("/admin/api/shop/{code}/img")
def admin_shop_img_del(code: str, _=Depends(admin), con=Depends(get_con)):
    ensure_shop(con)
    row = con.execute("SELECT img FROM shop WHERE code=?", (code,)).fetchone()
    if row and row["img"]:
        try:
            (BOTPICS / row["img"]).unlink()
        except OSError:
            pass
    con.execute("UPDATE shop SET img='' WHERE code=?", (code,))
    con.commit()
    return {"ok": True}


@app.delete("/admin/api/shop/{code}")
def admin_shop_delete(code: str, _=Depends(admin), con=Depends(get_con)):
    if con.execute("SELECT 1 FROM redemptions WHERE code=?", (code,)).fetchone():
        con.execute("UPDATE shop SET active=0 WHERE code=?", (code,))
        hidden = True
    else:
        con.execute("DELETE FROM shop WHERE code=?", (code,))
        hidden = False
    con.commit()
    return {"ok": True, "hidden": hidden}


@app.get("/admin/api/redemptions")
def admin_redemptions(status: str = "pending", _=Depends(admin), con=Depends(get_con)):
    rows = db.rows(con.execute(
        "SELECT r.*, s.title, m.first_name, m.last_name, m.username FROM redemptions r "
        "LEFT JOIN shop s ON s.code=r.code LEFT JOIN members m ON m.tg_id=r.tg_id "
        "WHERE r.status=? ORDER BY r.id DESC LIMIT 200", (status,)))
    for r in rows:
        r["who"] = person_name(r)
    return rows


@app.post("/admin/api/redemptions/{rid}")
async def admin_redemption_decide(rid: int, req: Request, _=Depends(admin), con=Depends(get_con)):
    st = (await req.json()).get("status")
    if st not in ("done", "rejected"):
        raise HTTPException(400, "Неверный статус")
    if not con.execute("SELECT 1 FROM redemptions WHERE id=?", (rid,)).fetchone():
        raise HTTPException(404, "Нет такой заявки")
    con.execute("UPDATE redemptions SET status=? WHERE id=?", (st, rid))
    con.commit()
    return {"ok": True}


@app.get("/admin/api/offers")
def admin_offers(_=Depends(admin), con=Depends(get_con)):
    ensure_offers(con)
    rows = db.rows(con.execute(
        "SELECT o.*, m.first_name, m.last_name, m.username, m.sphere FROM offers o LEFT JOIN members m ON m.tg_id=o.tg_id ORDER BY o.id DESC LIMIT 300"))
    for o in rows:
        o["author"] = person_name(o)
        o["until"] = offer_until(o["approved_at"]) if o.get("approved_at") else ""
        o["requests"] = con.execute("SELECT COUNT(*) FROM offer_requests WHERE offer_id=?", (o["id"],)).fetchone()[0]
    return rows


@app.post("/admin/api/offers/{oid}/status")
async def admin_offer_status(oid: int, req: Request, _=Depends(admin), con=Depends(get_con)):
    ensure_offers(con)
    st = (await req.json()).get("status")
    if st not in ("active", "hidden", "pending"):
        raise HTTPException(400, "Неверный статус")
    row = con.execute("SELECT * FROM offers WHERE id=?", (oid,)).fetchone()
    if not row:
        raise HTTPException(404, "Нет такого предложения")
    con.execute("UPDATE offers SET status=?, approved_at=CASE WHEN ?='active' AND approved_at IS NULL THEN ? ELSE approved_at END WHERE id=?", (st, st, db.now(), oid))
    con.commit()
    if st == "active" and row["status"] == "pending":
        spawn(send_text(row["tg_id"], render(con, "offer_live", title=row["title"]), tg.app_button("Открыть клуб", "#events"), key="offer_live"))
    return {"ok": True}


@app.get("/admin/api/offer-requests")
def admin_offer_requests(_=Depends(admin), con=Depends(get_con)):
    ensure_offers(con)
    return db.rows(con.execute(
        "SELECT r.*, o.title, m.first_name, m.last_name, m.username FROM offer_requests r "
        "LEFT JOIN offers o ON o.id=r.offer_id LEFT JOIN members m ON m.tg_id=r.from_tg ORDER BY r.id DESC LIMIT 300"))


# ---------------- страницы ----------------

@app.get("/health")
def health():
    return {"ok": True}


STATIC = BASE / "static"


def _page(name: str):
    """Отдаем страницу без кеша, а к скриптам и стилям добавляем версию: после обновления Telegram сразу берет новые файлы."""
    txt = (STATIC / name).read_text(encoding="utf-8")
    for f in ("app.js", "app.css"):
        fp = STATIC / f
        if fp.exists():
            txt = txt.replace('/static/%s"' % f, '/static/%s?v=%d"' % (f, int(fp.stat().st_mtime)))
    return HTMLResponse(txt, headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/admin")
def admin_page():
    return _page("admin.html")


@app.get("/")
def app_page():
    return _page("index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
