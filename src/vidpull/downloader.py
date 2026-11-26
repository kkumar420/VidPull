
from pathlib import Path
from typing import Any, cast

from yt_dlp import YoutubeDL

from vidpull.models import DownloadPlan


def _get_output_dir() -> Path:
    """Create and return VidPull's output directory."""
    output_dir = Path.home() / "Downloads" / "VidPull"
    output_dir.mkdir(parents=True, exist_ok=True)

    return output_dir


def build_video_format_selector(plan: DownloadPlan) -> str:
    """
    Build a yt-dlp format selector using the selected resolution,
    preferred FPS and audio tracks.
    """
    max_height = plan.video.get("max_height")

    if not isinstance(max_height, int) or max_height <= 0:
        raise ValueError("Invalid maximum video resolution.")

    fps = plan.video.get("fps")

    if fps is not None:
        if not isinstance(fps, (int, float)) or fps <= 0:
            raise ValueError("Invalid preferred FPS.")

        preferred = (
            f"bestvideo[height<={max_height}]"
            f"[fps={fps:g}]"
        )

        fallback = f"bestvideo[height<={max_height}]"

        video_selector = f"({preferred}/{fallback})"

    else:
        video_selector = f"bestvideo[height<={max_height}]"

    # Append the selected audio tracks, if any.
    selected_tracks = plan.audio.get("selected_tracks", [])
    audio_selectors = []

    for track in selected_tracks:
        format_ids = track.get("format_ids") or []

        if not format_ids:
            raise ValueError(
                "A selected audio track has no usable formats."
            )

        # Format IDs are ranked from best to worst.
        # Use / to allow yt-dlp to fall back to another variant.
        audio_selectors.append(
            f"({'/'.join(format_ids)})"
        )

    format_selector = video_selector

    if audio_selectors:
        format_selector += "+" + "+".join(audio_selectors)

    return format_selector


def download_video(plan: DownloadPlan) -> tuple[bool, Path]:
    """Download a video using the user's selected configuration."""
    if "video" not in plan.assets:
        raise ValueError("No video asset selected.")

    format_selector = build_video_format_selector(plan)

    output_dir = _get_output_dir()

    container = plan.video.get("container", "mkv")

    if container not in {"mp4", "mkv", "webm"}:
        raise ValueError("Unsupported output container.")

    selected_tracks = plan.audio.get("selected_tracks", [])

    ydl_options: dict[str, Any] = {
        "format": format_selector,

        "outtmpl": str(
            output_dir / "%(title)s [%(id)s].%(ext)s"
        ),

        # Merge separate video and audio streams into the chosen container.
        "merge_output_format": container,

        # Preserve multiple selected audio streams in the output.
        "allow_multiple_audio_streams": len(selected_tracks) > 1,

        "noplaylist": True,

        "js_runtimes": {
            "node": {}
        },
    }

    with YoutubeDL(cast(Any, ydl_options)) as ydl:
        exit_code = ydl.download([plan.url])

    return exit_code == 0, output_dir


def download_audio(
    plan: DownloadPlan
) -> tuple[list[dict[str, Any]], Path]:
    """Download selected audio tracks as separate files."""
    if "audio" not in plan.assets:
        raise ValueError("No audio-only asset selected.")

    output_format = plan.audio.get("output_format")

    supported_formats = {"mp3", "m4a", "opus", "wav", "flac"}

    if output_format not in supported_formats:
        raise ValueError("Invalid audio output format.")

    selected_tracks = plan.audio.get("selected_tracks", [])

    if not selected_tracks:
        raise ValueError("No audio tracks selected.")

    output_dir = _get_output_dir()
    results = []

    for track in selected_tracks:
        language = track.get("language") or "unknown"
        format_ids = track.get("format_ids") or []

        if not format_ids:
            results.append({
                "language": language,
                "success": False,
                "error": "No usable audio formats available.",
            })
            continue

        audio_selector = "/".join(format_ids)

        ydl_options: dict[str, Any] = {
            "format": f"({audio_selector})",

            "outtmpl": str(
                output_dir
                / f"%(title)s [%(id)s] - {language}.%(ext)s"
            ),

            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": output_format,
                    "preferredquality": "0",
                }
            ],

            "noplaylist": True,

            "js_runtimes": {
                "node": {}
            },

            "sleep_interval_requests": 1,
            "sleep_interval": 5,
            "max_sleep_interval": 10,
        }

        try:
            with YoutubeDL(cast(Any, ydl_options)) as ydl:
                exit_code = ydl.download([plan.url])

            results.append({
                "language": language,
                "success": exit_code == 0,
                "error": (
                    None if exit_code == 0 else "Download failed."
                ),
            })

        except Exception as error:
            results.append({
                "language": language,
                "success": False,
                "error": str(error),
            })

    return results, output_dir


