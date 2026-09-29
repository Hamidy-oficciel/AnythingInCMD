"""YouTube URL validation and yt-dlp stream extraction (pure Python, no native build)."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
SUPPORTED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


class StreamError(Exception):
    """Expected extraction failure with a user-friendly message."""


@dataclass(frozen=True)
class StreamInfo:
    title: str
    duration: float | None
    fps: float
    width: int
    height: int
    video_url: str
    audio_url: str


def extract_video_id(url: str) -> str | None:
    """Return the 11-char video id for a supported YouTube URL, else None."""
    url = url.strip()
    m = re.match(r"^https?://(?:[a-z]+\.)?youtube\.com/watch\?(?:.*&)?v=([^&#]+)", url, re.I)
    if m:
        vid = m.group(1)
        return vid if VIDEO_ID_PATTERN.match(vid) else None
    m = re.match(r"^https?://(?:[a-z]+\.)?youtube\.com/(?:embed|shorts|live)/([A-Za-z0-9_-]{11})",
                 url, re.I)
    if m:
        return m.group(1)
    m = re.match(r"^https?://youtu\.be/([A-Za-z0-9_-]{11})", url, re.I)
    return m.group(1) if m else None


def validate_youtube_url(url: str) -> bool:
    return extract_video_id(url) is not None


def _run_yt_dlp(args: list[str]) -> str:
    binary = shutil.which("yt-dlp")
    if not binary:
        raise StreamError("yt-dlp is not installed or not on PATH.")
    try:
        proc = subprocess.run([binary, *args], capture_output=True, text=True, timeout=60)
    except FileNotFoundError as exc:
        raise StreamError("yt-dlp was not found on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise StreamError("yt-dlp timed out while extracting the video.") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        hint = f"\n{detail[-1]}" if detail else ""
        raise StreamError(f"Could not extract this video.{hint}")
    return proc.stdout


def extract_streams(url: str, max_height: int = 360) -> StreamInfo:
    """Resolve direct stream URLs plus basic metadata via yt-dlp JSON output."""
    if not validate_youtube_url(url):
        raise StreamError("Invalid YouTube URL. Use a watch or youtu.be link.")
    fmt = f"bv*[height<={max_height}][ext=mp4]+ba[ext=m4a]/b[height<={max_height}]"
    raw = _run_yt_dlp(["-f", fmt, "--no-playlist", "-q", "--dump-json", url])
    import json

    try:
        data = json.loads(raw.splitlines()[0])
    except (json.JSONDecodeError, IndexError) as exc:
        raise StreamError("Unexpected yt-dlp output; could not parse streams.") from exc

    def pick(pred):
        for f in data.get("formats", []):
            if pred(f) and f.get("url"):
                return f
        return None

    video = pick(lambda f: f.get("vcodec", "none") != "none" and f.get("acodec", "none") == "none")
    audio = pick(lambda f: f.get("acodec", "none") != "none" and f.get("vcodec", "none") == "none")
    if video is None:
        video = pick(lambda f: f.get("vcodec", "none") != "none")
    if video is None:
        raise StreamError("No playable video stream found for this URL.")
    progressive_audio = audio if audio is not None else video

    return StreamInfo(
        title=data.get("title", "Untitled"),
        duration=data.get("duration"),
        fps=float(video.get("fps") or 25.0),
        width=int(video.get("width") or 640),
        height=int(video.get("height") or 360),
        video_url=video["url"],
        audio_url=progressive_audio["url"],
    )
