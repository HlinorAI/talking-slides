"""Пайплайн: аудио или ссылка на видео → транскрипция → слайды → PDF + PPTX.

Вход — путь к аудиофайлу (все форматы ffmpeg) ИЛИ http(s)-ссылка на видео
(YouTube, VK и всё, что поддерживает yt-dlp): тогда сначала скачивается
аудиодорожка, а заголовком презентации становится название видео.
Нечитаемый файл даёт понятную ошибку на этапе probe, до транскрибации.

Использование:
    python pipeline.py audio.m4a | https://... [--model DIR] [--outdir DIR] [--formats pdf,pptx,txt] [--lang auto|ru|en|...] [--beam N] [--theme auto|ИМЯ]

Прогресс для GUI — JSON-строки в stderr:
    {"stage":"download","pct":0.34}
    {"stage":"transcribe"}
    {"event":"done","outputs":["/path/a.pdf", ...]}
"""

import argparse
import json
import os
import re
import signal
import sys
from itertools import islice

from slidebuilder import build_slides
from renderers import render_pdf, render_pptx, render_html
from themes import detect_theme, DEFAULT_THEME
from util import safe_stem, t, detect_ui_lang

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def emit(**payload):
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)


# Дочерние процессы (ffmpeg при нарезке фрагментов). GUI-«Отменить»
# делает process.terminate() только для python — по SIGTERM гасим детей,
# чтобы ffmpeg не оставался висеть с частичными файлами.
# Обработчик ставится ТОЛЬКО на время нарезки: Python-обработчик не
# срабатывает внутри долгих C-вызовов (ctranslate2), и с ним «Отменить»
# во время транскрибации висела бы до конца окна декодирования. Вне
# нарезки действует SIG_DFL — мгновенная смерть по SIGTERM.
_children = []


def _kill_children_and_exit(signum, _frame):
    for proc in list(_children):
        try:
            proc.terminate()
        except Exception:
            pass
    sys.exit(128 + signum)


class child_kill_handlers:
    """Контекст: на время блока SIGTERM/SIGINT гасят дочерние процессы."""

    def __enter__(self):
        self._old = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
        for s in (signal.SIGTERM, signal.SIGINT):
            signal.signal(s, _kill_children_and_exit)
        return self

    def __exit__(self, *exc):
        for s, h in self._old.items():
            signal.signal(s, h)
        return False


def cut_fragments(audio, slides, outdir, ui_lang="en"):
    """Нарезает исходник на m4a-фрагменты по таймкодам слайдов.
    Возвращает список путей (None там, где таймкодов нет)."""
    import subprocess

    with child_kill_handlers():
        return _cut_fragments_inner(audio, slides, outdir, subprocess, ui_lang)


def _cut_fragments_inner(audio, slides, outdir, subprocess, ui_lang="en"):
    media_dir = os.path.join(outdir, "media")
    os.makedirs(media_dir, exist_ok=True)
    # старые фрагменты от прошлого прогона не должны оставаться
    for old in os.listdir(media_dir):
        if re.fullmatch(r"slide_\d+\.m4a", old):
            os.remove(os.path.join(media_dir, old))
    paths = []
    for i, slide in enumerate(slides, 1):
        start, end = slide.get("start"), slide.get("end")
        if start is None or end is None or end <= start:
            paths.append(None)
            continue
        out = os.path.join(media_dir, f"slide_{i:02d}.m4a")
        try:
            proc = subprocess.Popen(
                ["ffmpeg", "-y", "-loglevel", "error",
                 "-ss", f"{start:.2f}", "-i", audio, "-t", f"{end - start:.2f}",
                 "-c:a", "aac", "-b:a", "96k", out],
            )
        except FileNotFoundError as e:
            raise RuntimeError(t("ffmpeg_missing", ui_lang)) from e
        _children.append(proc)
        try:
            if proc.wait() != 0:
                raise RuntimeError(t("fragment_failed", ui_lang,
                                     i=i, code=proc.returncode))
        finally:
            _children.remove(proc)
        paths.append(out)
    return paths


