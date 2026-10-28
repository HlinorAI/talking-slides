"""Структурирование транскрипта в слайды презентации (офлайн, эвристики)."""

import re
from collections import Counter

# английские служебные слова — дополняют русские в STOPWORDS
EN_STOPWORDS = set(
    """the a an and or but if of at by for with about to from in on into over after
    is are was were be been being am do does did done have has had having will would
    shall should may might must can could this that these those there here it its
    i you he she we they them their his her our your my me him us who whom whose
    what which when where why how all any both each few more most other some such
    no nor not only own same so than too very just now then also because as until
    while again once during before between out up down off above below further
    dont don't cant can't wont won't im i'm youre you're thats that's really very
    okay ok well basically actually literally maybe probably lets let's gonna wanna
    like you know mean kind sort thing things something anything everything nothing
    one two first second next last good bad new right wrong yes""".split()
)

STOPWORDS = set(
    """и в во не что он на я с со как а то все всё она так его но да ты к у же вы за бы по
    только ее её мне было вот от меня еще ещё нет о об из ему теперь когда даже ну вдруг
    ли если уже или ни был него до вас нибудь опять уж вам ведь там потом себя ничего ей
    может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз
    тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом
    один почти мой тем чтобы нее кажется сейчас были куда зачем всех никогда сегодня
    можно при наконец два другой хоть после над больше тот через эти нас про всего них
    какая много три эту моя впрочем хорошо свою этой перед иногда лучше чуть том нельзя
    такой им более всегда конечно всю между это которые поэтому например значит ну ладно
    просто типа короче вообще даже именно скажем допустим вообщем""".split()
)

FILLER_START = re.compile(
    r"^(?:значит|ну|ладно|так|вот|короче|давайте|то есть|в общем|соответственно|"
    r"собственно|вообще|вот-с|ага|угу|окей|ок|хорошо|отлично|да|и|а)[,\s-]+",
    re.IGNORECASE,
)

# английские слова-паразиты в начале фразы: "So, basically...", "Okay, ..."
EN_FILLER_START = re.compile(
    r"^(?:so|well|okay|ok|right|now|basically|actually|literally|honestly|"
    r"anyway|look|listen|um|uh|hmm|er|ah|yeah|yes|alright|you know|i mean|"
    r"kind of|sort of|by the way)[,\s-]+",
    re.IGNORECASE,
)

SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+")
WORD = re.compile(r"[а-яёa-z-]{4,}", re.IGNORECASE)


def _chunk_long(text, limit=400):
    """Режет длинный фрагмент на части по границам предложений."""
    if len(text) <= limit:
        return [text]
    sentences = SENT_SPLIT.split(text)
    parts, cur = [], ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if cur and len(cur) + len(s) + 1 > limit:
            parts.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        parts.append(cur)
    return parts or [text]


def _keywords(text, top=12):
    words = [
        w.lower().strip("-")
        for w in WORD.findall(text)
        if w.lower() not in STOPWORDS and w.lower() not in EN_STOPWORDS
    ]
    return [w for w, _ in Counter(words).most_common(top)]


def _clean_sentence(s):
    s = s.strip()
    prev = None
    while prev != s:
        prev = s
        s = FILLER_START.sub("", s)
        s = EN_FILLER_START.sub("", s)
    # хвостовое «…»/«...» из транскрипта (обрыв речи) на слайде выглядит хуже,
    # чем его отсутствие
    s = re.sub(r"\s*[…\.]+\s*$", "", s)
    if s and s[0].isalpha() and s[0].islower():
        s = s[0].upper() + s[1:]
    return s


def _split_sentences(text):
    out = []
    for chunk in text.split("\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for s in SENT_SPLIT.split(chunk):
            s = _clean_sentence(s)
            if s:
                out.append(s)
    return out


def _trim(s, limit=70):
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;: ") + "…"


def _pick_title(sentences):
    for s in sentences[:4]:
        clean = _clean_sentence(s).rstrip(". ")
        first_word = clean.split()[0] if clean.split() else ""
        if len(clean) >= 25 and len(clean.split()) >= 4 \
                and "." not in first_word and not first_word.lower().startswith(("http", "www")):
            return clean
    return _clean_sentence(sentences[0]).rstrip(". ")


def build_slides(segments, target_chars=1100, max_chars=1600, min_pause=1.2):
    """segments: [{'start': float, 'end': float, 'text': str}] → слайды.

    Возвращает список слайдов: {'title', 'bullets', 'start', 'end'}.
    Логика: главы по паузам между репликами, тезисы — самые информативные
    предложения главы.
    """
    paragraphs, cur = [], []
    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue
        parts = _chunk_long(text, limit=400)
        for part in parts:
            if cur and (seg["start"] - cur[-1]["end"] >= min_pause or
                        sum(len(s["text"]) for s in cur) + len(part) > 400):
                paragraphs.append(cur)
                cur = []
            cur.append({"start": seg["start"], "end": seg["end"], "text": part})
            if sum(len(s["text"]) for s in cur) >= max_chars:
                paragraphs.append(cur)
                cur = []
    if cur:
        paragraphs.append(cur)

    chapters, cur, cur_len = [], [], 0
    for para in paragraphs:
        para_len = sum(len(s["text"]) for s in para)
        cur.append(para)
        cur_len += para_len
        if cur_len >= target_chars:
            chapters.append(cur)
            cur, cur_len = [], 0
    if cur:
        if chapters and cur_len < target_chars * 0.35:
            chapters[-1].extend(cur)
        else:
            chapters.append(cur)

    slides = []
    for chapter in chapters:
        segs = [s for para in chapter for s in para]
        text = " ".join(s["text"] for s in segs)
        sentences = _split_sentences(text)
        if not sentences:
            continue
        kws = _keywords(text)
        scored = []
        for i, s in enumerate(sentences):
            if not (40 <= len(s) <= 320):
                continue
            low = s.lower()
            score = sum(low.count(k) for k in kws) + (2 if i < 3 else 0)
            scored.append((score, i, s))
        # заголовок — первое существительное предложение главы;
        # он исключается из тезисов, чтобы не дублировать сам себя
        title_raw = _pick_title(sentences)
        bullets = [
            s for _, _, s in sorted(scored, key=lambda t: (-t[0], t[1]))
            if _clean_sentence(s).rstrip(" .") != title_raw.rstrip(" .")
        ][:5]
        bullets.sort(key=lambda s: sentences.index(s))
        if not bullets:
            bullets = [s for s in sentences if s != title_raw][:3] or sentences[:1]
        slides.append(
            {
                "title": _trim(title_raw, limit=130),
                # тезисы не укорачиваем: обрезанные на полуслове фразы
                # хуже длинного пункта, рендер переносит строки сам
                "bullets": [_clean_sentence(b) for b in bullets],
                "start": segs[0]["start"],
                "end": segs[-1]["end"],
            }
        )
    return slides


def build_slides_from_text(text, target_chars=1100, max_chars=1600):
    """Фолбэк для уже готового текста без таймкодов."""
    fake_segments = []
    t = 0.0
    for para in re.split(r"\n\s*\n", text):
        if para.strip():
            fake_segments.append({"start": t, "end": t, "text": para.strip()})
            t += 1.0
    slides = build_slides(fake_segments, target_chars, max_chars, min_pause=1e9)
    for s in slides:
        s["start"] = s["end"] = None
    return slides


def format_ts(sec):
    if sec is None:
        return ""
    sec = int(sec)
    return f"{sec // 60:02d}:{sec % 60:02d}"
