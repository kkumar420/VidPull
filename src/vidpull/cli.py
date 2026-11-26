import typer
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from yt_dlp.utils import DownloadError

from vidpull.inspection import inspect_url
from vidpull.models import DownloadPlan
from vidpull.downloader import (
    download_video,
    download_audio,
    download_subtitles,
    download_thumbnail,
    download_playlist,
)


app = typer.Typer(
    add_completion=False,
    no_args_is_help=False
)

console = Console()


def configure_video(info):

    formats = info.get("formats") or []

    # Find formats containing an actual video stream.
    video_formats = [
        fmt for fmt in formats
        if fmt.get("vcodec") not in (None, "none")
        and isinstance(fmt.get("height"), (int, float))
    ]

    if not video_formats:
        console.print("[red]No usable video formats found.[/red]")
        return {}

    # Discover available resolutions.
    resolutions = sorted({
        int(fmt["height"])
        for fmt in video_formats
        if fmt["height"] > 0
    })

    if not resolutions:
        console.print("[red]No usable resolutions found.[/red]")
        return {}

    console.print("\n[bold]Available resolutions[/bold]")

    for height in resolutions:
        console.print(f"  • {height}p")

    # Let the user choose a maximum resolution.
    quality_choices = ["best"] + [
        f"{height}p" for height in resolutions
    ]

    selected_quality = Prompt.ask(
        "\nMaximum video quality",
        choices=quality_choices,
        default="best"
    )

    if selected_quality == "best":
        max_height = resolutions[-1]
    else:
        max_height = int(selected_quality[:-1])

    console.print(f"[green]Maximum resolution: {max_height}p[/green]")

    # Discover FPS values at the selected resolution.
    fps_values = sorted({
        float(fmt["fps"])
        for fmt in video_formats
        if fmt.get("height") == max_height
        and isinstance(fmt.get("fps"), (int, float))
        and fmt["fps"] > 0
    })

    selected_fps = None

    if len(fps_values) > 1:

        fps_options = {}

        for fps in fps_values:
            label = f"{fps:.2f}".rstrip("0").rstrip(".")
            fps_options[label] = fps

        fps_choices = ["best"] + list(fps_options.keys())

        console.print("\n[bold]Available FPS options[/bold]")

        for label in fps_options:
            console.print(f"  • {label} FPS")

        fps_choice = Prompt.ask(
            "\nPreferred FPS",
            choices=fps_choices,
            default="best"
        )

        if fps_choice != "best":
            selected_fps = fps_options[fps_choice]

    elif len(fps_values) == 1:

        console.print(
            f"\nOnly one FPS available at {max_height}p: "
            f"{fps_values[0]:g}"
        )

    else:
        console.print("\nFPS information unavailable.")

    container = Prompt.ask(
        "\nVideo output container",
        choices=["mp4", "mkv", "webm"],
        default="mkv"
    )

    return {
        "max_height": max_height,
        "fps": selected_fps,
        "container": container,
    }


