"""Рекомендации знакомств: раз в месяц несколько подходящих людей, которым можно написать.
Бот ничего не рассылает: подбор показывается в приложении. После «Обновить» можно получить новых людей."""
import json
import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from . import coffee, db
from .config import TZ

log = logging.getLogger("recs")


def month_key(dt=None):
    dt = dt or datetime.now(ZoneInfo(TZ))
    return f"{dt.year}-{dt.month:02d}"


def ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS recs(
      id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, rec_id INTEGER, month TEXT, batch INTEGER DEFAULT 1,
      reason TEXT DEFAULT '', written_at TEXT, created_at TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS recs_by_user ON recs(tg_id, month)")
    for col in ("outcome TEXT", "outcome_at TEXT", "asked_at TEXT"):  # ответ на «встретились?»
        try:
            con.execute(f"ALTER TABLE recs ADD COLUMN {col}")
        except Exception:
            pass
    con.execute("""CREATE TABLE IF NOT EXISTS recs_feedback(
      id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, month TEXT, batch INTEGER, met INTEGER, created_at TEXT)""")


def _norm(m):
    """Пустые поля как пустые строки: так подсчет совпадений не падает на None."""
    d = dict(m)
    for k in ("first_name", "last_name", "sphere", "project", "city", "seek", "give", "username"):
        d[k] = d.get(k) or ""
    d["offline"] = d.get("offline") or 0
    return d


def _tags(m):
    t = m.get("tags")
    try:
        a = json.loads(t) if isinstance(t, str) else (t or [])
    except ValueError:
        return set()
    return {str(x) for x in a} if isinstance(a, list) else set()


def _low(t):
    return (t or "").strip().rstrip(".").lower()


def _reason(me, other, ab, ba, common):
    name = other["first_name"] or "Этот человек"
    if ab and other["give"]:
        return f"Вы ищете: {_low(me['seek'])}. {name} может помочь: {_low(other['give'])}."
    if ba and other["seek"]:
        return f"{name} ищет: {_low(other['seek'])}. Вы можете помочь: {_low(me['give'])}."
    if common:
        return "Общие интересы: " + ", ".join(sorted(common)[:3]).lower() + "."
    if me["city"] and me["city"].strip().lower() == other["city"].strip().lower():
        return f"Вы оба из города {me['city']}, можно встретиться вживую."
    return f"{other['sphere'] or 'Участник клуба'}. Новый человек в вашем круге."


def make_batch(con, me, month, batch, n):
    """Подбирает n человек, которых этому участнику еще не рекомендовали. Без username не берем: иначе не с кем связаться."""
    ensure(con)
    me = _norm(me)
    seen = {r[0] for r in con.execute("SELECT rec_id FROM recs WHERE tg_id=?", (me["tg_id"],))}
    pool = db.rows(con.execute(
        "SELECT * FROM members WHERE status='active' AND profile_done=1 AND consent_at IS NOT NULL AND coffee=1 "
        "AND tg_id!=? AND COALESCE(username,'')!=''", (me["tg_id"],)))
    scored = []
    for o in pool:
        if o["tg_id"] in seen:
            continue
        o = _norm(o) | {"tags": o.get("tags")}
        s, ab, ba = coffee.score(me | {"tags": None}, o, set())
        common = _tags(me) & _tags(o)
        s += 0.5 * len(common)
        scored.append((s, random.random(), o, ab, ba, common))
    scored.sort(key=lambda x: (-x[0], x[1]))
    made = 0
    for s, _, o, ab, ba, common in scored[:n]:
        con.execute("INSERT INTO recs(tg_id,rec_id,month,batch,reason,created_at) VALUES(?,?,?,?,?,?)",
                    (me["tg_id"], o["tg_id"], month, batch, _reason(me, o, ab, ba, common), db.now()))
        made += 1
    con.commit()
    return made


def _latest(con, tg_id, month):
    r = con.execute("SELECT MAX(batch) FROM recs WHERE tg_id=? AND month=?", (tg_id, month)).fetchone()
    return r[0] if r and r[0] else None


def current(con, me, n):
    """Рекомендации этого месяца (последний подбор). Если подбора еще нет, составляет его."""
    ensure(con)
    month = month_key()
    batch = _latest(con, me["tg_id"], month)
    if batch is None:
        make_batch(con, me, month, 1, n)
        batch = _latest(con, me["tg_id"], month)
    if batch is None:
        return {"month": month, "batch": 0, "items": []}
    rows = con.execute("SELECT * FROM recs WHERE tg_id=? AND month=? AND batch=? ORDER BY id",
                       (me["tg_id"], month, batch)).fetchall()
    items = []
    for r in rows:
        other = con.execute("SELECT * FROM members WHERE tg_id=?", (r["rec_id"],)).fetchone()
        if other:
            items.append({"id": r["id"], "other": db.row(other), "reason": r["reason"], "written": bool(r["written_at"])})
    return {"month": month, "batch": batch, "items": items}


def mark_written(con, me_id, rid):
    ensure(con)
    r = con.execute("SELECT id FROM recs WHERE id=? AND tg_id=?", (rid, me_id)).fetchone()
    if not r:
        return False
    con.execute("UPDATE recs SET written_at=COALESCE(written_at, ?) WHERE id=?", (db.now(), rid))
    con.commit()
    return True


def refresh(con, me, met, n):
    """«Обновить»: записывает ответ, списались ли с людьми. Если да, составляет новый подбор.
    Возвращает True, если подобраны новые люди. Нужно написать хотя бы одному человеку из текущего подбора."""
    ensure(con)
    month = month_key()
    batch = _latest(con, me["tg_id"], month)
    if batch is None:
        raise ValueError("Подбор еще не составлен")
    written = con.execute("SELECT COUNT(*) FROM recs WHERE tg_id=? AND month=? AND batch=? AND written_at IS NOT NULL",
                          (me["tg_id"], month, batch)).fetchone()[0]
    if not written:
        raise ValueError("Сначала напишите хотя бы одному человеку из списка")
    con.execute("INSERT INTO recs_feedback(tg_id,month,batch,met,created_at) VALUES(?,?,?,?,?)",
                (me["tg_id"], month, batch, 1 if met else 0, db.now()))
    con.commit()
    if not met:
        return False
    make_batch(con, me, month, batch + 1, n)
    return True


OUTCOMES = ("met", "chat", "no")


def pending_meet(con, me_id, days=7):
    """Люди, которым участник написал неделю назад и еще не ответил, как прошло знакомство."""
    ensure(con)
    from datetime import timedelta, timezone
    lim = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    out = []
    for r in con.execute("SELECT * FROM recs WHERE tg_id=? AND written_at IS NOT NULL AND written_at<=? AND outcome IS NULL "
                         "ORDER BY written_at DESC LIMIT 6", (me_id, lim)).fetchall():
        o = con.execute("SELECT first_name, last_name, username FROM members WHERE tg_id=?", (r["rec_id"],)).fetchone()
        if o:
            name = " ".join(x for x in (o["first_name"], o["last_name"]) if x) or ("@" + (o["username"] or ""))
            out.append({"id": r["id"], "name": name, "username": o["username"] or "", "written_at": r["written_at"]})
    return out


def set_outcome(con, me_id, rid, outcome):
    ensure(con)
    if outcome not in OUTCOMES:
        return False
    r = con.execute("SELECT id FROM recs WHERE id=? AND tg_id=? AND written_at IS NOT NULL", (rid, me_id)).fetchone()
    if not r:
        return False
    con.execute("UPDATE recs SET outcome=?, outcome_at=? WHERE id=?", (outcome, db.now(), rid))
    con.commit()
    return True


def month_summary(con, me_id, month):
    """Знакомства, из которых что-то вышло (встретились или переписались) за месяц: для итогов месяца."""
    ensure(con)
    out = []
    for r in con.execute("SELECT * FROM recs WHERE tg_id=? AND outcome IN ('met','chat') AND substr(outcome_at,1,7)=? ORDER BY outcome_at",
                         (me_id, month)).fetchall():
        o = con.execute("SELECT first_name, last_name, username FROM members WHERE tg_id=?", (r["rec_id"],)).fetchone()
        if o:
            name = " ".join(x for x in (o["first_name"], o["last_name"]) if x)
            out.append({"name": name, "username": o["username"] or "", "outcome": r["outcome"]})
    return out
