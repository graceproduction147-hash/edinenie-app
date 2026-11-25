"""Послание дня: фраза на день (у всех одна) и картинка 1080x1920 на фирменном фоне.
Фразы можно править прямо в этом списке. Выбор фразы зависит только от даты."""
import io
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


def _logo(img):
    """Солнце-спираль берем из фонового файла карточки (светлые лучи на темном) и кладем белым поверх нового фона."""
    bg = Image.open(io.BytesIO(card_assets.bg_bytes())).convert("L").crop((430, 50, 650, 270))
    mask = bg.point(lambda v: 0 if v < 90 else min(255, int((v - 90) * 2.2)))
    white = Image.new("RGBA", mask.size, (255, 255, 255, 255))
    white.putalpha(mask)
    img.alpha_composite(white, (470, 150))


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
    img = Image.new("RGBA", (W, H), (22, 25, 40, 255))
    _orb(img, 880, 160, 360, (214, 120, 80), 235)
    _orb(img, 40, 1020, 300, (96, 112, 196), 150)
    _orb(img, 700, 1900, 420, (60, 66, 120), 110)
    _logo(img)
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
    label = f"{d.day} {MONTHS_GEN[d.month - 1]}".upper()
    card.text_c(dr, 540, 1640, label, "Manrope-Medium.ttf", 26, MUTED, ls=6)
    card.text_c(dr, 540, 1740, "ЕДИНЕНИЕ", "Forum.ttf", 46, INK, ls=9)
    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


if __name__ == "__main__":
    for i in (0, 2, 9, 17):
        d = date.fromordinal(date(2026, 11, 25).toordinal() + i)
        open(f"/tmp/quote_{i}.png", "wb").write(render(d))