def _format_chapter_ts(sec):
    """Таймкод главы: MM:SS, для записей длиннее часа — H:MM:SS (как
    требует YouTube)."""
    sec = int(sec)
    if sec >= 3600:
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{sec // 60:02d}:{sec % 60:02d}"


def write_chapters(slides, path, min_chapters=3, min_duration=10.0):
    """chapters.txt в формате YouTube. Требования YouTube: первая глава
    ровно 00:00, минимум 3 главы, каждая не короче 10 секунд. Если глава
    начинается раньше, чем через min_duration после предыдущей, она не
    выделяется; если глав меньше min_chapters, файл не пишется вовсе —
    YouTube такой список не примет."""
    if not slides or slides[0].get("start") is None:
        return False
    lines = [f"00:00 {slides[0]['title']}"]
    last_start = 0.0
    for slide in slides[1:]:
        start = slide.get("start")
        if start is None or start - last_start < min_duration:
            continue
        lines.append(f"{_format_chapter_ts(start)} {slide['title']}")
        last_start = start
    # последняя глава тоже должна быть не короче min_duration — её конец
    # это конец записи (конец последнего слайда)
    video_end = slides[-1].get("end")
    if lines and video_end is not None and video_end - last_start < min_duration:
        lines.pop()
    if len(lines) < min_chapters:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return True


def _default_model_dir():
    env = os.environ.get("AT_MODEL_DIR")
    if env:
        return env
    candidates = [
        os.path.join(PROJECT_DIR, "model"),
        os.path.expanduser("~/whisper-model"),
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, "model.bin")):
            return c
    return candidates[0]


DEFAULT_MODEL = _default_model_dir()


def log(msg):
    print(msg, flush=True)


def probe_audio(path, ui_lang="en"):
    """Проверяет до транскрибации, что файл декодируется и содержит звук.

    Поддержка форматов определяется не расширением, а возможностью
    декодировать: тем самым покрывается всё, что умеет ffmpeg (PyAV).
    """
    import av

    name = os.path.basename(path)
    try:
        with av.open(path) as container:
            if not container.streams.audio:
                raise RuntimeError(t("no_audio_track", ui_lang, name=name))
            frames = list(islice(container.decode(audio=0), 3))
            if not frames:
                raise RuntimeError(t("empty_audio_track", ui_lang, name=name))
    except av.error.FFmpegError as e:
        raise RuntimeError(
            t("unreadable_file", ui_lang, name=name)
        ) from e


def transcribe(audio, model_dir, lang="auto", beam_size=5, ui_lang="en"):
    from faster_whisper import WhisperModel

    log(t("log_model", ui_lang, dir=model_dir))
    model = WhisperModel(model_dir, device="cpu", compute_type="int8")
    log(t("log_transcribing", ui_lang, file=audio))
    segments_iter, info = model.transcribe(
        audio,
        language=None if lang == "auto" else lang,
        beam_size=beam_size,
        vad_filter=True,
    )
    if lang == "auto" and getattr(info, "language", None):
        log(t("log_lang", ui_lang, lang=info.language,
              pct=f"{info.language_probability:.0%}"))
        emit(detected_lang=info.language, p_lang=round(float(info.language_probability), 2))

    segments, texts = [], []
    duration = info.duration or 0.0
    for seg in segments_iter:
        segments.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
        texts.append(seg.text.strip())
        if duration:
            emit(progress=True, stage="transcribe", pct=min(1.0, seg.end / duration))
    text = "\n\n".join(t for t in texts if t)
    return text, segments, info


def fragments_plan(formats, pptx_audio):
    """pptx_audio: None — авто (звук в PPTX включён по умолчанию),
    True — легаси-флаг (эквивалентен авто), False — без звука.
    Возвращает (резать_фрагменты, встраивать_в_pptx).
    Фрагменты режутся только если есть куда их положить: html-плеер
    или PPTX со звуком."""
    embed = pptx_audio is not False
    cut = "html" in formats or ("pptx" in formats and embed)
    return cut, embed


