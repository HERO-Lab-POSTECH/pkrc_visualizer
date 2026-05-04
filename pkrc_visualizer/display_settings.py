"""Per-page display settings — dataclasses, YAML codec, Qt store.

The pure-data section (dataclasses + load/save) has no Qt deps so it can
be exercised without an event loop. The Qt store wrapper is added in a
later task.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class FramesSettings:
    map_axes_length_m: float = 1.0
    map_axes_line_width: int = 3
    robot_axes_length_m: float = 0.5
    robot_axes_line_width: int = 3
    label_font_size: int = 16
    map_label_color: str = "#ffff99"
    robot_label_color: str = "#99ff99"
    show_map_frame: bool = True
    show_robot_frame: bool = True


@dataclass
class CloudSettings:
    style: str = "points"            # points | spheres
    size: float = 2.0
    alpha: float = 1.0
    decay_max_points: int = 300_000
    color_transformer: str = "flat"  # flat | z | intensity
    flat_color: str = "#4fc3f7"
    color_min: float = 0.0
    color_max: float = 10.0


@dataclass
class PageDisplaySettings:
    background: str = "#1e1e1e"
    frames: FramesSettings = field(default_factory=FramesSettings)
    cloud: CloudSettings = field(default_factory=CloudSettings)


def settings_to_dict(s: PageDisplaySettings) -> dict[str, Any]:
    return asdict(s)


def settings_from_dict(d: dict[str, Any]) -> PageDisplaySettings:
    frames = FramesSettings(**d.get("frames", {}))
    cloud = CloudSettings(**d.get("cloud", {}))
    return PageDisplaySettings(
        background=d.get("background", PageDisplaySettings().background),
        frames=frames,
        cloud=cloud,
    )


def load_yaml(path: Path) -> dict[str, PageDisplaySettings]:
    """Load all pages' settings from YAML.

    On parse error, rename to <path>.bak and return empty dict so the
    caller falls back to defaults.
    """
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        path.rename(path.with_suffix(path.suffix + ".bak"))
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        k: settings_from_dict(v)
        for k, v in raw.items()
        if isinstance(v, dict)
    }


def save_yaml(path: Path, all_pages: dict[str, PageDisplaySettings]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialised = {k: settings_to_dict(v) for k, v in all_pages.items()}
    path.write_text(yaml.safe_dump(serialised, sort_keys=False))
