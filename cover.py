"""Обложка эфира по единому шаблону: фирменный фон с планетами, название и спикер.
Нужна для карточки в приложении и анонса в боте. Размер 1280x720 (горизонтальная 16:9)."""
import io
import random

from PIL import Image, ImageDraw, ImageFilter

try:
    from . import card, quotes
except ImportError:
    import card, quotes

ACC = (220, 166, 126)
INK = (245, 238, 228)
# фон, свечение 1, свечение 2, планета (светлая сторона, темная), золото
THEMES = [
    ((16, 18, 40), (232, 112, 72), (90, 110, 235), ((255, 170, 120), (60, 18, 22)), (240, 190, 140)),
    ((14, 20, 44), (214, 96, 130), (70, 150, 235), ((255, 150, 150), (50, 16, 40)), (240, 184, 160)),
    ((12, 24, 40), (240, 150, 70), (60, 170, 200), ((255, 200, 120), (60, 30, 16)), (245, 205, 150)),
    ((22, 16, 44), (180, 100, 240), (240, 120, 100), ((230, 160, 255), (36, 18, 70)), (235, 190, 170)),
]


def _glow(img, cx, cy, r, col, al):
    quotes._orb(img, cx, cy, r, col, al)


def _planet(img, cx, cy, R, light, dark, rim):
    n = int(R * 2.6)
    c = n / 2
    hx, hy = c - R * 0.45, c - R * 0.5          # источник света сверху-слева
    d = int(R * 3.1)
    g = Image.radial_gradient("L").resize((d, d), Image.BILINEAR)
    t = Image.new("L", (n, n), 255)
    t.paste(g, (int(hx - d / 2), int(hy - d / 2)))
    t = t.point(lambda v: int(255 * min(1.0, v * 1.4142 / 255) ** 1.15))
    body = Image.composite(Image.new("RGB", (n, n), dark), Image.new("RGB", (n, n), light), t).convert("RGBA")
    m = Image.new("L", (n, n), 0)
    ImageDraw.Draw(m).ellipse([c - R, c - R, c + R, c + R], fill=255)
    body.putalpha(m.filter(ImageFilter.GaussianBlur(1.2)))
    ring = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([c - R, c - R, c + R, c + R], outline=rim + (200,), width=3)
    halo = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse([c - R - 10, c - R - 10, c + R + 10, c + R + 10], outline=light + (170,), width=14)
    layer = Image.alpha_composite(halo.filter(ImageFilter.GaussianBlur(18)), body)
    layer.alpha_composite(ring.filter(ImageFilter.GaussianBlur(0.8)))
    img.alpha_composite(layer, (int(cx - c), int(cy - c)))


