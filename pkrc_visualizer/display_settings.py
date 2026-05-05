"""Per-page display settings — dataclasses, YAML codec, Qt store.

The pure-data section (dataclasses + load/save) has no Qt deps so it can
be exercised without an event loop. The Qt store wrapper is added in a
later task.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
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
    style: str = "points"            # points | square | spheres
    size: float = 2.0
    size_unit: str = "meters"        # pixels | meters
    alpha: float = 1.0
    decay_seconds: float = 30.0      # 0.0 disables decay (accumulate forever, capped by HARD_MAX)
    color_transformer: str = "flat"  # flat | z | intensity
    flat_color: str = "#4fc3f7"
    color_min: float = 0.0
    color_max: float = 10.0


@dataclass
class ImagePanelSettings:
    topic_name: str = ""
    msg_type: str = "Image"  # "Image" | "CompressedImage"
    object_name: str = ""    # QDockWidget objectName for restoreState matching


@dataclass
class ImageLayoutSettings:
    panels: list[ImagePanelSettings] = field(default_factory=list)
    # base64(QMainWindow.saveState()) — see pages/image_page.py.
    # Empty string = first launch / migration / corrupted: fall back to default
    # left-to-right horizontal dock arrangement.
    dock_state: str = ""


@dataclass
class PageDisplaySettings:
    background: str = "#1e1e1e"
    frames: FramesSettings = field(default_factory=FramesSettings)
    cloud: CloudSettings = field(default_factory=CloudSettings)
    image: ImageLayoutSettings = field(default_factory=ImageLayoutSettings)


_DEFAULTS = PageDisplaySettings()


def settings_to_dict(s: PageDisplaySettings) -> dict[str, Any]:
    return asdict(s)


def _filter_known(cls, data: dict[str, Any]) -> dict[str, Any]:
    """Drop keys that the dataclass doesn't declare.

    Forward-compat: a YAML written by a future version with extra fields
    must not crash older readers — unknown fields fall back to defaults.
    """
    known = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in known}


def settings_from_dict(d: dict[str, Any]) -> PageDisplaySettings:
    frames = FramesSettings(**_filter_known(FramesSettings, d.get("frames", {})))
    cloud = CloudSettings(**_filter_known(CloudSettings, d.get("cloud", {})))
    image_dict = d.get("image", {})
    if not isinstance(image_dict, dict):
        image_dict = {}
    raw_panels = image_dict.get("panels", [])
    panels = [
        ImagePanelSettings(**_filter_known(ImagePanelSettings, p))
        for p in raw_panels if isinstance(p, dict)
    ]
    # _filter_known leaves the raw `panels` list in place; immediately
    # override it with the dataclass-converted list above.
    image = ImageLayoutSettings(
        **{
            **_filter_known(ImageLayoutSettings, image_dict),
            "panels": panels,
        }
    )
    return PageDisplaySettings(
        background=d.get("background", _DEFAULTS.background),
        frames=frames,
        cloud=cloud,
        image=image,
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


from PyQt5.QtCore import QObject, QTimer, pyqtSignal


DEFAULT_PATH = Path.home() / ".config" / "pkrc_visualizer" / "display_settings.yaml"

# Atomic cross-field guard: when size_unit flips, the stale size value
# from the previous unit might be 6 orders of magnitude off in the new
# one (e.g. 10 px -> 10 m splat radius). Without clamping inside the
# same store transaction, the panel-side debounce delivers the
# size_unit change first and the view briefly paints a giant splat
# that freezes the GPU before the size update arrives.
SIZE_UNIT_THRESHOLD = 1.0
SAFE_SIZE_FOR_PIXELS = 2.0
SAFE_SIZE_FOR_METERS = 0.05


def _safe_size_for_unit(unit: str, current: float) -> float:
    if unit == "meters" and current > SIZE_UNIT_THRESHOLD:
        return SAFE_SIZE_FOR_METERS
    if unit == "pixels" and current < SIZE_UNIT_THRESHOLD:
        return SAFE_SIZE_FOR_PIXELS
    return current


class DisplaySettingsStore(QObject):
    """Qt-aware in-memory settings cache with debounced YAML persistence."""

    changed = pyqtSignal(str, object)  # page_key, PageDisplaySettings

    def __init__(self, path: Path | None = None, debounce_ms: int = 500) -> None:
        super().__init__()
        self._path = path or DEFAULT_PATH
        self._pages: dict[str, PageDisplaySettings] = load_yaml(self._path)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(debounce_ms)
        self._save_timer.timeout.connect(self._flush)

    def get(self, page_key: str) -> PageDisplaySettings:
        return self._pages.setdefault(page_key, PageDisplaySettings())

    def update(self, page_key: str, path: str, value: Any) -> None:
        page = self.get(page_key)
        parts = path.split(".")
        obj = page
        for part in parts[:-1]:
            obj = getattr(obj, part)
        last = parts[-1]
        if not hasattr(obj, last):
            raise KeyError(f"unknown setting: {page_key}.{path}")
        setattr(obj, last, value)
        if path == "cloud.size_unit":
            page.cloud.size = _safe_size_for_unit(value, page.cloud.size)
        self.changed.emit(page_key, page)
        self._save_timer.start()

    def reset(self, page_key: str, section: str | None = None) -> None:
        defaults = PageDisplaySettings()
        if section is None:
            self._pages[page_key] = defaults
        else:
            page = self.get(page_key)
            if not hasattr(page, section):
                raise KeyError(f"unknown section: {section}")
            setattr(page, section, getattr(defaults, section))
        self.changed.emit(page_key, self.get(page_key))
        self._save_timer.start()

    def _flush(self) -> None:
        save_yaml(self._path, self._pages)
