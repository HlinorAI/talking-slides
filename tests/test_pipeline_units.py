# Тесты talking-slides: всё офлайн, модель не нужна.
#
# Запуск: .venv/bin/python -m pytest tests -q
# (был установлен через: .venv/bin/pip install -r requirements-dev.txt)

import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------- util.safe_stem ----------

def test_safe_stem_dots_only():
    from util import safe_stem
    assert safe_stem("..") == "video"
    assert safe_stem("...") == "video"
    assert safe_stem(". " * 40) == "video"


def test_safe_stem_keeps_inner_dots():
    from util import safe_stem
    assert safe_stem("Chapter 1.5: intro") == "Chapter 1.5 intro"


def test_safe_stem_strips_edges():
    from util import safe_stem
    assert safe_stem(". hidden .") == "hidden"
    assert safe_stem("  My .. Video: Final?  ") == "My .. Video Final"


def test_safe_stem_limits_and_fallback():
    from util import safe_stem
    assert len(safe_stem("x" * 100)) == 60
    assert safe_stem("") == "video"
    assert safe_stem(None) == "video"


# ---------- pipeline.write_chapters (правила YouTube) ----------

def slide(title, start, dur=30):
    end = start + dur if start is not None else None
    return {"title": title, "bullets": ["x"], "start": start, "end": end}


def test_chapters_requires_three(tmp_path):
    from pipeline import write_chapters
    p = tmp_path / "chapters.txt"
    assert write_chapters([slide("A", 0), slide("B", 60)], str(p)) is False
    assert not p.exists()


def test_chapters_starts_at_zero(tmp_path):
    from pipeline import write_chapters
    p = tmp_path / "chapters.txt"
    assert write_chapters([slide("A", 12), slide("B", 60), slide("C", 130)], str(p))
    assert p.read_text().splitlines()[0].startswith("00:00 ")


def test_chapters_hours_format(tmp_path):
    from pipeline import write_chapters
    p = tmp_path / "chapters.txt"
    write_chapters([slide("A", 0), slide("B", 700), slide("C", 4530)], str(p))
    assert "1:15:30 C" in p.read_text()


def test_chapters_skip_short(tmp_path):
    from pipeline import write_chapters
    p = tmp_path / "chapters.txt"
    write_chapters(
        [slide("A", 0), slide("B", 61), slide("C", 65), slide("D", 200)], str(p))
    lines = p.read_text().splitlines()
    assert len(lines) == 3  # C на 65 сек не выделяется (после B прошло <10 с)


def test_chapters_no_timestamps(tmp_path):
    from pipeline import write_chapters
    p = tmp_path / "chapters.txt"
    assert write_chapters([slide("A", None)], str(p)) is False


def test_chapters_short_last_dropped(tmp_path):
    """Последняя глава короче 10 с до конца записи не выделяется."""
    from pipeline import write_chapters
    p = tmp_path / "chapters.txt"
    # запись кончается на 615: глава D на 606 живёт только 9 с → выпадает,
    # остаются A/B/C (3 главы) — файл пишется без D
    slides = [slide("A", 0), slide("B", 300), slide("C", 500), slide("D", 606)]
    slides[-1]["end"] = 615
    assert write_chapters(slides, str(p)) is True
    text = p.read_text()
    assert "D" not in text
    assert text.splitlines()[-1].startswith("08:20 C")


def test_sigterm_handler_scoped_to_fragments():
    """Обработчик SIGTERM ставится только внутри нарезки (регрессия c7d707b:
    с постоянным обработчиком «Отменить» ждала окончания C-вызова)."""
    import signal
    from pipeline import child_kill_handlers
    before = signal.getsignal(signal.SIGTERM)
    assert before is signal.SIG_DFL
    with child_kill_handlers():
        inside = signal.getsignal(signal.SIGTERM)
        assert inside is not signal.SIG_DFL
    after = signal.getsignal(signal.SIGTERM)
    assert after is signal.SIG_DFL


# ---------- pipeline.fragments_plan (звук в PPTX по умолчанию) ----------

def test_fragments_plan_default_audio():
    from pipeline import fragments_plan
    # авто (None): pptx → резать и встраивать; pdf один → не резать
    assert fragments_plan(("pdf", "pptx"), None) == (True, True)
    assert fragments_plan(("pdf",), None) == (False, True)
    # html один → резать (для плеера)
    assert fragments_plan(("html",), None)[0] is True
    # отключено пользователем → не резать и не встраивать
    assert fragments_plan(("pdf", "pptx"), False) == (False, False)
    # html включён, но звук в PPTX отключён → резать, не встраивать
    assert fragments_plan(("html", "pptx"), False) == (True, False)
    # легаси True без pptx в форматах — фрагменты не нарезаются
    # (некуда класть), с pptx — как авто
    assert fragments_plan(("pdf",), True) == (False, True)
    assert fragments_plan(("pptx",), True) == (True, True)