def _bg(seed, W, H):
    rnd = random.Random(seed)
    base, g1, g2, (pl, pd), gold = THEMES[seed % len(THEMES)]
    img = Image.new("RGBA", (W, H), base + (255,))
    k = H / 1350 * 1.0
    _glow(img, W * 0.88, H * 0.10, int(560 * k), g1, 235)
    _glow(img, W * 0.04, H * 0.85, int(520 * k), g2, 215)
    _glow(img, W * 0.55, H * 1.05, int(460 * k), g1, 120)
    _planet(img, W * 0.90, H * 0.14, int(300 * k * 1.1), pl, pd, gold)
    _planet(img, W * 0.03, H * 0.86, int(190 * k * 1.1), (170, 190, 255), (18, 22, 70), (190, 205, 255))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for _ in range(4):
        cx, cy, r = rnd.randint(-200, W + 200), rnd.randint(int(H * .3), int(H * .9)), rnd.randint(int(H * .35), int(H * .7))
        od.ellipse([cx - r, cy - r, cx + r, cy + r], outline=gold + (40,), width=2)
    img.alpha_composite(ov)
    dust = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dust)
    for _ in range(int(W * H / 7500)):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        if 200 < x < W - 200 and H * .28 < y < H * .8 and rnd.random() < .85:
            continue
        r = rnd.choice([1, 1, 2, 2, 3, 4])
        dd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 246, 232, rnd.randint(90, 230)))
    img.alpha_composite(dust.filter(ImageFilter.GaussianBlur(0.7)))
    # лёгкая тёмная подложка снизу для читаемости текста
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([0, int(H * .45), W, H], fill=base + (150,))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(120)))
    noise = Image.effect_noise((W, H), 28).convert("L").point(lambda v: v // 14)
    grain = Image.new("RGBA", (W, H), (255, 255, 255, 0)); grain.putalpha(noise)
    img.alpha_composite(grain)
    return img


def render(title, speaker="", label="ЭФИР", seed=0):
    W, H = 1280, 720
    img = _bg(seed, W, H)
    quotes._logo(img, W // 2, 62, 0.5)
    dr = ImageDraw.Draw(img, "RGBA")
    size = 112
    while True:
        f = quotes._nf(size)
        lines = quotes._wrap(title, f, 1040)
        if len(lines) <= 2 or size <= 56:
            break
        size -= 4
    n = len(lines)
    w = 1040
    while n > 1 and w > 300:  # выравниваем строки: ищем самую узкую ширину при том же числе строк
        w -= 20
        t = quotes._wrap(title, quotes._nf(size), w)
        if len(t) > n:
            break
        lines = t
    lh = int(size * 1.2)
    span = (130 if speaker else 64 + lh) + len(lines) * lh - (0 if speaker else lh)
    t0 = 372 - span / 2                      # весь блок (подпись, линия, название, спикер) по центру между логотипом и низом
    card.text_c(dr, W // 2, t0, label, "Manrope-Medium.ttf", 24, ACC, ls=8, max_w=700)
    dr.line([(W // 2 - 44, t0 + 36), (W // 2 + 44, t0 + 36)], fill=ACC, width=2)
    y = t0 + 64 + lh / 2
    for ln in lines:
        quotes._nf(size); card.text_c(dr, W // 2, y, ln, "PoiretOne", size, INK, ls=1.3)
        y += lh
    if speaker:
        card.text_c(dr, W // 2, y - lh / 2 + 66, speaker.upper(), "Manrope-Medium.ttf", 34, ACC, ls=7, max_w=1100)
    card.text_c(dr, W // 2, H - 52, "ЕДИНЕНИЕ", "Forum.ttf", 28, INK, ls=8)
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=90, optimize=True)
    return out.getvalue()


# сдержанные палитры для миниатюр: фон, свечение, планета (свет, тень), металл
ORB_THEMES = [
    ((11, 13, 24), (56, 66, 112), ((178, 170, 196), (22, 24, 44)), (214, 176, 132)),   # полночь и бронза
    ((14, 14, 18), (74, 70, 84), ((196, 192, 200), (30, 30, 38)), (222, 210, 190)),    # графит и жемчуг
    ((20, 12, 18), (96, 52, 64), ((204, 160, 150), (40, 18, 26)), (224, 184, 128)),    # бордо и золото
    ((9, 18, 24), (40, 86, 96), ((160, 196, 196), (14, 34, 42)), (222, 200, 160)),     # глубокая бирюза и шампань
]


def orb(seed=0, S=192):
    """Круглая миниатюра для списков: тёмная, приглушённая, с тонкой золотой линией. У каждого seed своя композиция."""
    Q = S * 3
    rnd = random.Random(seed * 7919 + 13)
    base, glow, (pl, pd), gold = ORB_THEMES[seed % len(ORB_THEMES)]
    img = Image.new("RGBA", (Q, Q), base + (255,))
    gx, gy = rnd.choice([.25, .75]) * Q, rnd.choice([.2, .8]) * Q
    _glow(img, int(gx), int(gy), int(Q * .6), glow, 150)
    # главная планета: небольшая, смещена от центра
    R = int(Q * rnd.uniform(.17, .24))
    px, py = Q * rnd.uniform(.4, .62), Q * rnd.uniform(.4, .62)
    _planet(img, px, py, R, pl, pd, gold)
    ov = Image.new("RGBA", (Q, Q), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    # тонкая золотая орбита-эллипс вокруг планеты, у каждого свой наклон
    a, b = R * rnd.uniform(1.7, 2.2), R * rnd.uniform(.5, .8)
    tilt = Image.new("RGBA", (Q, Q), (0, 0, 0, 0))
    ImageDraw.Draw(tilt).ellipse([px - a, py - b, px + a, py + b], outline=gold + (150,), width=3)
    tilt = tilt.rotate(rnd.uniform(-35, 35), center=(px, py), resample=Image.BICUBIC)
    img.alpha_composite(tilt)
    # маленький спутник на орбите
    ang = rnd.uniform(0, 6.28)
    sx, sy = px + a * 0.95 * __import__("math").cos(ang), py + b * 0.95 * __import__("math").sin(ang)
    r2 = Q * .018
    od.ellipse([sx - r2, sy - r2, sx + r2, sy + r2], fill=gold + (220,))
    # редкая звёздная пыль, без ярких цветов
    for _ in range(14):
        x, y, r = rnd.randint(0, Q), rnd.randint(0, Q), rnd.choice([1, 2, 2])
        od.ellipse([x - r, y - r, x + r, y + r], fill=(235, 228, 216, rnd.randint(60, 150)))
    img.alpha_composite(ov)
    m = Image.new("L", (Q, Q), 0)
    ImageDraw.Draw(m).ellipse([3, 3, Q - 4, Q - 4], fill=255)
    out = Image.new("RGBA", (Q, Q), (0, 0, 0, 0))
    out.paste(img.convert("RGB"), (0, 0), m)
    ImageDraw.Draw(out).ellipse([3, 3, Q - 4, Q - 4], outline=gold + (110,), width=4)
    buf = io.BytesIO()
    out.resize((S, S), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


if __name__ == "__main__":
    open("/tmp/cover_a.jpg", "wb").write(render("Окружение", "Влад Митьковский", seed=0))
    open("/tmp/cover_b.jpg", "wb").write(render("Как собрать событие с нуля", "Влад Митьковский", seed=2))
    open("/tmp/cover_c.jpg", "wb").write(render("Большая игра", "Влад Митьковский", seed=3))
