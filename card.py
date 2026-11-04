"""Карточка месяца: расчет архетипа и этапа и рисование картинки 1080x1920 для Stories.
Фон и неизменные подписи лежат в assets/card_bg.png, здесь рисуется только то, что меняется у человека."""
import io
import json
import math
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

try:
    from . import card_assets
except ImportError:  # запуск не из пакета (проверка вручную)
    import card_assets

# Шесть сфер карточки (порядок осей созвездия) и их формы для фразы «На стыке ...»
SPHERES = ["Капитал", "Сила окружения", "Глубина", "Энергия", "Тонкий вкус", "Сила слова"]
GENITIVE = {"Капитал": "капитала", "Сила окружения": "силы окружения", "Глубина": "глубины",
            "Энергия": "энергии", "Тонкий вкус": "тонкого вкуса", "Сила слова": "силы слова"}

# Какой вопрос анкеты какой сфере карточки соответствует. Меняется в одном месте.
FORM_TO_SPHERE = {"s_money": "Капитал", "s_people": "Сила окружения", "s_meaning": "Глубина",
                  "s_practices": "Энергия", "s_impressions": "Тонкий вкус", "s_opportunities": "Сила слова"}

ARCH = {
    ("Капитал", "Сила окружения"): "Коннектор", ("Капитал", "Глубина"): "Долгосрочный инвестор",
    ("Капитал", "Энергия"): "Вечный двигатель", ("Капитал", "Тонкий вкус"): "Коллекционер",
    ("Капитал", "Сила слова"): "Медиа-основатель", ("Сила окружения", "Глубина"): "Тихий лидер",
    ("Сила окружения", "Энергия"): "Катализатор", ("Сила окружения", "Тонкий вкус"): "Архитектор среды",
    ("Сила окружения", "Сила слова"): "Лидер мнений", ("Глубина", "Энергия"): "Стратег",
    ("Глубина", "Тонкий вкус"): "Ценитель", ("Глубина", "Сила слова"): "Идеолог",
    ("Энергия", "Тонкий вкус"): "Хедлайнер", ("Энергия", "Сила слова"): "Мастер слова",
    ("Тонкий вкус", "Сила слова"): "Культурный код",
}
THESIS = {
    "Точка отсчета": "Начало нового большого пути",
    "Расширение": "Все, что было тесным, получает воздух",
    "Прорыв": "Накопленное наконец складывается в форму",
    "Закрепление": "Ритм установился, и в нем спокойно",
    "Перестройка": "Старое уступает место более точному",
    "Перезагрузка": "Время тишины перед новым движением",
}
MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь",
          "Октябрь", "Ноябрь", "Декабрь"]


def _num(v):
    try:
        return max(1.0, min(10.0, float(str(v).replace(",", "."))))
    except (TypeError, ValueError):
        return None


def scores_from_form(d):
    """Ответы анкеты -> {сфера карточки: оценка}. Если сфер не хватает, возвращает None."""
    out = {}
    for key, sph in FORM_TO_SPHERE.items():
        v = _num((d or {}).get(key))
        if v is None:
            return None
        out[sph] = v
    return out


def pick_stage(cur, prev):
    """Этап по сравнению с прошлым месяцем. Пороги подобраны так, чтобы правила не пересекались."""
    if not prev:
        return "Точка отсчета"
    d = [cur[s] - prev[s] for s in SPHERES]
    mx, mn, mean = max(d), min(d), sum(d) / len(d)
    if mean <= -0.7 and mx < 2:
        return "Перезагрузка"
    if mx >= 1 and mn <= -1:
        return "Перестройка"
    if mx >= 2:
        return "Прорыв"
    if sum(1 for x in d if x >= 1) >= 2:
        return "Расширение"
    # почти без изменений: на высоком уровне это закрепление, на невысоком пауза перед новым движением
    return "Закрепление" if sum(cur.values()) / len(cur) >= 7 else "Перезагрузка"


