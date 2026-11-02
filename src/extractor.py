import asyncio
from dataclasses import dataclass
import functools
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


def _run_ydl(target: str) -> list[dict]:
    opts = ytdl_options()
    opts.update({
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


def _extract_sync(query: str, raw_query: str = "") -> list[dict]:
    entries = _run_ydl(query)
    if entries:
        return entries

    # Fallback أوتوماتيكي لـ SoundCloud إيلا يوتيوب بلوكا السيرفر
    fallback_q = raw_query or query.removeprefix("ytsearch:").removeprefix("scsearch:")
    if not fallback_q.startswith(("http://", "https://")):
        entries = _run_ydl(f"scsearch:{fallback_q}")
        if entries:
            return entries

    raise ValueError("Empty playlist or search result.")


async def fetch_song(query: str, requester, platform_hint: str = "youtube") -> list[Song]:
    search_target = query
    if not query.startswith(("http://", "https://")):
        prefix_map = {
            "spotify": "scsearch:",
            "youtube": "scsearch:",
            "soundcloud": "scsearch:",
        }
        pfx = prefix_map.get(platform_hint.lower(), "scsearch:")
        search_target = f"{pfx}{query}"

    loop = asyncio.get_running_loop()
    try:
        data_list = await asyncio.wait_for(
            loop.run_in_executor(None, functools.partial(_extract_sync, search_target, query)),
            timeout=35.0,
        )
    except asyncio.TimeoutError:
        raise TimeoutError("Search timed out. Try again.")

    songs = []
    for data in data_list:
        url = data.get("webpage_url") or data.get("url") or f"https://www.youtube.com/watch?v={data.get('id')}"
        duration = int(data.get("duration") or 0)
        m, s = divmod(duration, 60)
        h, m = divmod(m, 60)
        dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        if duration == 0:
            dur_str = "LIVE"

        stream_url = data.get("url")
        if not stream_url:
            formats = data.get("formats", [])
            for f in formats:
                if f.get("acodec") != "none" and f.get("url"):
                    stream_url = f["url"]
                    break

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
                stream_url=stream_url or url,
            )
        )
    return songs
