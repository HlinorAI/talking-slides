"""Темы оформления слайдов + автоопределение темы по содержанию транскрипта."""

import re

# Каждая тема: градиент фона (стопы 0..1), акцент, цвет текста, приглушённый
# цвет и ключевые слова, по которым тема выбирается для конкретной записи.
THEMES = {
    "midnight": {
        "label": "Глубокая ночь",
        "bg_stops": [(0.0, (23, 26, 56)), (0.55, (35, 33, 82)), (1.0, (56, 40, 106))],
        "accent": (128, 143, 255),
        "text": (244, 245, 252),
        "muted": (164, 170, 205),
        "vign": 0.38,
        "keywords": [
            "psycholog", "brain", "conscious", "philosoph", "meaning",
            "emotion", "behavior", "motivation", "habit", "mind", "person",
            "психолог", "мозг", "сознани", "мышлен", "философ", "смысл",
            "личност", "эмоци", "харизм", "отношен", "поведен", "мотивац",
            "характер", "привычк", "навык", "общен",
        ],
    },
    "ember": {
        "label": "Угли",
        "bg_stops": [(0.0, (52, 24, 18)), (0.5, (84, 34, 22)), (1.0, (128, 62, 30))],
        "accent": (255, 176, 92),
        "text": (252, 246, 238),
        "muted": (214, 178, 148),
        "vign": 0.42,
        "keywords": [
            "war", "empire", "revolution", "president", "politic",
            "army", "battle", "front", "troops", "captiv",
            "войн", "импер", "революц", "президент", "политик",
            "сражен", "арми", "сражал", "войск", "фронт", "плен",
        ],
    },
    "forest": {
        "label": "Хвойный лес",
        "bg_stops": [(0.0, (16, 42, 34)), (0.55, (22, 62, 46)), (1.0, (34, 88, 60))],
        "accent": (126, 224, 162),
        "text": (240, 250, 244),
        "muted": (158, 196, 172),
        "vign": 0.4,
        "keywords": [
            "health", "body", "sport", "nutrition", "nature", "energy",
            "sleep", "breath", "train", "practic", "organism",
            "здоров", "тело", "спорт", "питани", "природ", "энерг",
            "сон", "дыхан", "практ", "трениров", "organizм", "организ",
        ],
    },
    "slate": {
        "label": "Графит",
        "bg_stops": [(0.0, (26, 30, 38)), (0.55, (34, 40, 52)), (1.0, (48, 58, 78))],
        "accent": (108, 186, 255),
        "text": (240, 244, 250),
        "muted": (156, 168, 186),
        "vign": 0.36,
        "keywords": [
            "business", "money", "sales", "marketing", "startup", "client",
            "project", "company", "technolog", "computer", "software",
            "market", "profit", "budget", "contract",
            "бизнес", "деньг", "продаж", "маркетинг", "стартап", "клиент",
            "проект", "компан", "технолог", "компьютер", "программ",
            "рынок", "договор", "документ", "прибыл", "бюджет",
        ],
    },
    "dawn": {
        "label": "Рассвет",
        "bg_stops": [(0.0, (38, 22, 54)), (0.5, (86, 34, 74)), (1.0, (158, 62, 84))],
        "accent": (255, 158, 176),
        "text": (252, 243, 246),
        "muted": (214, 172, 186),
        "vign": 0.4,
        "keywords": [
            "family", "child", "love", "feel", "soul", "heart", "mother",
            "father", "friend", "warm", "home",
            "семья", "дет", "любов", "чувств", "душ", "сердц", "мама",
            "папа", "друж", "близк", "тепл", "дом",
        ],
    },
    "parchment": {
        "label": "Пергамент",
        "bg_stops": [(0.0, (238, 231, 214)), (0.55, (230, 220, 196)), (1.0, (214, 200, 170))],
        "accent": (146, 96, 44),
        "text": (44, 40, 34),
        "muted": (122, 112, 94),
        "vign": 0.16,
        "keywords": [
            "god", "spiritual", "faith", "church", "addiction",
            "sobriety", "seminar", "priest", "prayer", "bible", "christ",
            "communit", "scriptur",
            "бог", "духовн", "вера", "церков", "шаг", "зависимост",
            "трезвост", "групп", "семинар", "священ", "молитв", "библ",
            "писан", "христ", "вероучен", "общин",
        ],
    },
}

DEFAULT_THEME = "midnight"


def detect_theme(text, default=DEFAULT_THEME):
    """Возвращает имя темы, лучше всего отвечающей содержанию текста."""
    low = (text or "")[:60000].lower()
    scores = {}
    for name, theme in THEMES.items():
        scores[name] = sum(low.count(kw) for kw in theme["keywords"])
    best = max(scores, key=lambda n: scores[n])
    if scores[best] == 0:
        return default
    return best


def resolve(name):
    if name in THEMES:
        return THEMES[name]
    raise KeyError(f"Неизвестная тема: {name}. Доступны: {', '.join(THEMES)}")


def blend(c1, c2, t):
    """Смешение двух RGB-цветов (0–255); t=0 → c1, t=1 → c2."""
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))
