"""База клуба: один файл SQLite. Все части системы читают и пишут только сюда."""
import json
import sqlite3
from datetime import datetime, timezone

from .config import DB_PATH, UPLOADS

SCHEMA = """
CREATE TABLE IF NOT EXISTS members(
  tg_id INTEGER PRIMARY KEY,
  username TEXT, first_name TEXT, last_name TEXT,
  level TEXT DEFAULT 'club',            -- club | inside
  status TEXT DEFAULT 'guest',          -- guest | active | expired
  paid_until TEXT, period_months INTEGER, last_amount REAL,
  sphere TEXT DEFAULT '', project TEXT DEFAULT '', city TEXT DEFAULT '',
  seek TEXT DEFAULT '', give TEXT DEFAULT '', tags TEXT DEFAULT '[]',
  offline INTEGER DEFAULT 1, coffee INTEGER DEFAULT 1,
  profile_done INTEGER DEFAULT 0, consent_at TEXT,
  bot_started INTEGER DEFAULT 0, source TEXT,
  manager TEXT, engagement TEXT DEFAULT 'новый', note TEXT DEFAULT '',
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, event TEXT,
  amount REAL, currency TEXT, period_months INTEGER, expires_at TEXT,
  verified INTEGER, raw TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS likes(
  from_id INTEGER, to_id INTEGER, value INTEGER, created_at TEXT,
  PRIMARY KEY(from_id, to_id)
);
CREATE TABLE IF NOT EXISTS matches(
  a INTEGER, b INTEGER, created_at TEXT, PRIMARY KEY(a, b)
);
CREATE TABLE IF NOT EXISTS coffee_pairs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, week TEXT, a INTEGER, b INTEGER,
  reason_a TEXT, reason_b TEXT, met_a INTEGER, met_b INTEGER, created_at TEXT
);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, rubric TEXT, speaker TEXT,
  starts_at TEXT, place TEXT DEFAULT 'Zoom', inside_only INTEGER DEFAULT 0,
  join_url TEXT DEFAULT '', description TEXT DEFAULT '',
  recording_url TEXT DEFAULT '', podcast_url TEXT DEFAULT '',
  summary TEXT DEFAULT '[]', timecodes TEXT DEFAULT '[]', clips INTEGER DEFAULT 0,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS rsvp(
  event_id INTEGER, tg_id INTEGER, created_at TEXT, PRIMARY KEY(event_id, tg_id)
);
CREATE TABLE IF NOT EXISTS library(
  id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, title TEXT, author TEXT,
  meta TEXT DEFAULT '', url TEXT DEFAULT '', body TEXT DEFAULT '',
  inside_only INTEGER DEFAULT 0, event_id INTEGER, created_at TEXT
);
CREATE TABLE IF NOT EXISTS point_rules(
  code TEXT PRIMARY KEY, title TEXT, hint TEXT, points INTEGER,
  kind TEXT DEFAULT 'text', active INTEGER DEFAULT 1, sort INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS claims(
  id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, rule_code TEXT,
  points INTEGER, text TEXT DEFAULT '', file TEXT, ref TEXT,
  status TEXT DEFAULT 'pending', decided_at TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS shop(
  code TEXT PRIMARY KEY, title TEXT, hint TEXT, cost INTEGER,
  inside_only INTEGER DEFAULT 0, icon TEXT DEFAULT 'gift', active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS redemptions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, code TEXT, cost INTEGER,
  status TEXT DEFAULT 'pending', created_at TEXT
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""

# Стартовые правила баллов. Цифры условные: меняются в кабинете.
RULES = [
    ("insight", "Инсайт после эфира", "Что забрали с последнего эфира", 10, "text", 1),
    ("result", "Поделиться результатом", "Чего достигли благодаря клубу", 20, "text", 2),
    ("thanks", "Поблагодарить участника", "Кому и за что вы благодарны", 10, "text", 3),
    ("story", "Сторис о клубе", "С хештегом #единение, приложите скриншот", 15, "file", 4),
    ("invite", "Пригласить в клуб", "Баллы придут, когда друг оплатит участие", 50, "link", 5),
    ("coffee", "Встреча Random Coffee", "Созвонились с парой недели", 20, "text", 6),
]
SHOP = [
    ("review", "Личный разбор от спикера, 30 минут", "Выберите спикера из клуба", 200, 0, "talk"),
    ("gift", "Подарок от партнера клуба", "Подборка меняется каждый месяц", 120, 0, "gift"),
    ("cottage", "Место на закрытом выступлении в коттедже", "Только для Inside-level", 150, 1, "house"),
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOADS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    con.row_factory = sqlite3.Row
    # встроенный lower в SQLite не понимает кириллицу
    con.create_function("lower", 1, lambda x: x.lower() if isinstance(x, str) else x, deterministic=True)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init():
    con = connect()
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(members)")}
    if "role" not in cols:  # команда клуба: вход по секретной ссылке
        con.execute("ALTER TABLE members ADD COLUMN role TEXT DEFAULT ''")
    if not con.execute("SELECT 1 FROM point_rules LIMIT 1").fetchone():
        con.executemany("INSERT INTO point_rules(code,title,hint,points,kind,sort) VALUES(?,?,?,?,?,?)", RULES)
    if not con.execute("SELECT 1 FROM shop LIMIT 1").fetchone():
        con.executemany("INSERT INTO shop(code,title,hint,cost,inside_only,icon) VALUES(?,?,?,?,?,?)", SHOP)
    con.commit()
    con.close()


def row(r):
    if r is None:
        return None
    d = dict(r)
    for k in ("tags", "summary", "timecodes"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                d[k] = []
    return d


def rows(rs):
    return [row(r) for r in rs]


def balance(con, tg_id):
    earned = con.execute("SELECT COALESCE(SUM(points),0) FROM claims WHERE tg_id=? AND status='approved'", (tg_id,)).fetchone()[0]
    spent = con.execute("SELECT COALESCE(SUM(cost),0) FROM redemptions WHERE tg_id=? AND status!='rejected'", (tg_id,)).fetchone()[0]
    pending = con.execute("SELECT COALESCE(SUM(points),0) FROM claims WHERE tg_id=? AND status='pending'", (tg_id,)).fetchone()[0]
    return {"balance": earned - spent, "pending": pending}


def get_setting(con, key, default=None):
    r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r[0] if r else default


def set_setting(con, key, value):
    con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def team_ids(con):
    return [r[0] for r in con.execute("SELECT tg_id FROM members WHERE role='team'")]


def team_code(con, regenerate=False):
    import secrets
    code = get_setting(con, "team_code")
    if regenerate or not code:
        code = secrets.token_urlsafe(12).replace("-", "a").replace("_", "b")
        set_setting(con, "team_code", code)
        con.commit()
    return code
