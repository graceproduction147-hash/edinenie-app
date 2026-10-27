"""Сервер клуба Единение: мини-приложение, кабинет, бот и оплаты Tribute в одном месте."""
import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import coffee, db, tg
from .config import (ADMIN_IDS, ADMIN_PASSWORD, BASE, DEV_MODE, INSIDE_MONTHS, JOIN_URL, PERIOD_MAP,
                     PUBLIC_URL, TRIBUTE_API_KEY, UPLOADS, WEBHOOK_SECRET)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("club")


@asynccontextmanager
async def lifespan(app):
    db.init()
    task = asyncio.create_task(coffee.scheduler())
    yield
    task.cancel()


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


def public_card(m):
    return {k: m.get(k) for k in ("tg_id", "first_name", "last_name", "sphere", "project", "city", "seek", "give", "tags", "offline", "level")}


@app.get("/api/me")
def me(m=Depends(current_user), con=Depends(get_con)):
    stats = {
        "matches": con.execute("SELECT COUNT(*) FROM matches WHERE a=? OR b=?", (m["tg_id"], m["tg_id"])).fetchone()[0],
        "insights": con.execute("SELECT COUNT(*) FROM claims WHERE tg_id=? AND rule_code='insight'", (m["tg_id"],)).fetchone()[0],
        "coffee": con.execute("SELECT COUNT(*) FROM coffee_pairs WHERE (a=? AND met_a=1) OR (b=? AND met_b=1)", (m["tg_id"], m["tg_id"])).fetchone()[0],
    }
    return {"me": m, "points": db.balance(con, m["tg_id"]), "stats": stats, "join": JOIN_URL,
            "is_admin": is_team(m)}


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
                await tg.send(who["tg_id"],
                              f"✨ <b>Это взаимно!</b>\n\nВы и <b>{peer['first_name'] or ''}</b> отметили друг друга в Знакомствах."
                              f"{' Напишите: @' + peer['username'] if peer['username'] else ''}",
                              tg.app_button("Открыть знакомства", "#matches"))
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
    return {"soon": soon, "records": recs}


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
    shop = db.rows(con.execute("SELECT * FROM shop WHERE active=1 ORDER BY cost"))
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
    await tg.notify_team(f"Новая заявка на баллы: <b>{rule['title']}</b> +{rule['points']} от {m['first_name'] or ''} "
                         f"{'@' + m['username'] if m['username'] else ''}\n\n{text[:500]}\n\nПодтвердить в кабинете: {PUBLIC_URL}/admin")
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
    await tg.notify_team(f"Обмен баллов: <b>{item['title']}</b> ({item['cost']}) — {m['first_name'] or ''} "
                         f"{'@' + m['username'] if m['username'] else ''}. Свяжитесь с участником.")
    return {"ok": True}


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


