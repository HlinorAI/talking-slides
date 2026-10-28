"""Генерация фоновых изображений слайдов: градиент + мягкие декоративные
элементы в цветах темы. Один фон на деку, аспект под формат вывода."""

import random
import tempfile
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def _gradient(w, h, stops):
    """Диагональный градиент по стопам [(pos, (r,g,b)), ...]."""
    xs = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    t = np.clip(xs * 0.62 + ys * 0.38, 0.0, 1.0)
    positions = np.array([p for p, _ in stops], dtype=np.float32)
    img = np.zeros((h, w, 3), dtype=np.float32)
    for ch in range(3):
        values = np.array([c[ch] for _, c in stops], dtype=np.float32)
        img[:, :, ch] = np.interp(t, positions, values)
    return img


def _decorations(img, theme, rng):
    """Кольца и мягкие пятна акцентного цвета поверх градиента."""
    w, h = img.size
    accent = theme["accent"]
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # мягкие световые пятна
    for cx, cy, r, alpha in [
        (0.80, 0.18, 0.34, 26),
        (0.12, 0.86, 0.30, 18),
        (0.55, 0.55, 0.42, 10),
    ]:
        x, y, rr = cx * w, cy * h, r * min(w, h)
        draw.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(*accent, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.09 * min(w, h)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)

    # тонкие кольца
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for cx, cy, r, width, alpha in [
        (0.74, 0.30, 0.21, max(2, w // 560), 44),
        (0.30, 0.78, 0.10, max(2, w // 780), 34),
    ]:
        x, y, rr = cx * w, cy * h, r * min(w, h)
        draw.ellipse(
            [x - rr, y - rr, x + rr, y + rr],
            outline=(*accent, alpha),
            width=width,
        )
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img.convert("RGB")


def _vignette(arr, strength):
    h, w = arr.shape[:2]
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    ys = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
    d = np.sqrt(xs * xs + ys * ys) / np.sqrt(2.0)
    mask = 1.0 - strength * np.clip((d - 0.55) / 0.45, 0.0, 1.0)
    return arr * mask[:, :, None]


def make_backdrop(theme, w=1920, h=1080, seed="deck"):
    """Фон-картинка для темы; возвращает путь к JPEG во временном каталоге."""
    rng = random.Random(f"{seed}:{w}x{h}")
    arr = _gradient(w, h, theme["bg_stops"])
    arr = _vignette(arr, theme.get("vign", 0.35))
    # лёгкий шум против полос на градиенте
    arr = arr + rng.uniform(-3.0, 3.0)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    img = _decorations(img, theme, rng)

    out_dir = os.path.join(tempfile.gettempdir(), "at_backdrops")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{seed}_{w}x{h}.jpg")
    img.save(path, "JPEG", quality=90)
    return path