def configure_audio(info, selected_assets):

    formats = info.get("formats") or []

    # Find audio-only formats.
    audio_formats = [
        fmt for fmt in formats
        if fmt.get("resolution") == "audio only"
        or (
            fmt.get("vcodec") == "none"
            and fmt.get("acodec") not in (None, "none")
        )
    ]

    if not audio_formats:
        console.print(
            "[yellow]No identifiable audio formats found.[/yellow]"
        )
        return {}

    # Group available formats by reported language.
    audio_tracks = {}

    for fmt in audio_formats:

        language = fmt.get("language") or "unknown"

        audio_tracks.setdefault(language, []).append(fmt)

    track_languages = sorted(
        audio_tracks,
        key=lambda language: (language == "unknown", language)
    )

    console.print("\n[bold cyan]AUDIO TRACK SELECTION[/bold cyan]")

    # Display available tracks.
    for index, language in enumerate(track_languages, start=1):

        if language == "unknown":
            label = "Unidentified audio (language unavailable)"
        else:
            label = language

        console.print(f"[cyan][{index}][/cyan] {label}")

    # Collect multiple track selections.
    while True:

        selection = Prompt.ask(
            "\nSelect audio tracks (comma-separated)",
            default="1"
        )

        try:
            selected_numbers = {
                int(item.strip())
                for item in selection.split(",")
                if item.strip()
            }

        except ValueError:
            console.print("[red]Enter valid numbers.[/red]")
            continue

        if not selected_numbers:
            console.print("[red]Select at least one track.[/red]")
            continue

        if any(
            number < 1 or number > len(track_languages)
            for number in selected_numbers
        ):
            console.print("[red]Invalid selection. Try again.[/red]")
            continue

        break

    selected_tracks = []

    for number in sorted(selected_numbers):

        language = track_languages[number - 1]
        variants = audio_tracks[language]

        # Rank source variants from best to worst.
        variants = sorted(
            variants,
            key=lambda fmt: (
                fmt.get("abr") or fmt.get("tbr") or 0,
                fmt.get("audio_channels") or 0,
                fmt.get("asr") or 0,
                fmt.get("filesize_approx") or 0,
                "high" in (fmt.get("format_note") or "").lower(),
            ),
            reverse=True
        )

        selected_tracks.append({
            "language": language if language != "unknown" else None,
            "format_ids": [
                fmt["format_id"]
                for fmt in variants
                if fmt.get("format_id") is not None
            ]
        })

    console.print(
        "\n[green]Source audio quality: Best available (automatic)[/green]"
    )

    # Ask for output format only for audio-only downloads.
    output_format = None

    if "audio" in selected_assets:

        output_format = Prompt.ask(
            "\nAudio output format",
            choices=["mp3", "m4a", "opus", "wav", "flac"],
            default="mp3"
        )

    return {
        "selected_tracks": selected_tracks,
        "output_format": output_format,
    }


def configure_subtitles(info):

    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}

    subtitle_options = []

    # Collect manually uploaded subtitles first.
    for language, entries in sorted(manual.items()):

        if language == "live_chat":
            continue

        language_name = next(
            (
                entry.get("name")
                for entry in entries
                if entry.get("name")
            ),
            language
        )

        subtitle_options.append({
            "language": language,
            "source": "manual",
            "label": f"{language_name} ({language}) — Uploaded"
        })

    # Collect automatically generated captions.
    for language, entries in sorted(automatic.items()):

        if language == "live_chat":
            continue

        language_name = next(
            (
                entry.get("name")
                for entry in entries
                if entry.get("name")
            ),
            language
        )

        subtitle_options.append({
            "language": language,
            "source": "automatic",
            "label": f"{language_name} ({language}) — Automatic"
        })

    if not subtitle_options:
        console.print("[yellow]No subtitles available.[/yellow]")
        return {}

    console.print("\n[bold cyan]SUBTITLE SELECTION[/bold cyan]")

    for index, option in enumerate(subtitle_options, start=1):
        console.print(f"[cyan][{index}][/cyan] {option['label']}")

    # Collect multiple selections.
    while True:

        selection = Prompt.ask(
            "\nSelect subtitles (comma-separated)",
            default="1"
        )

        try:
            selected_numbers = {
                int(item.strip())
                for item in selection.split(",")
                if item.strip()
            }

        except ValueError:
            console.print("[red]Enter valid numbers.[/red]")
            continue

        if not selected_numbers:
            console.print("[red]Select at least one subtitle track.[/red]")
            continue

        if any(
            number < 1 or number > len(subtitle_options)
            for number in selected_numbers
        ):
            console.print("[red]Invalid selection. Try again.[/red]")
            continue

        break

    selected_tracks = [
        subtitle_options[number - 1]
        for number in sorted(selected_numbers)
    ]

    output_format = Prompt.ask(
        "\nSubtitle output format",
        choices=["srt", "vtt", "ass"],
        default="srt"
    )

    return {
        "selected_tracks": selected_tracks,
        "output_format": output_format
    }


