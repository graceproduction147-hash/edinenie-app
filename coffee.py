"""Random Coffee: раз в неделю составляет пары с учетом «ищу» и «могу помочь»."""
import asyncio
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from . import db, tg
from .config import TZ

log = logging.getLogger("coffee")
STOP = set("для и в на с по от из к о об что как это или а но за под над при так же мне его ее их".split())


def words(text):
    out = set()
    for w in re.findall(r"[a-zа-я0-9]+", (text or "").lower()):
        if len(w) > 3 and w not in STOP:
            out.add(w[:5])  # грубая основа слова: «фотографа» и «фотограф» совпадут
    return out


def week_key(dt=None):
    dt = dt or datetime.now(ZoneInfo(TZ))
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def score(a, b, history):
    s = 0.0
    ab = words(a["seek"]) & words(b["give"])
    ba = words(b["seek"]) & words(a["give"])
    s += 3 * len(ab) + 3 * len(ba)
    s += len(words(a["sphere"] + " " + a["project"]) & words(b["sphere"] + " " + b["project"])) * 0.5
    if a["city"] and a["city"].strip().lower() == (b["city"] or "").strip().lower():
        s += 2 if (a["offline"] and b["offline"]) else 1
    if (min(a["tg_id"], b["tg_id"]), max(a["tg_id"], b["tg_id"])) in history:
        s -= 100  # уже встречались
    return s, ab, ba


def reason(me, other, overlap):
    name = other["first_name"] or "Ваша пара"
    if overlap:
        return f"Вы ищете: {me['seek'].strip().rstrip('.').lower()}. {name} может помочь: {other['give'].strip().rstrip('.').lower()}."
    if me["city"] and me["city"] == other["city"]:
        return f"Вы оба из города {me['city']}, можно встретиться вживую."
    return f"{name}: {other['sphere'] or 'участник клуба'}. Новый человек в вашем круге."


def make_pairs(con, week=None):
    week = week or week_key()
    if con.execute("SELECT 1 FROM coffee_pairs WHERE week=? LIMIT 1", (week,)).fetchone():
        return []
    people = db.rows(con.execute(
        "SELECT * FROM members WHERE status='active' AND coffee=1 AND profile_done=1"))
    history = {(min(r["a"], r["b"]), max(r["a"], r["b"])) for r in con.execute("SELECT a,b FROM coffee_pairs")}
    cand = []
    for i, a in enumerate(people):
        for b in people[i + 1:]:
            s, ab, ba = score(a, b, history)
            cand.append((s, a, b, ab, ba))
    cand.sort(key=lambda x: -x[0])
    used, pairs = set(), []
    for s, a, b, ab, ba in cand:
        if a["tg_id"] in used or b["tg_id"] in used:
            continue
        used |= {a["tg_id"], b["tg_id"]}
        ra, rb = reason(a, b, ab), reason(b, a, ba)
        con.execute("INSERT INTO coffee_pairs(week,a,b,reason_a,reason_b,created_at) VALUES(?,?,?,?,?,?)",
                    (week, a["tg_id"], b["tg_id"], ra, rb, db.now()))
        pairs.append((a, b, ra, rb))
    con.commit()
    left = [p for p in people if p["tg_id"] not in used]
    log.info("Random Coffee %s: %d пар, без пары %d", week, len(pairs), len(left))
    return pairs, left


async def announce(pairs, left):
    for a, b, ra, rb in pairs:
        for me, other, why in ((a, b, ra), (b, a, rb)):
            await tg.send(me["tg_id"],
                          f"☕ <b>Random Coffee на эту неделю</b>\n\nВаша пара: <b>{other['first_name'] or ''} {other['last_name'] or ''}</b>"
                          f"{' (@' + other['username'] + ')' if other['username'] else ''}\n\n{why}\n\n"
                          "Договоритесь о созвоне на 30 минут. В пятницу я спрошу, как прошло.",
                          tg.app_button("Открыть пару", "#coffee"))
    for p in left:
        await tg.send(p["tg_id"], "На этой неделе пары не хватило, вы первая в очереди на следующую.")
    if pairs or left:
        await tg.notify_team(f"Random Coffee: составлено пар {len(pairs)}, без пары {len(left)}.")


async def remind_feedback(con):
    week = week_key()
    rs = con.execute("SELECT * FROM coffee_pairs WHERE week=?", (week,)).fetchall()
    for r in rs:
        for who, met in ((r["a"], r["met_a"]), (r["b"], r["met_b"])):
            if met is None:
                await tg.send(who, "Как прошла встреча Random Coffee? Расскажите в двух словах, за отзыв начисляются баллы.",
                              tg.app_button("Оставить отзыв", "#coffee"))


async def event_reminders(con):
    """Напоминания записавшимся: за сутки и за час до эфира."""
    from datetime import timedelta, timezone
    now = datetime.now(timezone.utc)
    for kind, delta, text in (("day", timedelta(hours=24), "Завтра эфир клуба"), ("hour", timedelta(hours=1), "Через час эфир клуба")):
        lo, hi = (now + delta - timedelta(minutes=5)).isoformat(), (now + delta + timedelta(minutes=5)).isoformat()
        for e in con.execute("SELECT * FROM events WHERE starts_at BETWEEN ? AND ?", (lo, hi)).fetchall():
            key = f"rem:{e['id']}:{kind}"
            if db.get_setting(con, key):
                continue
            db.set_setting(con, key, "1"); con.commit()
            link = f"\n\nПодключиться: {e['join_url']}" if e["join_url"] else ""
            for (tg_id,) in con.execute("SELECT tg_id FROM rsvp WHERE event_id=?", (e["id"],)).fetchall():
                await tg.send(tg_id, f"{text}: <b>{e['title']}</b>{link}")


async def scheduler():
    """Понедельник 10:00 — пары, пятница 12:00 — вопрос про встречу (по Москве)."""
    while True:
        try:
            t = datetime.now(ZoneInfo(TZ))
            con = db.connect()
            wk = week_key(t)
            if t.weekday() == 0 and t.hour >= 10 and db.get_setting(con, "coffee_week") != wk:
                res = make_pairs(con, wk)
                db.set_setting(con, "coffee_week", wk); con.commit()
                if res:
                    await announce(*res)
            if t.weekday() == 4 and t.hour >= 12 and db.get_setting(con, "coffee_remind") != wk:
                db.set_setting(con, "coffee_remind", wk); con.commit()
                await remind_feedback(con)
            await event_reminders(con)
            con.close()
        except Exception:
            log.exception("ошибка планировщика")
        await asyncio.sleep(60)