@app.post("/tribute/webhook")
async def tribute(req: Request, con=Depends(get_con)):
    raw = await req.body()
    sig = req.headers.get("trbt-signature", "")
    verified = None
    if TRIBUTE_API_KEY:
        calc = hmac.new(TRIBUTE_API_KEY.encode(), raw, hashlib.sha256).hexdigest()
        verified = 1 if hmac.compare_digest(calc, sig) else 0
    data = json.loads(raw or b"{}")
    event = data.get("name", "")
    p = data.get("payload", {}) or {}
    tg_id = p.get("telegram_user_id") or p.get("user_telegram_id")
    months = months_from(p)
    price = p.get("amount", p.get("price"))
    amount = (price / 100) if isinstance(price, (int, float)) else None  # Tribute присылает копейки
    expires = p.get("expires_at")
    con.execute("INSERT INTO payments(tg_id,event,amount,currency,period_months,expires_at,verified,raw,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (tg_id, event, amount, p.get("currency"), months, expires, verified, raw.decode("utf-8", "replace"), db.now()))
    con.commit()
    if verified == 0:
        log.warning("Tribute: неверная подпись, оплата записана, но доступ не выдан")
        await tg.notify_team("Пришла оплата Tribute с неверной подписью. Проверьте в кабинете, раздел «Оплаты».")
        return JSONResponse({"ok": False}, status_code=401)
    if not tg_id:
        return {"ok": True, "note": "нет telegram_user_id"}
    tg_id = int(tg_id)
    if event in ("new_subscription", "renewed_subscription", "new_donation", "subscription_renewed"):
        until = expires or (datetime.now(timezone.utc) + timedelta(days=31 * (months or 1))).isoformat()
        level = "inside" if (months or 0) >= INSIDE_MONTHS else "club"
        exists = con.execute("SELECT level FROM members WHERE tg_id=?", (tg_id,)).fetchone()
        if exists and exists["level"] == "inside":
            level = "inside"
        upsert_member(con, {"id": tg_id}, status="active", paid_until=until, period_months=months,
                      last_amount=amount, level=level)
        m = db.row(con.execute("SELECT * FROM members WHERE tg_id=?", (tg_id,)).fetchone())
        # пригласивший получает заявку на баллы
        if m.get("source", "") and m["source"].startswith("ref_") and not con.execute(
                "SELECT 1 FROM claims WHERE ref=?", (f"invite:{tg_id}",)).fetchone():
            try:
                add_claim(con, int(m["source"][4:]), "invite", f"Пригласил(а) участника {tg_id}", ref=f"invite:{tg_id}")
                con.commit()
            except Exception:
                log.exception("не удалось начислить приглашение")
        name = m.get("first_name") or ""
        await tg.send(tg_id, f"Добро пожаловать в Единение{', ' + name if name else ''}!\n\n"
                             "Откройте клуб и заполните анкету: по ней мы подбираем знакомства и пару Random Coffee.",
                      tg.app_button("Открыть клуб"))
        await tg.notify_team(
            f"💳 Новая оплата: {name} {'@' + m['username'] if m.get('username') else ''} (id {tg_id})\n"
            f"{level.capitalize()}-level, {months or '?'} мес., {amount or '?'} ₽\n\n"
            f"Приветствие для отправки:\n«{name or 'Привет'}, добро пожаловать в Единение! Я ваш менеджер. "
            f"Расскажите, с каким запросом пришли в клуб, и я помогу найти своих людей.»")
    elif event in ("cancelled_subscription", "subscription_cancelled"):
        await tg.notify_team(f"Отмена подписки: id {tg_id}. Доступ сохранится до конца оплаченного периода.")
    return {"ok": True}


# ---------------- бот ----------------

@app.post("/tg/webhook")
async def bot_update(req: Request, con=Depends(get_con)):
    if req.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        raise HTTPException(403)
    upd = await req.json()
    msg = upd.get("message") or {}
    u, text = msg.get("from"), (msg.get("text") or "")
    if not u or msg.get("chat", {}).get("type") != "private":
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
            await tg.send(u["id"], "Вы в команде клуба Единение. Приложение открыто полностью, уведомления об оплатах и заявках на баллы будут приходить от team-бота: нажмите /start в @edinenie_team1_bot.",
                          tg.app_button("Открыть клуб"))
            await tg.notify_team(f"В команду клуба добавлен(а) {u.get('first_name') or ''} {'@' + u['username'] if u.get('username') else ''} (id {u['id']}).")
            return {"ok": True}
        if status == "active":
            await tg.send(u["id"], f"{u.get('first_name') or 'Привет'}, вы в клубе Единение. Здесь знакомства, эфиры, библиотека и ваши баллы.",
                          tg.app_button("Открыть клуб"))
        else:
            await tg.send(u["id"], "Это бот клуба Единение. Приложение откроется, как только оплата участия пройдет.\n\n"
                                   f"Вступить в клуб: {JOIN_URL}")
    return {"ok": True}


# ---------------- кабинет (для вас и менеджера) ----------------

TOKENS = {}


def admin(authorization: str = Header("")):
    tok = authorization.removeprefix("Bearer ").strip()
    if not tok or tok not in TOKENS:
        raise HTTPException(401, "Войдите в кабинет")
    return TOKENS[tok]


@app.post("/admin/api/login")
async def admin_login(req: Request):
    data = await req.json()
    if not ADMIN_PASSWORD or not secrets.compare_digest(str(data.get("password", "")).strip().encode(), ADMIN_PASSWORD.strip().encode()):
        raise HTTPException(401, "Неверный пароль")
    tok = secrets.token_urlsafe(32)
    TOKENS[tok] = data.get("name") or "команда"
    return {"token": tok}


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


@app.get("/admin/api/members")
def admin_members(_=Depends(admin), con=Depends(get_con)):
    out = db.rows(con.execute("SELECT * FROM members ORDER BY created_at DESC"))
    for m in out:
        m["points"] = db.balance(con, m["tg_id"])
    return out


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
    c = con.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
    if not c or c["status"] != "pending":
        raise HTTPException(400, "Заявка уже обработана")
    status = "approved" if data.get("approve") else "rejected"
    pts = int(data.get("points", c["points"]))
    con.execute("UPDATE claims SET status=?, points=?, decided_at=? WHERE id=?", (status, pts, db.now(), cid))
    con.commit()
    if status == "approved":
        await tg.send(c["tg_id"], f"Команда клуба подтвердила +{pts} баллов. Спасибо за вклад!", tg.app_button("Мои баллы", "#profile"))
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


@app.post("/admin/api/coffee/run")
async def admin_coffee(_=Depends(admin), con=Depends(get_con)):
    res = coffee.make_pairs(con)
    if not res:
        return {"ok": False, "note": "Пары на эту неделю уже составлены"}
    await coffee.announce(*res)
    return {"ok": True, "pairs": len(res[0]), "left": len(res[1])}


@app.get("/admin/api/payments")
def admin_payments(_=Depends(admin), con=Depends(get_con)):
    return db.rows(con.execute("SELECT id,tg_id,event,amount,period_months,expires_at,verified,created_at FROM payments ORDER BY id DESC LIMIT 300"))


# ---------------- страницы ----------------

@app.get("/health")
def health():
    return {"ok": True}


STATIC = BASE / "static"


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC / "admin.html")


@app.get("/")
def app_page():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
