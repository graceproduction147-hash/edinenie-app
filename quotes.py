"""Послание дня: фраза на день (у всех одна) и картинка 1080x1920 на фирменном фоне.
Фразы можно править прямо в этом списке. Выбор фразы зависит только от даты."""
import io
import random
from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter

try:
    from . import card, card_assets, quote_font
    from .config import TZ
except ImportError:
    import card, card_assets, quote_font
    TZ = "Europe/Moscow"

PHRASES = ['Все ресурсы уже есть, просто нужно их взять', 'Приглашения можно не ждать', 'Все имеет смысл', 'Можно легче', 'Где ты себя обманываешь?', 'Мы сами решаем, какие возможности у нас есть', 'Пора переходить в большую игру', 'Быстрый результат приносит замедление', 'Научись наслаждаться процессом', 'Если я буду таким как все, то кто будет таким как я', 'Покажи, на что ты свободен', 'Сбудется', 'Все проходит, и это пройдет', 'Все получится, другого варианта нет', 'Много хочешь, много получишь', 'Иногда решение не там, где ты ищешь', 'Добро пожаловать на белую полосу', 'Все, что происходит, это хорошо, но почему, ты узнаешь позже', 'Это добром кончится', 'Начни с того, что есть', 'Не жди разрешения', 'Сегодня подходящий день', 'Хватит откладывать', 'Главное решение уже принято, остались действия', 'Ты сам выбираешь, чем сегодня гордиться', 'Можно просто начать', 'Не усложняй', 'Спроси. Что тебе стоит?', 'Позвони тому, о ком думаешь', 'Нужное окружение не находят, его собирают', 'Размер игры выбираешь ты', 'Не сравнивай. У тебя своя дистанция', 'Хорошие знакомства начинаются с простого «привет»', 'Тебе есть что предложить', 'Попроси. Тебе ответят чаще, чем ты думаешь', 'Расти там, где тебя понимают', 'Сделай шаг, остальное прояснится', 'Люди делают тебя сильнее. Выбирай их', 'Скучно? Значит, тесно', 'Не бывает слишком маленького шага', 'Смелость начинается с первого сообщения', 'Сегодня можно быть собой', 'Где ты молчишь, хотя есть что сказать?', 'Удивляйся чаще', 'Чего ты не говоришь вслух?', 'Вместе проще', 'Сделай то, что давно откладывал', 'Где ты сейчас играешь не в полную силу?', 'Хватит ждать знака. Это он', 'Реши сам, что для тебя успех', 'Проще, чем кажется', 'Доверяй процессу, но делай свою часть', 'Окружение тоже выбор', 'Не торопись быстрее, чем растешь', 'Свое никто не заберет', 'Ты уже в пути', 'Иногда достаточно одного разговора', 'Что бы ты сделал, если бы не боялся ошибиться?', 'Не жди идеального момента. Начни неидеально']

W, H = 1080, 1920
INK = (244, 240, 232, 255)
ACC = (220, 166, 126, 255)
MUTED = (160, 160, 172, 255)
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def today():
    return datetime.now(ZoneInfo(TZ)).date()


def phrase_for(d):
    return PHRASES[d.toordinal() % len(PHRASES)]


def _orb(img, cx, cy, r, col, alpha):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (alpha,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(r * 0.45)))


def _logo(img, cx=540, cy=230):
    """Солнце-спираль берем из фонового файла карточки (светлые лучи на темном), обрезаем по самому знаку и ставим точно по центру."""
    bg = Image.open(io.BytesIO(card_assets.bg_bytes())).convert("L").crop((430, 50, 650, 270))
    mask = bg.point(lambda v: 0 if v < 90 else min(255, int((v - 90) * 2.2)))
    bbox = mask.getbbox()
    mask = mask.crop(bbox)
    white = Image.new("RGBA", mask.size, (255, 255, 255, 255))
    white.putalpha(mask)
    img.alpha_composite(white, (int(cx - mask.width / 2), int(cy - mask.height / 2)))


