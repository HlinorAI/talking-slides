"""Скачивание аудиодорожки с видеохостингов через yt-dlp.

Прогресс — в emit_fn (JSON-строки, как у пайплайна). Возвращает
(путь к m4a, заголовок видео).
"""

import os
import time

from util import safe_stem, t


def download_audio(url, outdir, emit_fn=None, ui_lang="en"):
    import yt_dlp

    os.makedirs(outdir, exist_ok=True)
    state = {"last_pct": -100.0, "last_ts": 0.0}

    def hook(d):
        if emit_fn is None:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes")
            now = time.monotonic()
            if not total or not done:
                return
            pct = done / total
            # шлём не чаще, чем каждые 2% или 0.5 с
            if (pct - state["last_pct"] >= 0.02) or (now - state["last_ts"] >= 0.5):
                state["last_pct"] = pct
                state["last_ts"] = now
                emit_fn(stage="download", pct=min(1.0, pct))
        elif d.get("status") == "finished":
            emit_fn(stage="download", pct=1.0)

    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(outdir, "%(id)s.%(ext)s"),
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "192"}
        ],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "progress_hooks": [hook],
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        requested = info.get("requested_downloads") or []
        path = None
        if requested and requested[0].get("filepath"):
            path = requested[0]["filepath"]
        if not path or not os.path.exists(path):
            path = os.path.splitext(ydl.prepare_filename(info))[0] + ".m4a"
        if not os.path.exists(path):
            raise RuntimeError(t("download_no_file", ui_lang, url=url))

    title = (info.get("title") or "").strip() or os.path.splitext(os.path.basename(path))[0]
    return path, title, safe_stem(title)