def run(audio, model_dir=None, outdir=None, formats=("pdf", "pptx"), lang="auto",
        theme="auto", beam_size=5, pptx_audio=None, ui_lang=None):
    ui_lang = ui_lang or detect_ui_lang()
    model_dir = model_dir or DEFAULT_MODEL
    is_url = audio.startswith(("http://", "https://"))
    video_title = None
    if is_url:
        emit(stage="download")
        from downloader import download_audio
        dl_dir = os.path.join(PROJECT_DIR, "results", "_downloads")
        audio, video_title, _ = download_audio(audio, dl_dir, emit_fn=emit,
                                               ui_lang=ui_lang)
        log(t("log_downloaded", ui_lang, title=video_title))
    else:
        audio = os.path.abspath(audio)
        if not os.path.exists(audio):
            raise FileNotFoundError(audio)
        probe_audio(audio, ui_lang)

    stem = os.path.splitext(os.path.basename(audio))[0]
    # человеческий заголовок: «00_Predislovie» → «Predislovie»;
    # для ссылки из видео — само название видео
    if video_title:
        stem = safe_stem(video_title)
        clean_stem = video_title.strip()
    else:
        clean_stem = re.sub(r"^\d+[\s_.\-]*", "", stem)
        clean_stem = re.sub(r"[_\-]+", " ", clean_stem).strip() or stem
    outdir = outdir or os.path.join(PROJECT_DIR, "results", stem)
    os.makedirs(outdir, exist_ok=True)

    emit(stage="transcribe")
    text, segments, info = transcribe(audio, model_dir, lang, beam_size,
                                      ui_lang=ui_lang)
    html_lang = getattr(info, "language", None) or (lang if lang != "auto" else "ru")
    content_lang = "ru" if html_lang == "ru" else "en"

    txt_path = os.path.join(outdir, f"{stem}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)
    log(f"TXT: {txt_path}")

    emit(stage="slides")
    slides = build_slides(segments)
    if not slides:
        raise RuntimeError(t("empty_transcript", ui_lang))
    log(t("log_slides", ui_lang, n=len(slides)))

    theme_name = theme if theme != "auto" else detect_theme(text)
    emit(stage="theme", name=theme_name)
    log(t("log_theme", ui_lang, name=theme_name))

    # фрагменты аудио: для HTML-плеера и звука в PPTX (по умолчанию)
    cut_needed, embed_pptx = fragments_plan(formats, pptx_audio)
    fragments = None
    if cut_needed:
        emit(stage="fragments")
        fragments = cut_fragments(audio, slides, outdir, ui_lang)
        cut = sum(1 for f in fragments if f)
        log(t("log_fragments", ui_lang, cut=cut, total=len(slides)))

    outputs = [txt_path]
    if "pdf" in formats:
        emit(stage="render", fmt="pdf")
        pdf_path = os.path.join(outdir, f"{stem}.pdf")
        render_pdf(slides, pdf_path, clean_stem, source=audio, theme_name=theme_name,
                   content_lang=content_lang)
        outputs.append(pdf_path)
        log(f"PDF: {pdf_path}")
    if "pptx" in formats:
        emit(stage="render", fmt="pptx")
        pptx_path = os.path.join(outdir, f"{stem}.pptx")
        render_pptx(slides, pptx_path, clean_stem, source=audio, theme_name=theme_name,
                    audio_fragments=fragments if embed_pptx else None,
                    content_lang=content_lang)
        outputs.append(pptx_path)
        log(f"PPTX: {pptx_path}")
    if "html" in formats:
        emit(stage="render", fmt="html")
        html_path = os.path.join(outdir, f"{stem}.html")
        render_html(slides, html_path, clean_stem, source=audio, theme_name=theme_name,
                    audio_fragments=fragments, lang=html_lang,
                    content_lang=content_lang)
        outputs.append(html_path)
        log(f"HTML: {html_path}")

    chapters_path = os.path.join(outdir, "chapters.txt")
    if write_chapters(slides, chapters_path):
        outputs.append(chapters_path)
        log(t("log_chapters", ui_lang, path=chapters_path))

    emit(done=True, outputs=outputs, slides=len(slides))
    return outputs


def main():
    ap = argparse.ArgumentParser(description="Аудио → транскрипт → презентация")
    ap.add_argument("audio")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--formats", default="pdf,pptx")
    ap.add_argument("--lang", default="auto",
                    help="auto (определить) или код языка: ru, en, uk, kk, es, de, fr, it, pt, tr")
    ap.add_argument("--theme", default="auto",
                    help="auto или имя темы (см. themes.py)")
    ap.add_argument("--beam", type=int, default=5,
                    help="beam_size: 5 — качество, 1 — быстрый режим (в 2–4 раза быстрее)")
    ap.add_argument("--ui-lang", choices=("en", "ru"), default=None,
                    help="язык сообщений (по умолчанию — из LANG; en)")
    audio_group = ap.add_mutually_exclusive_group()
    audio_group.add_argument("--pptx-audio", action="store_true",
                             help="(устарел: звук в PPTX теперь по умолчанию)")
    audio_group.add_argument("--no-pptx-audio", action="store_true",
                             help="не встраивать аудиофрагменты в PPTX")
    args = ap.parse_args()

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    try:
        pptx_audio = True if args.pptx_audio else (False if args.no_pptx_audio else None)
        outputs = run(args.audio, args.model, args.outdir, formats, args.lang,
                      args.theme, args.beam, pptx_audio, args.ui_lang)
    except Exception as e:  # noqa: BLE001 — GUI читает событие error из stderr
        emit(error=True, message=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