# палитры: фон, цвета трех свечений (все из гаммы клуба: ночной синий, глина, синий, золото)
PALETTES = [
    ((22, 25, 40), (214, 120, 80), (96, 112, 196), (220, 166, 126)),
    ((20, 22, 38), (190, 96, 96), (84, 100, 190), (226, 180, 140)),
    ((18, 28, 40), (210, 150, 90), (70, 130, 170), (230, 200, 150)),
    ((26, 22, 40), (200, 110, 120), (110, 90, 190), (224, 170, 150)),
    ((16, 24, 36), (224, 140, 84), (60, 90, 160), (236, 190, 130)),
    ((24, 24, 36), (180, 100, 70), (120, 130, 200), (214, 160, 120)),
]


def _background(d):
    """Фон меняется от дня к дню: палитра и расположение свечений зависят от даты, поверх тонкие орбиты, звездная пыль и зерно."""
    rnd = random.Random(d.toordinal() * 7919)
    base, c1, c2, gold = PALETTES[d.toordinal() % len(PALETTES)]
    img = Image.new("RGBA", (W, H), base + (255,))
    # три больших свечения в случайных местах (но так, чтобы середина с текстом оставалась спокойной)
    spots = [(rnd.choice([120, 900, 960, 60]), rnd.randint(40, 520), rnd.randint(300, 420), c1, rnd.randint(190, 240)),
             (rnd.choice([40, 1040, 980]), rnd.randint(900, 1300), rnd.randint(240, 340), c2, rnd.randint(120, 170)),
             (rnd.randint(200, 900), rnd.randint(1750, 1980), rnd.randint(320, 440), c2, rnd.randint(90, 130))]
    for cx, cy, r, col, al in spots:
        _orb(img, cx, cy, r, col, al)
    # тонкие золотые орбиты вокруг логотипа
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for r, al in ((190, 70), (270, 45), (360, 28)):
        od.ellipse([540 - r, 230 - r, 540 + r, 230 + r], outline=gold + (al,), width=2)
    # длинные дуги по краям, у каждого дня свой наклон
    for _ in range(3):
        cx, cy, r = rnd.randint(-300, 1380), rnd.randint(700, 1700), rnd.randint(500, 900)
        od.ellipse([cx - r, cy - r, cx + r, cy + r], outline=gold + (22,), width=2)
    img.alpha_composite(ov)
    # звездная пыль
    dust = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dust)
    for _ in range(140):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        if 380 < y < 1540 and 160 < x < 920 and rnd.random() < 0.7:
            continue
        r = rnd.choice([1, 1, 2, 2, 3])
        dd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 245, 230, rnd.randint(70, 200)))
    img.alpha_composite(dust.filter(ImageFilter.GaussianBlur(0.6)))
    # зерно
    noise = Image.effect_noise((W, H), 28).convert("L").point(lambda v: v // 14)
    grain = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    grain.putalpha(noise)
    img.alpha_composite(grain)
    return img


def _nf(size):
    """Тонкий шрифт Poiret One. Кладем в кеш шрифтов карточки, чтобы использовать card.text_c."""
    from PIL import ImageFont
    key = ("PoiretOne", round(size, 1))
    if key not in card._fonts:
        f = ImageFont.truetype(io.BytesIO(quote_font.font_bytes()), size)
        card._fonts[key] = f
    return card._fonts[key]


def _wrap(text, f, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if f.getlength(t) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


@lru_cache(maxsize=8)
def render(d):
    """d: date. Возвращает PNG (bytes)."""
    img = _background(d)
    _logo(img, 540, 230)
    dr = ImageDraw.Draw(img, "RGBA")
    card.text_c(dr, 540, 520, "ПОСЛАНИЕ ДНЯ", "Manrope-Medium.ttf", 28, ACC, ls=7, max_w=900)
    dr.line([(480, 566), (600, 566)], fill=ACC, width=2)
    text = phrase_for(d)
    size = 52
    while True:
        f = _nf(size)
        lines = _wrap(text, f, 860)
        if len(lines) <= 5 or size <= 36:
            break
        size -= 2
    lh = int(size * 1.35)
    y = 960 - (len(lines) - 1) * lh / 2
    for ln in lines:
        _nf(size); card.text_c(dr, 540, y, ln, "PoiretOne", size, INK, ls=1.2)
        y += lh
    card.text_c(dr, 540, 1600, "ЕДИНЕНИЕ", "Forum.ttf", 46, INK, ls=9)
    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


if __name__ == "__main__":
    for i in (0, 2, 9, 17):
        d = date.fromordinal(date(2026, 11, 25).toordinal() + i)
        open(f"/tmp/quote_{i}.png", "wb").write(render(d))