def build_card_data(cur, prev, level, month_no, name=None, when=None, base=None):
    when = when or datetime.now(timezone.utc)
    growth = {s: (cur[s] - prev[s]) if prev else 0 for s in SPHERES}
    order = sorted(SPHERES, key=lambda s: (-cur[s], -growth[s], SPHERES.index(s)))
    top2 = sorted(order[:2], key=SPHERES.index)
    return {
        "name": (name or "").strip(), "month": MONTHS[when.month - 1], "year": when.year,
        "top3": order[:3], "archetype": ARCH[tuple(top2)], "stage": pick_stage(cur, prev),
        "strong": order[:2], "scores": [cur[s] for s in SPHERES],
        "prev": [(prev or base)[s] for s in SPHERES] if (prev or base) else None,
        "status": "Inside" if level == "inside" else "Club", "month_no": month_no,
    }


# ---------- рисование ----------
W, H = 1080, 1920
INK, MUTED, ACC, HOT = (241, 233, 223), (156, 151, 166), (220, 166, 126), (246, 210, 187)
_fonts = {}


def font(name, size):
    key = (name, round(size, 1))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(io.BytesIO(card_assets.font_bytes(name)), size)
    return _fonts[key]


def _width(text, f, ls):
    return sum(f.getlength(c) for c in text) + ls * max(0, len(text) - 1)


def text_c(dr, cx, cy, text, name, size, fill, ls=0.0, max_w=None, min_size=20, align="c", x=None):
    """Одна строка: по центру cx (или с левого края x / по правому x при align l/r), по высоте вокруг cy."""
    f = font(name, size)
    if max_w:
        while _width(text, f, ls) > max_w and size > min_size:
            size -= 1
            ls = ls * size / (size + 1)
            f = font(name, size)
    w = _width(text, f, ls)
    asc, desc = f.getmetrics()
    base = cy + (asc - desc) / 2
    left = cx - w / 2 if align == "c" else (x if align == "l" else x - w)
    for ch in text:
        dr.text((left, base), ch, font=f, fill=fill, anchor="ls")
        left += f.getlength(ch) + ls
    return w


def constellation(img, box, scores, prev, strong_idx):
    S = 4
    bx, by, bw, bh = box
    k = bw / 440.0 * S
    size = (int(bw * S), int(bh * S))
    layer = Image.new("RGBA", size, (0, 0, 0, 0))

    def paint(fn):
        nonlocal layer
        t = Image.new("RGBA", size, (0, 0, 0, 0))
        fn(ImageDraw.Draw(t, "RGBA"))
        layer = Image.alpha_composite(layer, t)

    def P(X, Y):
        return ((X + 70) * k, (Y - 10) * k)

    def pt(i, v):
        a = math.radians(-90 + 60 * i)
        r = 105.0 * v / 10.0
        return P(150 + r * math.cos(a), 150 + r * math.sin(a))

    def grid(d):
        for v in (3.3, 6.6, 10):
            pts = [pt(i, v) for i in range(6)]
            d.line(pts + [pts[0]], fill=(232, 176, 140, 46), width=max(1, int(k * 1.0)))
        for i in range(6):
            d.line([P(150, 150), pt(i, 10)], fill=(232, 176, 140, 31), width=max(1, int(k * 1.0)))

    pts = [pt(i, v) for i, v in enumerate(scores)]
    paint(grid)
    paint(lambda d: d.polygon(pts, fill=(220, 166, 126, 36)))

    def dashed(d):
        pp = [pt(i, v) for i, v in enumerate(prev)]
        pp = pp + [pp[0]]
        for a, b in zip(pp, pp[1:]):
            L = math.dist(a, b)
            n = max(1, int(L / (4 * k)))
            for j in range(0, n, 2):
                t0, t1 = j / n, min(1, (j + 1) / n)
                d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                        (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)],
                       fill=(241, 233, 223, 115), width=max(1, int(k * 1.3)))
    if prev:
        paint(dashed)
    paint(lambda d: d.line(pts + [pts[0], pts[1]], fill=(220, 166, 126, 255), width=max(1, int(k * 1.6)), joint="curve"))

    def glow(d):
        for i in strong_idx:
            p = pts[i]
            d.ellipse([p[0] - 13 * k, p[1] - 13 * k, p[0] + 13 * k, p[1] + 13 * k], fill=(242, 179, 148, 46))
    paint(glow)

    def dots(d):
        for i, p in enumerate(pts):
            if i in strong_idx:
                d.ellipse([p[0] - 6 * k, p[1] - 6 * k, p[0] + 6 * k, p[1] + 6 * k], fill=HOT + (255,))
            else:
                d.ellipse([p[0] - 3.5 * k, p[1] - 3.5 * k, p[0] + 3.5 * k, p[1] + 3.5 * k], fill=ACC + (255,))
    paint(dots)
    layer = layer.resize((int(bw), int(bh)), Image.LANCZOS)
    img.alpha_composite(layer, (int(bx), int(by)))


