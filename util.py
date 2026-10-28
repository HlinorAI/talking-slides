"""Общие утилиты пайплайна."""

import os
import re


def safe_stem(s):
    """Безопасное имя файла/папки из заголовка видео или файла.

    Запрещённые в именах символы заменяются пробелом, точки и пробелы по
    краям срезаются (иначе '..' превратится в выход из results/), длина
    ограничена 60 символами; пустой результат даёт fallback.
    """
    cleaned = re.sub(r'[\\/:*?"<>|]+', " ", s or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    cleaned = cleaned[:60].strip(" .")
    return cleaned or "video"


# Тексты сообщений пайплайна на двух языках: en — язык по умолчанию,
# ru — для русского интерфейса приложения и LANG. Слайды остаются на
# языке записи — здесь только сообщения и ошибки.
STRINGS = {
    "no_audio_track": {
        "en": "No audio track in “{name}”",
        "ru": "В файле «{name}» нет звуковой дорожки",
    },
    "empty_audio_track": {
        "en": "The audio track in “{name}” is empty",
        "ru": "Звуковая дорожка в «{name}» пуста",
    },
    "unreadable_file": {
        "en": "Could not read “{name}”: unsupported format or damaged file",
        "ru": "Не удалось прочитать «{name}»: формат не поддерживается или файл повреждён",
    },
    "download_no_file": {
        "en": "Download produced no audio file: {url}",
        "ru": "Скачивание не дало аудиофайл: {url}",
    },
    "ffmpeg_missing": {
        "en": "ffmpeg not found — cannot cut audio fragments. Install it: brew install ffmpeg",
        "ru": "ffmpeg не найден — нарезка фрагментов невозможна. Установите: brew install ffmpeg",
    },
    "fragment_failed": {
        "en": "ffmpeg failed to cut fragment {i} (exit code {code})",
        "ru": "ffmpeg не смог нарезать фрагмент {i} (код {code})",
    },
    "empty_transcript": {
        "en": "Empty transcript — no slides built",
        "ru": "Пустой транскрипт — слайды не построены",
    },
    "log_model": {"en": "Loading model: {dir}", "ru": "Загрузка модели: {dir}"},
    "log_transcribing": {"en": "Transcribing: {file}", "ru": "Транскрибация: {file}"},
    "log_lang": {"en": "Language: {lang} (confidence {pct})", "ru": "Язык: {lang} (уверенность {pct})"},
    "log_downloaded": {"en": "Downloaded: {title}", "ru": "Скачано: {title}"},
    "log_slides": {"en": "Slides: {n}", "ru": "Слайды: {n}"},
    "log_theme": {"en": "Theme: {name}", "ru": "Тема оформления: {name}"},
    "log_fragments": {"en": "Audio fragments: {cut}/{total}", "ru": "Фрагменты аудио: {cut}/{total}"},
    "log_chapters": {"en": "Chapters: {path}", "ru": "Главы: {path}"},
}


def t(key, lang="en", **params):
    """Перевод по ключу; нет перевода — английский, нет ключа — сам ключ."""
    entry = STRINGS.get(key) or {}
    text = entry.get(lang) or entry.get("en") or key
    return text.format(**params) if params else text


def detect_ui_lang():
    """Язык сообщений: AT_UI_LANG или LANG (ru → русский, иначе английский)."""
    env = os.environ.get("AT_UI_LANG") or os.environ.get("LANG") or ""
    return "ru" if env[:2].lower() == "ru" else "en"
