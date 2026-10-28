"""Генерация иконки Audio Transcriber (macOS Big Sur style):
скруглённый квадрат 824×824 на полотне 1024×1024, диагональный градиент
«глубокая ночь» (как тема слайдов), белая звуковая волна, лёгкий блик.

Запуск: .venv/bin/python app-sources/make_icon.py [out_dir]
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
TILE = 824
RADIUS = 185
BARS = [88, 156, 232, 344, 448, 344, 232, 156, 88]  # высоты волны, px
BAR_W, GAP = 36, 26


def rounded_gradient(size, stops, radius):
    xs = np.linspace(0.0, 1.0, size, dtype=np.float32)[None, :]
    ys = np.linspace(0.0, 1.0, size, dtype=np.float32)[:, None]
    t = np.clip(xs * 0.55 + ys * 0.45, 0.0, 1.0)
    positions = np.array([p for p, _ in stops], dtype=np.float32)
    img = np.zeros((size, size, 4), dtype=np.float32)
    img[:, :, 3] = 255.0
    for ch in range(3):
        values = np.array([c[ch] for _, c in stops], dtype=np.float32)
        img[:, :, ch] = np.interp(t, positions, values)
    full = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA")

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(full, (0, 0), mask)
    return out


def sheen(tile):
    """Диагональный блик в верхней левой части."""
    w, h = tile.size
    xs = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    t = np.clip(1.0 - (xs * 0.6 + ys * 0.4), 0.0, 1.0) ** 2.2
    alpha = (t * 26).astype(np.uint8)
    layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    layer.putalpha(Image.fromarray(alpha, "L"))
    return Image.alpha_composite(tile, layer)


def waveform(tile):
    w, h = tile.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    total = len(BARS) * BAR_W + (len(BARS) - 1) * GAP
    x = (w - total) // 2
    cy = h // 2
    for bar_h in BARS:
        top = cy - bar_h / 2
        draw.rounded_rectangle(
            [x, top, x + BAR_W, top + bar_h],
            radius=BAR_W / 2,
            fill=(255, 255, 255, 244),
        )
        x += BAR_W + GAP
    return Image.alpha_composite(tile, layer)


def make_icon(path):
    tile = rounded_gradient(TILE, [(0.0, (28, 31, 64)), (0.55, (44, 42, 100)), (1.0, (74, 52, 132))], RADIUS)
    tile = sheen(tile)
    tile = waveform(tile)

    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    offset = (SIZE - TILE) // 2
    canvas.paste(tile, (offset, offset), tile)
    canvas.save(path, "PNG")
    return path


def make_iconset(png, out_dir):
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    os.makedirs(out_dir, exist_ok=True)
    for s in sizes:
        img = Image.open(png)
        img.thumbnail((s, s), Image.LANCZOS)
        img.save(os.path.join(out_dir, f"icon_{s}x{s}.png"))
        if s <= 512:
            img2 = Image.open(png)
            img2.thumbnail((s * 2, s * 2), Image.LANCZOS)
            img2.save(os.path.join(out_dir, f"icon_{s}x{s}@2x.png"))
    return out_dir


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "app-sources"
    png = os.path.join(out, "AppIcon_1024.png")
    make_icon(png)
    print("icon:", png)
