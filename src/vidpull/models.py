from dataclasses import dataclass, field
from typing import Any


@dataclass
class DownloadPlan:
    """Stores the user's selected media assets and download settings."""

    url: str
    title: str
    assets: list[str]

    video: dict[str, Any] = field(default_factory=dict)
    audio: dict[str, Any] = field(default_factory=dict)
    subtitles: dict[str, Any] = field(default_factory=dict)

    download_thumbnail: bool = False