def handle_video(info):

    console.print("\n[bold green]Single video detected![/bold green]")
    console.print(f"Title: {info.get('title', 'Unknown')}")

    formats = info.get("formats") or []

    has_video = any(
        fmt.get("vcodec") not in (None, "none")
        for fmt in formats
    )

    has_audio = any(
        fmt.get("resolution") == "audio only"
        or fmt.get("acodec") not in (None, "none")
        for fmt in formats
    )

    subtitles = info.get("subtitles") or {}
    captions = info.get("automatic_captions") or {}

    # Exclude live chat from subtitle availability.
    subtitles = {
        lang: tracks
        for lang, tracks in subtitles.items()
        if lang != "live_chat"
    }

    thumbnails = info.get("thumbnails") or []
    has_thumbnail = bool(info.get("thumbnail") or thumbnails)

    # Display available assets.
    table = Table(title="Available Assets")

    table.add_column("Asset")
    table.add_column("Availability")

    table.add_row(
        "Video",
        "Available" if has_video else "Unavailable"
    )
    table.add_row(
        "Audio",
        "Available" if has_audio else "Unavailable"
    )
    table.add_row("Subtitles", f"{len(subtitles)} languages")
    table.add_row("Auto captions", f"{len(captions)} languages")
    table.add_row("Thumbnails", f"{len(thumbnails)} available")

    console.print(table)

    # Construct the selection menu dynamically.
    available_assets = []

    if has_video:
        available_assets.append(
            ("video", "Video (with audio where available)")
        )

    if has_audio:
        available_assets.append(("audio", "Audio-only"))

    if subtitles or captions:
        available_assets.append(("subtitles", "Subtitles"))

    if has_thumbnail:
        available_assets.append(("thumbnail", "Thumbnail"))

    if not available_assets:
        console.print("[red]No supported assets found.[/red]")
        return

    console.print("\n[bold]Select the assets you want to download:[/bold]")

    for index, (asset, label) in enumerate(available_assets, start=1):
        console.print(f"[cyan][{index}][/cyan] {label}")

    default = "1"

    while True:

        selection = Prompt.ask(
            "\nSelect assets (comma-separated, e.g. 1,3,4)",
            default=default
        )

        selected_numbers = {
            item.strip()
            for item in selection.split(",")
            if item.strip()
        }

        valid_numbers = {
            str(index)
            for index in range(1, len(available_assets) + 1)
        }

        invalid_numbers = selected_numbers - valid_numbers

        if invalid_numbers:
            console.print("[red]Invalid selection. Try again.[/red]")
            continue

        if not selected_numbers:
            console.print("[red]Select at least one asset.[/red]")
            continue

        break

    selected_assets = [
        asset
        for index, (asset, label) in enumerate(
            available_assets,
            start=1
        )
        if str(index) in selected_numbers
    ]

    # Configure video only if selected.
    video_settings = {}

    if "video" in selected_assets:

        console.print("\n[bold cyan]VIDEO CONFIGURATION[/bold cyan]")

        video_settings = configure_video(info)

        if not video_settings:
            console.print("[red]Video configuration failed.[/red]")
            return

    # Configure audio for video or audio-only downloads.
    audio_settings = {}

    if "audio" in selected_assets or (
        "video" in selected_assets and has_audio
    ):

        audio_settings = configure_audio(info, selected_assets)

        if not audio_settings.get("selected_tracks"):
            console.print("[red]No usable audio tracks selected.[/red]")
            return

    # Configure subtitles only if selected.
    subtitle_settings = {}

    if "subtitles" in selected_assets:

        subtitle_settings = configure_subtitles(info)

        if not subtitle_settings:
            console.print("[red]No usable subtitles selected.[/red]")
            return

    # Construct the download plan.
    plan = DownloadPlan(
        url=info.get("webpage_url") or info.get("original_url") or "",
        title=info.get("title") or "Unknown",
        assets=selected_assets,
        video=video_settings,
        audio=audio_settings,
        subtitles=subtitle_settings,
        download_thumbnail="thumbnail" in selected_assets,
    )

    # Display the download plan.
    console.print("\n")

    console.print(
        Panel.fit(
            Text(f"{plan.title}\n{plan.url}"),
            title="Download Plan",
            border_style="green"
        )
    )

    console.print("\n[bold]Selected assets:[/bold]")

    for asset in plan.assets:
        console.print(f"  ✓ {asset}")

    if plan.video:

        console.print("\n[bold]Video configuration:[/bold]")
        console.print(f"Maximum resolution: {plan.video['max_height']}p")
        console.print(f"FPS: {plan.video['fps'] or 'Automatic'}")
        console.print(f"Container: {plan.video['container'].upper()}")

    if plan.audio:

        console.print("\n[bold]Audio configuration:[/bold]")

        for track in plan.audio["selected_tracks"]:

            console.print(
                f"Track: {track['language'] or 'Unidentified'}"
            )

        if plan.audio["output_format"]:
            console.print(
                f"Output format: {plan.audio['output_format'].upper()}"
            )

    if plan.subtitles:

        console.print("\n[bold]Subtitle configuration:[/bold]")

        for track in plan.subtitles["selected_tracks"]:
            console.print(
                f"{track['language']} — {track['source']}"
            )

        console.print(
            f"Output format: {plan.subtitles['output_format'].upper()}"
        )

    if plan.download_thumbnail:
        console.print("\nThumbnail: Yes")

    # Defensive check: don't start downloads if an unsupported asset is selected.
    unsupported_assets = set(plan.assets) - {
        "video",
        "audio",
        "subtitles",
        "thumbnail",
    }

    if unsupported_assets:

        console.print(
            f"\n[yellow]Not implemented yet: "
            f"{', '.join(sorted(unsupported_assets))}[/yellow]"
        )

        console.print(
            "[yellow]No downloads will be started until all "
            "selected assets are supported.[/yellow]"
        )

        return

    # ONE confirmation for the entire download plan.
    if not Confirm.ask("\nStart downloading?", default=True):

        console.print("\n[yellow]Download cancelled.[/yellow]")
        return

    output_dir = Path.home() / "Downloads" / "VidPull"

    # Execute video download if selected.
    if "video" in plan.assets:

        try:

            console.print("\n[bold cyan]Downloading video...[/bold cyan]")

            success, output_dir = download_video(plan)

            if success:
                console.print("[green]Video download completed![/green]")
            else:
                console.print("[red]Video download failed.[/red]")

        except Exception as error:

            console.print(f"[red]Video download failed: {error}[/red]")

    # Execute audio-only downloads if selected.
    if "audio" in plan.assets:

        try:

            console.print("\n[bold cyan]Downloading audio tracks...[/bold cyan]")

            results, output_dir = download_audio(plan)

            for result in results:

                if result["success"]:

                    console.print(
                        f"[green]✓ {result['language']}: "
                        f"Download completed[/green]"
                    )

                else:

                    console.print(
                        f"[red]✗ {result['language']}: "
                        f"{result['error']}[/red]"
                    )

        except Exception as error:

            console.print(f"[red]Audio download failed: {error}[/red]")

    # Download subtitles if selected.
    if "subtitles" in plan.assets:

        try:

            console.print(
                "\n[bold cyan]Downloading subtitles...[/bold cyan]"
            )

            results, output_dir = download_subtitles(plan)

            for result in results:

                label = (
                    f"{result['language']} "
                    f"({result['source']})"
                )

                if result["success"]:

                    console.print(
                        f"[green]✓ {label}: Download completed[/green]"
                    )

                else:

                    console.print(
                        f"[red]✗ {label}: {result['error']}[/red]"
                    )

        except Exception as error:

            console.print(
                f"[red]Subtitle download failed: {error}[/red]"
            )

    if plan.download_thumbnail:

        try:
            console.print("\n[bold]Downloading thumbnail...[/bold]")
            success, output_dir = download_thumbnail(plan)

            if success:
                console.print(
                    "[green]✓ Thumbnail downloaded successfully![/green]"
                )
            else:
                console.print("[red]✗ Thumbnail download failed.[/red]")

        except Exception as error:
            console.print(f"[red]Thumbnail download failed: {error}[/red]")

    console.print(f"\nSaved to: {output_dir}")


