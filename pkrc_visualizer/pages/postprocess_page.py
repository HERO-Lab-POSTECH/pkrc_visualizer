"""Post Processing page: load and view a saved PCD file."""
from pathlib import Path

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QFileDialog, QGridLayout, QHBoxLayout, QLabel,
                             QPushButton, QSlider, QVBoxLayout, QWidget)

from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.pyvista_view import PyVistaView


class PostprocessPage(BasePage):
    # Sliders store tenths of their unit (0.1° / 0.1 m resolution).
    _SLIDER_SCALE = 10
    _YAW_MAX_DEG = 180
    _XYZ_MAX_M = 100

    def __init__(self, ros_client, display_store, parent=None):
        super().__init__(ros_client, parent)

        self._load_btn = QPushButton("Load PCD...")
        self._load_btn.clicked.connect(self._on_load_clicked)
        self._path_label = QLabel("No file loaded")

        self._transform_toggle_btn = QPushButton("Transform ▾")
        self._transform_toggle_btn.setCheckable(True)
        self._transform_toggle_btn.setChecked(False)
        self._transform_toggle_btn.toggled.connect(self._on_transform_toggled)

        bar = QHBoxLayout()
        bar.addWidget(self._load_btn)
        bar.addWidget(self._path_label, 1)
        bar.addWidget(self._transform_toggle_btn)

        # Transform panel: sliders + reset button. Hidden until the
        # toggle button in the top bar is checked.
        self._transform_panel = QWidget()
        panel_layout = QVBoxLayout(self._transform_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        self._yaw_slider, self._yaw_value_label = self._build_slider_row(
            grid, row=0, name="Yaw (Z):", limit=self._YAW_MAX_DEG, suffix="°")
        self._tx_slider, self._tx_value_label = self._build_slider_row(
            grid, row=1, name="X (m):", limit=self._XYZ_MAX_M, suffix=" m")
        self._ty_slider, self._ty_value_label = self._build_slider_row(
            grid, row=2, name="Y (m):", limit=self._XYZ_MAX_M, suffix=" m")
        self._tz_slider, self._tz_value_label = self._build_slider_row(
            grid, row=3, name="Z (m):", limit=self._XYZ_MAX_M, suffix=" m")
        panel_layout.addLayout(grid)

        self._reset_btn = QPushButton("Reset transform")
        self._reset_btn.setEnabled(False)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        reset_bar = QHBoxLayout()
        reset_bar.addStretch(1)
        reset_bar.addWidget(self._reset_btn)
        panel_layout.addLayout(reset_bar)

        self._transform_panel.setVisible(False)

        # Tuple cache used by reset / label-refresh helpers.
        self._transform_rows = (
            (self._yaw_slider, self._yaw_value_label, "°"),
            (self._tx_slider, self._tx_value_label, " m"),
            (self._ty_slider, self._ty_value_label, " m"),
            (self._tz_slider, self._tz_value_label, " m"),
        )

        self._view = PyVistaView()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self._transform_panel)
        layout.addWidget(self._view)

        self._install_settings_panel(
            self._view, page_key="postprocess",
            store=display_store, include_decay=False,
            include_xyz_focus=True)

        # Cached unrotated/untranslated points. Slider changes re-apply
        # the transform from this so accumulated float noise doesn't
        # drift the cloud over time.
        self._original_points: np.ndarray | None = None

    def _build_slider_row(self, grid, row, name, limit, suffix):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(-limit * self._SLIDER_SCALE,
                        limit * self._SLIDER_SCALE)
        slider.setValue(0)
        slider.setEnabled(False)
        slider.valueChanged.connect(self._on_transform_changed)
        value_label = QLabel(f"+0.0{suffix}")
        value_label.setMinimumWidth(70)
        grid.addWidget(QLabel(name), row, 0)
        grid.addWidget(slider, row, 1)
        grid.addWidget(value_label, row, 2)
        return slider, value_label

    def _is_my_topic(self, topic_id: str) -> bool:
        return False

    def refresh(self) -> None:
        pass

    def _on_load_clicked(self) -> None:
        data_dir = Path.home() / "Data"
        start = str(data_dir if data_dir.exists() else Path.home())
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Load PCD (Ctrl/Shift for multi-select)", start,
            "PCD files (*.pcd)")
        if not paths:
            return

        chunks = []
        loaded = []
        errors = []
        for p in paths:
            try:
                chunks.append(self._read_pcd_ascii(p))
                loaded.append(p)
            except Exception as exc:
                errors.append(f"{Path(p).name}: {exc}")

        if not chunks:
            self._path_label.setText("Error loading: " + "; ".join(errors))
            return

        self._original_points = np.concatenate(chunks, axis=0)
        for slider, _, _ in self._transform_rows:
            slider.setEnabled(True)
        self._reset_btn.setEnabled(True)

        # Reset sliders silently, refresh labels + redraw once below.
        for slider, _, _ in self._transform_rows:
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        self._refresh_value_labels()
        self._render_with_current_transform()
        self._view.reset_camera()

        n_pts = self._original_points.shape[0]
        if len(loaded) == 1 and not errors:
            label = loaded[0]
        else:
            label = f"{len(loaded)} files ({n_pts:,} pts): " + ", ".join(
                Path(p).name for p in loaded)
        if errors:
            label += "  |  errors: " + "; ".join(errors)
        self._path_label.setText(label)

    def _on_transform_changed(self, _value: int = 0) -> None:
        self._refresh_value_labels()
        self._render_with_current_transform()

    def _on_transform_toggled(self, checked: bool) -> None:
        self._transform_panel.setVisible(checked)
        self._transform_toggle_btn.setText(
            "Transform ▴" if checked else "Transform ▾")

    def _on_reset_clicked(self) -> None:
        for slider, _, _ in self._transform_rows:
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        self._refresh_value_labels()
        self._render_with_current_transform()

    def _refresh_value_labels(self) -> None:
        for slider, value_label, suffix in self._transform_rows:
            value = slider.value() / self._SLIDER_SCALE
            value_label.setText(f"{value:+.1f}{suffix}")

    def _current_transform_values(self) -> tuple[float, float, float, float]:
        return (
            self._yaw_slider.value() / self._SLIDER_SCALE,
            self._tx_slider.value() / self._SLIDER_SCALE,
            self._ty_slider.value() / self._SLIDER_SCALE,
            self._tz_slider.value() / self._SLIDER_SCALE,
        )

    def _render_with_current_transform(self) -> None:
        if self._original_points is None:
            return
        yaw_deg, tx, ty, tz = self._current_transform_values()
        transformed = self._apply_transform(
            self._original_points, yaw_deg, tx, ty, tz)
        self._view.update_cloud(transformed, color="#81c784")

    @staticmethod
    def _apply_transform(
        points: np.ndarray,
        yaw_deg: float,
        tx: float, ty: float, tz: float,
    ) -> np.ndarray:
        """Rotate Nx3 points around world Z by yaw_deg, then translate by (tx,ty,tz).

        Order is rotate-then-translate: out = points @ R.T + t. The
        rotation pivot is the world origin, so the SLAM start pose stays
        the anchor of the coordinate system.
        """
        if yaw_deg == 0.0 and tx == 0.0 and ty == 0.0 and tz == 0.0:
            return points
        if yaw_deg == 0.0:
            rotated = points
        else:
            rad = np.deg2rad(yaw_deg, dtype=np.float32)
            c = np.cos(rad)
            s = np.sin(rad)
            rotation = np.array(
                [[c, -s, 0.0],
                 [s,  c, 0.0],
                 [0.0, 0.0, 1.0]],
                dtype=np.float32,
            )
            rotated = points @ rotation.T
        translation = np.array([tx, ty, tz], dtype=np.float32)
        return rotated + translation

    @staticmethod
    def _read_pcd_ascii(path: str) -> np.ndarray:
        """Minimal PCD v0.7 ASCII reader: skip header until DATA line."""
        with open(path) as f:
            for line in f:
                if line.strip().lower().startswith("data ascii"):
                    break
            else:
                raise ValueError("No 'DATA ascii' marker — not an ASCII PCD")
            arr = np.loadtxt(f, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr[:, :3]
