"""Declarative schema for SettingsPanel.

Each FieldSpec describes a single form widget. Path uses dotted notation
matching DisplaySettingsStore.update (e.g. "cloud.size", "background").
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldSpec:
    path: str            # e.g. "frames.map_axes_length_m" or "background"
    label: str
    widget: str          # slider | spinbox_int | spinbox_float | color | combobox | checkbox
    options: dict = field(default_factory=dict)


def frames_schema() -> list[FieldSpec]:
    return [
        FieldSpec("frames.show_map_frame", "Show map frame", "checkbox"),
        FieldSpec("frames.map_axes_length_m", "Map axes length (m)", "slider",
                  {"min": 0.1, "max": 5.0, "step": 0.1}),
        FieldSpec("frames.map_axes_line_width", "Map axes line width (px)", "spinbox_int",
                  {"min": 1, "max": 10}),
        FieldSpec("frames.map_label_color", "Map label color", "color"),
        FieldSpec("frames.show_robot_frame", "Show robot frame", "checkbox"),
        FieldSpec("frames.robot_axes_length_m", "Robot axes length (m)", "slider",
                  {"min": 0.1, "max": 3.0, "step": 0.1}),
        FieldSpec("frames.robot_axes_line_width", "Robot axes line width (px)", "spinbox_int",
                  {"min": 1, "max": 10}),
        FieldSpec("frames.robot_label_color", "Robot label color", "color"),
        FieldSpec("frames.label_font_size", "Label font size (pt)", "spinbox_int",
                  {"min": 8, "max": 32}),
    ]


def cloud_schema(include_decay: bool) -> list[FieldSpec]:
    fields_: list[FieldSpec] = [
        FieldSpec("cloud.style", "Style", "combobox",
                  {"choices": ["points", "square", "spheres"]}),
        FieldSpec("cloud.size", "Size (px or m)", "slider",
                  {"min": 0.01, "max": 20.0, "step": 0.1}),
        FieldSpec("cloud.size_unit", "Size unit", "combobox",
                  {"choices": ["pixels", "meters"]}),
        FieldSpec("cloud.alpha", "Alpha", "slider",
                  {"min": 0.0, "max": 1.0, "step": 0.05}),
    ]
    if include_decay:
        fields_.append(FieldSpec("cloud.decay_seconds",
                                 "Decay time (s, 0 = off)", "spinbox_float",
                                 {"min": 0.0, "max": 600.0, "step": 1.0}))
    fields_.extend([
        FieldSpec("cloud.color_transformer", "Color transformer", "combobox",
                  {"choices": ["flat", "z", "intensity"]}),
        FieldSpec("cloud.flat_color", "Flat color", "color"),
        FieldSpec("cloud.color_min", "Color min", "spinbox_float",
                  {"min": -1000.0, "max": 1000.0, "step": 0.1}),
        FieldSpec("cloud.color_max", "Color max", "spinbox_float",
                  {"min": -1000.0, "max": 1000.0, "step": 0.1}),
    ])
    return fields_


def prior_map_schema() -> list[FieldSpec]:
    return [
        FieldSpec("prior_map.show", "Show on ground plane", "checkbox"),
        FieldSpec("prior_map.alpha", "Alpha", "slider",
                  {"min": 0.0, "max": 1.0, "step": 0.05}),
    ]


def background_schema() -> list[FieldSpec]:
    return [
        FieldSpec("background", "Background color", "color"),
    ]


def panel_tabs(include_decay: bool, include_prior_map: bool = False
               ) -> list[tuple[str, str, list[FieldSpec]]]:
    """Return (tab_id, tab_label, fields) triples in display order."""
    tabs = [
        ("frames", "Frames", frames_schema()),
        ("cloud", "Cloud", cloud_schema(include_decay)),
    ]
    if include_prior_map:
        tabs.append(("prior_map", "Prior Map", prior_map_schema()))
    tabs.append(("background", "Background", background_schema()))
    return tabs