def handle_playlist(info):

    console.print("\n[bold green]Playlist detected![/bold green]")

    entries = info.get("entries") or []
    count = info.get("playlist_count") or len(entries)

    console.print(f"Title: {info.get('title', 'Unknown')}")
    console.print(f"Videos: {count}")

    choice = Prompt.ask(
        "\nDownload entire playlist or an individual video?",
        choices=["playlist", "individual"],
        default="playlist"
    )

    if choice == "playlist":

        console.print("\n[bold]Playlist configuration[/bold]")

        media_type = Prompt.ask(
            "Download type",
            choices=["video", "audio"],
            default="video"
        )

        if media_type == "video":
            quality = Prompt.ask(
                "Maximum quality",
                choices=[
                    "144p", "240p", "360p", "480p",
                    "720p", "1080p", "1440p", "2160p",
                    "best"
                ],
                default="best"
            )

        else:
            quality = "best"

        console.print("\n[bold]Playlist Download Plan[/bold]")
        console.print(f"Playlist: {info.get('title', 'Unknown')}")
        console.print(f"Videos: {count}")
        console.print(f"Media type: {media_type}")
        if media_type == "video":
            console.print(f"Maximum quality: {quality}")
        else:
            console.print("Audio quality: Best available")

        if not Confirm.ask("\nStart downloading?", default=True):
            console.print("[yellow]Download cancelled.[/yellow]")
            return

        console.print("\n[bold green]Starting playlist download...[/bold green]")

        try:
            result = download_playlist(info, media_type, quality)

        except Exception as error:
            console.print(f"\n[red]Playlist download failed: {error}[/red]")
            return

        console.print("\n[bold]Playlist Download Summary[/bold]")

        completed = result["completed"]
        failed = result["failed"]

        console.print(f"[green]Completed: {len(completed)}[/green]")

        for title in completed:
            console.print(f"  ✓ {title}")

        console.print(f"\n[red]Failed: {len(failed)}[/red]")

        for title in failed:
            console.print(f"  ✗ {title}")

        console.print(f"\nFiles saved to: {result['output_dir']}")

        if result["expected_count"] is not None:
            reported = len(completed) + len(failed)
            unreported = max(0, result["expected_count"] - reported)

            if unreported:
                console.print(
                    f"[yellow]Unreported entries: {unreported}[/yellow]"
                )

    else:

        if not entries:
            console.print("[red]No playlist entries were found.[/red]")
            return

        console.print("\n[bold]Playlist entries[/bold]")

        for index, entry in enumerate(entries, start=1):
            title = entry.get("title") or "Unknown title"
            console.print(f"[{index}] {title}", markup=False)

        while True:
            selection = Prompt.ask(
                "\nEnter the video number you want",
                default="1"
            )

            try:
                selection = int(selection)

                if 1 <= selection <= len(entries):
                    break

                console.print(
                    f"[red]Please enter a number between 1 and {len(entries)}.[/red]"
                )

            except ValueError:
                console.print("[red]Please enter a valid number.[/red]")

        selected_entry = entries[selection - 1]

        # Flat playlist entries may contain either a complete URL or just an ID.
        selected_url = (
            selected_entry.get("webpage_url")
            or selected_entry.get("url")
        )

        if not selected_url:
            console.print("[red]Could not determine the selected video's URL.[/red]")
            return

        if not selected_url.startswith(("http://", "https://")):
            extractor = (
                selected_entry.get("ie_key")
                or selected_entry.get("extractor_key")
                or info.get("extractor_key")
                or ""
            )

            if "youtube" in extractor.lower():
                selected_url = (
                    f"https://www.youtube.com/watch?v={selected_url}"
                )
            else:
                console.print(
                    "[red]Could not resolve this playlist entry's URL.[/red]"
                )
                return

        console.print("\n[bold green]Inspecting selected video...[/bold green]")

        try:
            video_info = inspect_url(selected_url)
        except Exception as error:
            console.print(f"[red]Could not inspect video: {error}[/red]")
            return

        handle_video(video_info)


@app.callback(invoke_without_command=True)
def main():

    console.print(
        Panel.fit(
            "[bold cyan]VidPull[/bold cyan]\n"
            "Interactive Media Downloader",
            border_style="cyan"
        )
    )

    url = Prompt.ask(
        "\n[bold]Enter video or playlist URL[/bold]"
    ).strip()

    if not url:
        console.print("[red]No URL provided.[/red]")
        raise typer.Exit(code=1)

    try:

        with console.status("Inspecting URL...", spinner="dots"):
            info = inspect_url(url)

    except DownloadError as error:

        console.print(f"[red]Extraction failed: {error}[/red]")
        raise typer.Exit(code=1)

    entries = info.get("entries")
    is_playlist = info.get("_type") == "playlist" or entries is not None

    if is_playlist:
        handle_playlist(info)
    else:
        handle_video(info)


if __name__ == "__main__":
    app()
