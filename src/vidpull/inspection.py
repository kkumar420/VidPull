from typing import Any, cast

from yt_dlp import YoutubeDL


def inspect_url(url: str) -> Any:
    """
    Extract metadata from a video or playlist URL without downloading media.

    Playlist entries are extracted in flat mode to avoid fetching complete
    metadata for every video during initial playlist inspection.
    """
    ydl_options: dict[str, Any] = {
        "quiet": True,

        # Use Node.js to solve YouTube JavaScript challenges.
        "js_runtimes": {
            "node": {}
        },

        # Extract playlist entries without fully inspecting each video.
        "extract_flat": "in_playlist",
    }

    with YoutubeDL(cast(Any, ydl_options)) as ydl:
        info = ydl.extract_info(url, download=False)

    return info