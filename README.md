# VidPull

**VidPull is an interactive command-line media downloader built with Python and [yt-dlp](https://github.com/yt-dlp/yt-dlp).** It lets you inspect a video or playlist, choose which media assets to download, configure the available quality options, and save the results locally.

VidPull is an early-stage project. It is designed as a straightforward terminal application rather than a graphical downloader.

## Features

### Single videos

- Inspect a URL before downloading and display the media assets reported by yt-dlp.
- Select video, audio-only, subtitles, and/or a thumbnail.
- Choose a maximum video resolution from the available options.
- Choose an FPS when multiple options are available at the selected resolution.
- Save video in MP4, MKV, or WebM containers.
- Select available audio-language tracks. Multiple selected tracks can be included in a video output where the source and container support them.
- Download audio-only tracks as MP3, M4A, OPUS, WAV, or FLAC. VidPull selects the best available source variant automatically.
- Download the preferred thumbnail independently of the media file.

### Playlists

- Download an entire playlist or select an individual entry.
- For full video playlists, set a maximum resolution. Each entry uses the best available quality at or below that limit.
- For full audio playlists, VidPull selects the best available source audio and converts it to MP3.
- Save playlist entries in a playlist-specific folder, with numbered filenames to preserve their order.
- Continue processing when an individual playlist entry fails and display a download summary.

### Subtitles

VidPull can identify uploaded subtitles and automatically generated captions, and offers SRT, VTT, and ASS as output formats. **Subtitle downloads are currently unreliable:** YouTube may respond with HTTP 429 (Too Many Requests), even when metadata inspection succeeds. This is caused by source-platform rate limiting and may not be resolved by retrying.

## Requirements

The following tools must be installed and available on your system:

- **Git** — to clone the repository.
- **Python 3.11 or later** — VidPull's minimum Python version.
- **[uv](https://docs.astral.sh/uv/)** — to create the project environment and install dependencies.
- **[Node.js 22 or later](https://nodejs.org/)** — used as yt-dlp's JavaScript runtime for supported YouTube extraction.
- **[FFmpeg and ffprobe](https://ffmpeg.org/)** — required for merging separate audio/video streams and for audio post-processing.

`ffmpeg`, `ffprobe`, and `node` must be discoverable through your system's `PATH`. After installing them, open a new terminal and verify that the commands below print version information:

```text
python --version
uv --version
node --version
ffmpeg -version
ffprobe -version
```

On Windows, if `python` is not recognised, try `py --version` or reinstall Python with the option to add it to `PATH` enabled.

## Installation

### Windows

1. Install **Python 3.11 or later** from [python.org](https://www.python.org/downloads/windows/). Enable the option to add Python to `PATH` during installation.
2. Install **Node.js 22 or later** from [nodejs.org](https://nodejs.org/en/download/).
3. Install **uv**. With [Windows Package Manager (winget)](https://learn.microsoft.com/en-us/windows/package-manager/winget/), open PowerShell or Windows Terminal and run:

   ```powershell
   winget install --id astral-sh.uv -e
   ```

   Alternatively, follow the [official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/).

4. Install FFmpeg. With winget, run:

   ```powershell
   winget install --id Gyan.FFmpeg -e
   ```

   You can also use the Windows builds from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/). Make sure the folder containing `ffmpeg.exe` and `ffprobe.exe` is added to `PATH`.

5. Close and reopen the terminal, then verify the requirements listed above.

### macOS

1. Install Python 3.11 or later from [python.org](https://www.python.org/downloads/macos/) or use your preferred package manager.
2. Install [Homebrew](https://brew.sh/) if it is not already installed.
3. Install uv, Node.js, and FFmpeg:

   ```bash
   brew install uv node ffmpeg
   ```

4. Verify the requirements listed above. If your Python installation is older than 3.11, install a newer version before continuing.

### Linux

1. Install Python 3.11 or later and Git using your distribution's package manager, or install Python from [python.org](https://www.python.org/downloads/).
2. Install **uv** using its official installer:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   Alternatively, use the [official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/) for your distribution.

3. Install **Node.js 22 or later** from [nodejs.org](https://nodejs.org/en/download/) or your distribution's package manager. Check the installed version; some distribution repositories provide older versions.
4. Install FFmpeg and ffprobe using your distribution's package manager. For Ubuntu or Debian:

   ```bash
   sudo apt update
   sudo apt install ffmpeg
   ```

5. Verify the requirements listed above.

### Clone and install VidPull

Once the prerequisites are installed, the remaining commands are the same on Windows, macOS, and Linux. Open PowerShell, Windows Terminal, Command Prompt, or your preferred Unix terminal and run:

```text
git clone <REPOSITORY_URL>
cd vidpull
uv sync
```

Replace `<REPOSITORY_URL>` with the clone URL of this GitHub repository. `uv sync` creates the project's virtual environment and installs the dependencies recorded in `pyproject.toml` and `uv.lock`.

## Usage

From the project directory, start VidPull:

```text
uv run vidpull
```

VidPull will prompt you for a video or playlist URL, inspect it, and guide you through the available choices. Select the assets you want, configure the relevant options, review the download plan, and confirm to begin.

To display the CLI help:

```text
uv run vidpull --help
```

## Download location

By default, VidPull saves files under the `Downloads/VidPull` folder in your user home directory:

- **Windows:** `C:\Users\<username>\Downloads\VidPull\`
- **macOS and Linux:** `~/Downloads/VidPull/`

Single-video downloads are saved directly in this directory. Full playlist downloads are organised in a subdirectory named after the playlist. Filenames include the media title and video ID to help distinguish files with similar titles.

## Notes and limitations

- VidPull uses yt-dlp for extraction and downloading. Source-platform changes can affect availability and behaviour.
- The current configuration does not import browser cookies or configure account authentication. Content that requires authentication may therefore be unavailable.
- YouTube may rate-limit requests. Subtitle downloads are particularly affected at present and may fail with HTTP 429.
- Full playlist video downloads are saved as MKV. Full playlist audio downloads are converted to MP3. Single-video downloads offer more output-format choices.
- Converting audio to a higher bitrate or a different format cannot improve the quality of the original source audio.
- FFmpeg and ffprobe are needed for post-processing, including merging separate streams and converting audio.

## Responsible use

Use VidPull only for media you have the right to download, and follow the terms and rules that apply to the content and service you use. You are responsible for ensuring that your use complies with applicable law and the source platform's terms.

## License

No license has been specified for this repository yet. Until a license is added, do not assume that the source code is available for reuse, redistribution, or modification under an open-source license.