def test_audio_flags_mutually_exclusive(monkeypatch):
    """--pptx-audio вместе с --no-pptx-audio → ошибка запуска, а не
    молчаливый приоритет одного из них."""
    from pipeline import main
    monkeypatch.setattr(sys, "argv",
                        ["pipeline.py", "x.m4a", "--pptx-audio", "--no-pptx-audio"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 2


def test_cut_fragments_missing_ffmpeg(tmp_path, monkeypatch):
    """Без ffmpeg в PATH — понятная ошибка, а не сырой FileNotFoundError."""
    from pipeline import cut_fragments
    monkeypatch.setenv("PATH", "/nonexistent")
    audio = _tiny_wav(tmp_path)
    slides = [slide("A", 0, 1)]
    with pytest.raises(RuntimeError, match="ffmpeg not found"):
        cut_fragments(audio, slides, str(tmp_path))
    with pytest.raises(RuntimeError, match="ffmpeg не найден"):
        cut_fragments(audio, slides, str(tmp_path), ui_lang="ru")


# ---------- pipeline.cut_fragments ----------

def test_cut_fragments_cleans_old(tmp_path):
    """Старые фрагменты от прошлого прогона удаляются (P2-11)."""
    from pipeline import cut_fragments
    media = tmp_path / "media"
    media.mkdir()
    stale = media / "slide_09.m4a"
    stale.write_bytes(b"old junk")
    audio = _tiny_wav(tmp_path)
    slides = [slide("A", 0, 1)]
    paths = cut_fragments(audio, slides, str(tmp_path))
    assert paths[0] and os.path.exists(paths[0])
    assert not stale.exists()  # срезан при новой нарезке


def _tiny_wav(tmp_path):
    """1-секундный wav через PyAV (ffmpeg уже в зависимостях)."""
    import av
    import numpy as np
    path = str(tmp_path / "src.wav") if hasattr(tmp_path, "__truediv__") else \
        os.path.join(str(tmp_path), "src.wav")
    c = av.open(path, "w")
    stream = c.add_stream("pcm_s16le", rate=16000, layout="mono")
    for _ in range(16):  # 16000 сэмплов / 1000 на фрейм
        frame = av.AudioFrame.from_ndarray(
            np.zeros((1, 1000), dtype="int16"), format="s16", layout="mono")
        frame.rate = 16000
        for packet in stream.encode(frame):
            c.mux(packet)
    for packet in stream.encode(None):
        c.mux(packet)
    c.close()
    return path


# ---------- slidebuilder ----------

def _segments(minutes=8, secs_per_seg=4):
    t = 0.0
    out = []
    for i in range(int(minutes * 60 / secs_per_seg)):
        out.append({
            "start": t,
            "end": t + 3.6,
            "text": f"Предложение номер {i} с достаточным объёмом текста "
                    f"для эвристики слайдов и тезисов. ",
        })
        t += secs_per_seg
    return out


def test_build_slides_basic():
    from slidebuilder import build_slides
    slides = build_slides(_segments())
    assert 2 <= len(slides) <= 12
    for s in slides:
        assert s["title"]
        assert s["bullets"]
        assert s["end"] >= s["start"]


def test_build_slides_empty():
    from slidebuilder import build_slides
    assert build_slides([]) == []


# ---------- renderers (smoke, во временную папку) ----------

@pytest.fixture(scope="module")
def real_slides():
    return [
        {"title": "Введение", "bullets": ["первый тезис", "второй тезис"],
         "start": 0, "end": 120},
        {"title": "Основная часть", "bullets": ["а", "б", "в"],
         "start": 120, "end": 300},
        {"title": "Заключение", "bullets": ["итог"], "start": 300, "end": 420},
    ]


def test_render_pdf_smoke(real_slides, tmp_path):
    from renderers import render_pdf
    p = str(tmp_path / "out.pdf")
    render_pdf(real_slides, p, "Тест")
    assert os.path.getsize(p) > 1000


def test_render_pptx_embeds_audio(real_slides, tmp_path):
    """Ключевая фишка: фрагмент встроен в ppt/media и привязан к слайду.
    Фрагмент делаем m4a, как в проде (cut_fragments режет aac)."""
    from renderers import render_pptx
    import subprocess
    wav = _tiny_wav(tmp_path)
    frag = os.path.join(str(tmp_path), "slide_01.m4a")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav,
                    "-c:a", "aac", frag], check=True)
    fragments = [frag, None, frag]
    p = str(tmp_path / "out.pptx")
    render_pptx(real_slides, p, "Тест", audio_fragments=fragments)
    with zipfile.ZipFile(p) as z:
        media = [n for n in z.namelist() if n.startswith("ppt/media/") and n.endswith(".m4a")]
        assert media, "нет встроенного аудио в ppt/media"
        xml1 = z.read("ppt/slides/slide2.xml").decode("utf-8", "replace")
        assert "videoFile" in xml1, "аудио не привязано к первому контентному слайду"
        xml2 = z.read("ppt/slides/slide3.xml").decode("utf-8", "replace")
        assert "videoFile" not in xml2, "у слайда без фрагмента не должно быть аудио"
        core = z.read("docProps/core.xml").decode("utf-8", "replace")
        assert "talking-slides" in core and "Steve Canny" not in core, \
            "в метаданных PPTX не должен оставаться автор шаблона"


def test_render_html_per_slide_audio(real_slides, tmp_path):
    from renderers import render_html
    p = str(tmp_path / "out.html")
    fragments = ["media/slide_01.m4a", None, "media/slide_03.m4a"]
    render_html(real_slides, p, "Тест", audio_fragments=fragments, lang="en")
    s = open(p, encoding="utf-8").read()
    assert s.count("<audio controls") == 2  # только слайды с фрагментом
    assert 'lang="en"' in s


def test_render_html_no_audio(real_slides, tmp_path):
    from renderers import render_html
    p = str(tmp_path / "out.html")
    render_html(real_slides, p, "Тест")
    assert "<audio controls" not in open(p, encoding="utf-8").read()