def render_card(data):
    """Возвращает PNG (bytes) 1080x1920."""
    img = Image.open(io.BytesIO(card_assets.bg_bytes())).convert("RGBA")
    dr = ImageDraw.Draw(img, "RGBA")
    cx = 540
    # имя и месяц
    tail = f'{data["month"]} {data["year"]}'
    nm = (data.get("name") or "").strip()
    words = nm.split()
    for cand in (nm, " ".join(words[:2]), (words[0] + " " + words[1][0] + ".") if len(words) > 1 else words[0] if words else ""):
        who = f"{cand} · {tail}" if cand else tail
        if _width(who.upper(), font("Manrope-Medium.ttf", 24), 6.3 * 24 / 28.8) <= 900:
            break
    text_c(dr, cx, 404.4, who.upper(), "Manrope-Medium.ttf", 28.8, MUTED, ls=6.3, max_w=900, min_size=22)
    # на стыке
    parts = [GENITIVE[s] for s in data["top3"]]
    bold = f'{parts[0]}, {parts[1]} и {parts[2]}'
    lead = "На стыке "
    fr, fb = font("Manrope-Regular.ttf", 33.6), font("Manrope-SemiBold.ttf", 33.6)
    size = 33.6
    while fr.getlength(lead) + fb.getlength(bold) > 900 and size > 26:
        size -= 1
        fr, fb = font("Manrope-Regular.ttf", size), font("Manrope-SemiBold.ttf", size)
    tw = fr.getlength(lead) + fb.getlength(bold)
    asc, desc = fr.getmetrics()
    base = 473.2 + (asc - desc) / 2
    dr.text((cx - tw / 2, base), lead, font=fr, fill=MUTED, anchor="ls")
    dr.text((cx - tw / 2 + fr.getlength(lead), base), bold, font=fb, fill=INK, anchor="ls")
    # созвездие
    strong_idx = [SPHERES.index(s) for s in data["strong"]]
    constellation(img, (288, 516.7, 504, 320.7), data["scores"], data["prev"], strong_idx)
    # архетип
    text_c(dr, cx, 967.2, data["archetype"].upper(), "Forum.ttf", 100.8, INK, ls=4.0, max_w=900, min_size=56)
    # плашка этапа
    label = f'Этап: {data["stage"]}'
    f = font("Manrope-Medium.ttf", 32.4)
    tw = f.getlength(label)
    cw = tw + 2 * 61.5
    x0, y0 = cx - cw / 2, 1056.3
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle([x0, y0, x0 + cw, y0 + 96], radius=48, fill=(220, 166, 126, 33),
                                         outline=ACC + (255,), width=2)
    img.alpha_composite(ov)
    dr = ImageDraw.Draw(img, "RGBA")
    text_c(dr, cx, y0 + 48, label, "Manrope-Medium.ttf", 32.4, ACC)
    # тезис
    text_c(dr, cx, 1224.5, THESIS[data["stage"]], "CormorantItalic.ttf", 55.2, INK, ls=0.55, max_w=900, min_size=40)
    # сильные стороны, статус
    for yy, s in zip((1357.4, 1476.3), data["strong"]):
        text_c(dr, 0, yy, s.upper(), "Forum.ttf", 45.6, INK, ls=1.37, align="l", x=165.6)
    text_c(dr, 0, 1593.0, f'Статус {data["status"]}', "Manrope-Medium.ttf", 36, ACC, align="l", x=165.6)
    n = data["month_no"]
    text_c(dr, 0, 1595.0, f"{n}-й месяц в клубе".upper(), "Manrope-Medium.ttf", 28.8, MUTED, ls=4.03, align="r", x=996)
    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


if __name__ == "__main__":
    cur = dict(zip(SPHERES, [8, 6, 7, 5, 8, 4]))
    prev = dict(zip(SPHERES, [6, 6, 5, 5, 7, 5]))
    d = build_card_data(cur, prev, "inside", 3, "Екатерина Коновалова", datetime(2026, 11, 4))
    print(d["archetype"], d["stage"], d["top3"])
    open("/tmp/card_test.png", "wb").write(render_card(d))
