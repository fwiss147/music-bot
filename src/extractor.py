import asyncio
from dataclasses import dataclass
import functools
import re
import urllib.request
import html
import yt_dlp

from config import ytdl_options


@dataclass
class Song:
    title: str
    webpage_url: str
    duration: int
    duration_str: str
    thumbnail: str
    artist: str
    platform: str
    requester: object
    query: str
    stream_url: str

    @property
    def length(self) -> str:
        return self.duration_str


def get_platform_meta(platform: str) -> dict:
    meta_map = {
        "spotify": {"name": "Spotify", "icon": "https://cdn-icons-png.flaticon.com/512/174/174872.png"},
        "youtube": {"name": "YouTube", "icon": "https://cdn-icons-png.flaticon.com/512/1384/1384060.png"},
        "soundcloud": {"name": "SoundCloud", "icon": "https://cdn-icons-png.flaticon.com/512/145/145809.png"},
        "applemusic": {"name": "Apple Music", "icon": "https://cdn-icons-png.flaticon.com/512/732/732068.png"},
        "deezer": {"name": "Deezer", "icon": "https://cdn-icons-png.flaticon.com/512/5968/5968860.png"},
    }
    return meta_map.get(platform.lower(), meta_map["youtube"])


def _resolve_spotify_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        page = resp.read().decode("utf-8", errors="ignore")
    title_match = re.search(r'<meta property="og:title" content="([^"]+)"', page)
    desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', page)
    title = html.unescape(title_match.group(1)) if title_match else ""
    artist = ""
    if desc_match:
        desc = html.unescape(desc_match.group(1))
        artist = desc.split("·")[0].strip()
    if title:
        return f"{title} {artist}".strip()
    raise ValueError("Could not resolve Spotify URL.")


def _run_ydl(target: str) -> list[dict]:
    opts = ytdl_options()
    opts.update({
        "format": "bestaudio[protocol^=http]/bestaudio/best",
        "extract_flat": False,
        "socket_timeout": 30,
        "extractor_retries": 2,
        "ignoreerrors": True,
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "tv"]}},
    })
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=False)
        if not info:
            return []
        if "entries" in info:
            return [e for e in info["entries"] if e is not None]
        return [info]


def _extract_sync(search_target: str, platform: str) -> list[dict]:
    if platform == "spotify":
        search_terms = _resolve_spotify_url(search_target)
        query = f"ytsearch1:{search_terms}"
    elif platform == "soundcloud":
        if search_target.startswith(("http://", "https://")):
            query = search_target
        else:
            query = f"scsearch1:{search_target}"
    else:  # YouTube أو بحث عادي
        if search_target.startswith(("http://", "https://")):
            query = search_target
        else:
            query = f"ytsearch1:{search_target}"

    entries = _run_ydl(query)
    if entries:
        return entries

    raise ValueError("Empty playlist or search result.")


async def fetch_song(query: str, requester, platform_hint: str = "youtube") -> list[Song]:
    # تحديد المنصة بدقة من الرابط أو الكلمة المدخلة
    if "spotify.com" in query or "spotify.link" in query:
        platform_hint = "spotify"
    elif "soundcloud.com" in query:
        platform_hint = "soundcloud"
    elif "youtube.com" in query or "youtu.be" in query:
        platform_hint = "youtube"
    elif not query.startswith(("http://", "https://")) and platform_hint == "youtube":
        platform_hint = "youtube"

    search_target = query

    loop = asyncio.get_running_loop()
    try:
        data_list = await asyncio.wait_for(
            loop.run_in_executor(None, functools.partial(_extract_sync, search_target, platform_hint)),
            timeout=35.0,
        )
    except asyncio.TimeoutError:
        raise TimeoutError("Search timed out. Try again.")

    songs = []
    for data in data_list:
        url = query if platform_hint == "spotify" else (data.get("webpage_url") or data.get("url") or query)
        duration = int(data.get("duration") or 0)
        m, s = divmod(duration, 60)
        h, m = divmod(m, 60)
        dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        if duration == 0:
            dur_str = "LIVE"

        stream_url = None
        formats = data.get("formats") or []
        for f in formats:
            f_url = f.get("url", "")
            if f.get("acodec") != "none" and f_url and ".m3u8" not in f_url and f.get("protocol") in ("http", "https"):
                stream_url = f_url
                break
        if not stream_url:
            stream_url = data.get("url") or url

        songs.append(
            Song(
                title=data.get("title", "Unknown Track"),
                webpage_url=url,
                duration=duration,
                duration_str=dur_str,
                thumbnail=data.get("thumbnail") or "",
                artist=data.get("uploader") or data.get("artist") or "Unknown Artist",
                platform=platform_hint.lower(),
                requester=requester,
                query=query,
                stream_url=stream_url,
            )
        )
    return songs