def download_subtitles(
    plan: DownloadPlan
) -> tuple[list[dict[str, Any]], Path]:
    """Download selected uploaded or automatically generated subtitles."""
    if "subtitles" not in plan.assets:
        raise ValueError("No subtitles selected.")

    output_format = plan.subtitles.get("output_format")
    supported_formats = {"srt", "vtt", "ass"}

    if output_format not in supported_formats:
        raise ValueError("Unsupported subtitle output format.")

    selected_tracks = plan.subtitles.get("selected_tracks", [])

    if not selected_tracks:
        raise ValueError("No subtitle tracks selected.")

    output_dir = _get_output_dir()
    results = []

    for track in selected_tracks:
        language = track["language"]
        source = track["source"]

        if source not in {"manual", "automatic"}:
            results.append({
                "language": language,
                "source": source,
                "success": False,
                "error": "Unknown subtitle source.",
            })
            continue

        ydl_options: dict[str, Any] = {
            "skip_download": True,

            # Enable only the requested subtitle source.
            "writesubtitles": source == "manual",
            "writeautomaticsub": source == "automatic",

            "subtitleslangs": [language],
            "subtitlesformat": "best",
            "convertsubtitles": output_format,

            # Distinguish uploaded and automatic subtitle filenames.
            "outtmpl": str(
                output_dir
                / f"%(title)s [%(id)s] - {source}.%(ext)s"
            ),

            "noplaylist": True,

            "js_runtimes": {
                "node": {}
            },

            "sleep_interval_requests": 1,
            "sleep_interval": 5,
            "max_sleep_interval": 10,
        }

        try:
            with YoutubeDL(cast(Any, ydl_options)) as ydl:
                exit_code = ydl.download([plan.url])

            results.append({
                "language": language,
                "source": source,
                "success": exit_code == 0,
                "error": (
                    None
                    if exit_code == 0
                    else "Subtitle download failed."
                ),
            })

        except Exception as error:
            results.append({
                "language": language,
                "source": source,
                "success": False,
                "error": str(error),
            })

    return results, output_dir


def download_thumbnail(plan: DownloadPlan) -> tuple[bool, Path]:
    """Download the preferred thumbnail without downloading the media."""
    if not plan.download_thumbnail:
        raise ValueError("No thumbnail selected.")

    output_dir = _get_output_dir()

    ydl_options: dict[str, Any] = {
        "quiet": False,
        "skip_download": True,
        "writethumbnail": True,

        "outtmpl": str(
            output_dir / "%(title)s [%(id)s].%(ext)s"
        ),

        "noplaylist": True,

        "js_runtimes": {
            "node": {}
        },

        "sleep_interval_requests": 1,
        "sleep_interval": 5,
        "max_sleep_interval": 10,
    }

    with YoutubeDL(cast(Any, ydl_options)) as ydl:
        exit_code = ydl.download([plan.url])

    return exit_code == 0, output_dir


def build_playlist_format_selector(
    media_type: str,
    quality: str,
) -> str:
    """
    Build a format selector for playlist downloads.

    Video quality acts as a maximum height, not a required resolution.
    Audio downloads always use the best available source audio.
    """
    if media_type == "audio":
        return "bestaudio/best"

    if media_type != "video":
        raise ValueError("Invalid playlist media type.")

    if quality == "best":
        return "bestvideo+bestaudio/best"

    if not quality.endswith("p") or not quality[:-1].isdigit():
        raise ValueError("Invalid video quality.")

    max_height = int(quality[:-1])

    if max_height <= 0:
        raise ValueError("Invalid video quality.")

    return (
        f"bestvideo[height<={max_height}]"
        f"+bestaudio/"
        f"best[height<={max_height}]"
    )


def download_playlist(
    info: dict[str, Any],
    media_type: str,
    quality: str,
) -> dict[str, Any]:
    """Download an entire playlist as video or audio."""
    if media_type not in {"video", "audio"}:
        raise ValueError("Invalid playlist media type.")

    playlist_url = (
        info.get("webpage_url")
        or info.get("original_url")
    )

    if (
        not isinstance(playlist_url, str)
        or not playlist_url.startswith("http")
    ):
        raise ValueError("Could not determine playlist URL.")

    format_selector = build_playlist_format_selector(
        media_type,
        quality,
    )

    if media_type == "video":
        postprocessors = []
        merge_output_format = "mkv"

    else:
        postprocessors = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            }
        ]
        merge_output_format = None

    output_dir = _get_output_dir()

    # Track completed and failed entries by video ID.
    completed = {}
    failed = {}

    def progress_hook(data: dict[str, Any]) -> None:
        """Record the outcome of individual playlist downloads."""
        status = data.get("status")

        if status not in {"finished", "error"}:
            return

        video_info = data.get("info_dict") or {}

        video_id = video_info.get("id") or video_info.get("title")
        title = video_info.get("title") or "Unknown title"

        if not video_id:
            return

        if status == "finished":
            completed[video_id] = title
            failed.pop(video_id, None)

        else:
            failed[video_id] = title
            completed.pop(video_id, None)

    ydl_options: dict[str, Any] = {
        "format": format_selector,

        "outtmpl": str(
            output_dir
            / "%(playlist_title)s"
            / "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"
        ),

        "merge_output_format": merge_output_format,
        "postprocessors": postprocessors,

        # Process the whole playlist rather than a single entry.
        "noplaylist": False,

        # Continue processing when an individual entry fails.
        "ignoreerrors": True,

        "progress_hooks": [progress_hook],

        "js_runtimes": {
            "node": {}
        },

        "sleep_interval_requests": 1,
        "sleep_interval": 5,
        "max_sleep_interval": 10,
    }

    with YoutubeDL(cast(Any, ydl_options)) as ydl:
        exit_code = ydl.download([playlist_url])

    expected_count = (
        info.get("playlist_count")
        or len(info.get("entries") or [])
    )

    return {
        "success": exit_code == 0 and not failed,
        "completed": list(completed.values()),
        "failed": list(failed.values()),
        "expected_count": expected_count,
        "output_dir": output_dir,
    }
