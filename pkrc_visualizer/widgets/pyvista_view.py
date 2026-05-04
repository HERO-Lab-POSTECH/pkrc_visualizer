"""pyvistaqt.QtInteractor embed.

Provides:
  - In-place cloud / marker / accumulating cloud actor updates (no flicker).
  - Bottom-left orientation widget with white XYZ labels.
  - Map-origin axes triad with a "map" billboard label (RViz-style).
  - Robot-frame axes triad with a "base_link" billboard label.
  - Auto-expanding grid sized to enclose the rendered cloud.
"""

import time

import numpy as np
import pyvista as pv
import vtk
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from pyvistaqt import QtInteractor

pv.global_theme.allow_empty_mesh = True


def _set_caption_text_color(caption_actor, rgb):
    prop = caption_actor.GetCaptionTextProperty()
    prop.SetColor(*rgb)
    prop.BoldOn()
    prop.ShadowOff()
    prop.SetFontSize(18)


def _quat_to_vtk_transform(position, quat):
    qx, qy, qz, qw = quat
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    m = vtk.vtkMatrix4x4()
    m.Identity()
    m.SetElement(0, 0, 1 - 2 * (yy + zz))
    m.SetElement(0, 1, 2 * (xy - wz))
    m.SetElement(0, 2, 2 * (xz + wy))
    m.SetElement(1, 0, 2 * (xy + wz))
    m.SetElement(1, 1, 1 - 2 * (xx + zz))
    m.SetElement(1, 2, 2 * (yz - wx))
    m.SetElement(2, 0, 2 * (xz - wy))
    m.SetElement(2, 1, 2 * (yz + wx))
    m.SetElement(2, 2, 1 - 2 * (xx + yy))
    m.SetElement(0, 3, position[0])
    m.SetElement(1, 3, position[1])
    m.SetElement(2, 3, position[2])
    t = vtk.vtkTransform()
    t.SetMatrix(m)
    return t


def _make_axes_actor(length):
    """Compact axes triad with NO XYZ caption text (label shown via billboard)."""
    a = vtk.vtkAxesActor()
    a.SetTotalLength(length, length, length)
    a.AxisLabelsOff()
    # Make the shafts thicker so they read at distance
    for prop in (a.GetXAxisShaftProperty(), a.GetYAxisShaftProperty(),
                 a.GetZAxisShaftProperty()):
        prop.SetLineWidth(3)
    return a


def _make_label(text, rgb=(1.0, 1.0, 1.0)):
    """Screen-space sized text that always faces the camera (RViz-style)."""
    actor = vtk.vtkBillboardTextActor3D()
    actor.SetInput(text)
    prop = actor.GetTextProperty()
    prop.SetFontSize(16)
    prop.SetColor(*rgb)
    prop.BoldOn()
    prop.ShadowOff()
    prop.SetJustificationToCentered()
    return actor


class PyVistaView(QWidget):
    MAX_ACCUM_POINTS = 300_000
    GRID_UPDATE_INTERVAL_S = 1.0
    ROBOT_AXES_LENGTH_M = 0.5
    ORIGIN_AXES_LENGTH_M = 1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plotter = QtInteractor(self)
        self._plotter.set_background("#1e1e1e")

        # Bottom-left orientation widget (XYZ labels in white)
        orient = vtk.vtkAxesActor()
        orient.SetXAxisLabelText("X")
        orient.SetYAxisLabelText("Y")
        orient.SetZAxisLabelText("Z")
        for cap in (orient.GetXAxisCaptionActor2D(),
                    orient.GetYAxisCaptionActor2D(),
                    orient.GetZAxisCaptionActor2D()):
            _set_caption_text_color(cap, (1.0, 1.0, 1.0))
        self._orient_widget = vtk.vtkOrientationMarkerWidget()
        self._orient_widget.SetOrientationMarker(orient)
        self._orient_widget.SetInteractor(self._plotter.interactor)
        self._orient_widget.SetViewport(0.0, 0.0, 0.18, 0.22)
        self._orient_widget.SetEnabled(1)
        self._orient_widget.InteractiveOff()

        # Map-origin axes (always at world origin) + "map" frame label
        self._origin_axes = _make_axes_actor(self.ORIGIN_AXES_LENGTH_M)
        self._plotter.add_actor(self._origin_axes)
        self._origin_label = _make_label("map", rgb=(1.0, 1.0, 0.6))
        self._origin_label.SetPosition(0.0, 0.0, 0.0)
        self._plotter.add_actor(self._origin_label)

        # Robot-frame axes (movable via update_robot_pose) + "base_link" label
        self._robot_axes = _make_axes_actor(self.ROBOT_AXES_LENGTH_M)
        self._robot_axes.SetVisibility(False)
        self._plotter.add_actor(self._robot_axes)
        self._robot_label = _make_label("base_link", rgb=(0.6, 1.0, 0.6))
        self._robot_label.SetVisibility(False)
        self._plotter.add_actor(self._robot_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plotter.interactor)

        # Persistent actors; their PolyData is swapped in place via
        # _set_actor_points to avoid actor add/remove flicker.
        self._polydata_keepalive: dict[int, pv.PolyData] = {}
        empty = pv.PolyData(np.zeros((0, 3), dtype=np.float32))

        self._cloud_actor = self._plotter.add_mesh(
            empty.copy(), color="#4fc3f7", point_size=2,
            render_points_as_spheres=False)
        self._marker_actor = self._plotter.add_mesh(
            empty.copy(), color="#ffb74d", point_size=4,
            render_points_as_spheres=True)
        self._accum_actor = self._plotter.add_mesh(
            empty.copy(), color="#4fc3f7", point_size=2,
            render_points_as_spheres=False)
        self._accum_points = np.zeros((0, 3), dtype=np.float32)

        # Cloud color config: (transformer, flat_color, color_min, color_max).
        # Read by _set_actor_points to attach the right scalar to fresh polydata.
        self._cloud_color_config = ("flat", "#4fc3f7", 0.0, 10.0)
        self._jet_lut = self._make_jet_lut()
        # Instance-level FIFO cap so apply_display_settings can shrink it at runtime.
        self.max_accum_points = self.MAX_ACCUM_POINTS

        # Persistent vtkCubeAxesActor — bounds updated in place (no flicker).
        cube_axes = vtk.vtkCubeAxesActor()
        cube_axes.SetCamera(self._plotter.camera)
        cube_axes.SetUseTextActor3D(0)
        cube_axes.SetXTitle("X (m)")
        cube_axes.SetYTitle("Y (m)")
        cube_axes.SetZTitle("Z (m)")
        cube_axes.GetTitleTextProperty(0).SetColor(0.85, 0.85, 0.85)
        cube_axes.GetTitleTextProperty(1).SetColor(0.85, 0.85, 0.85)
        cube_axes.GetTitleTextProperty(2).SetColor(0.85, 0.85, 0.85)
        cube_axes.GetLabelTextProperty(0).SetColor(0.7, 0.7, 0.7)
        cube_axes.GetLabelTextProperty(1).SetColor(0.7, 0.7, 0.7)
        cube_axes.GetLabelTextProperty(2).SetColor(0.7, 0.7, 0.7)
        for i in range(3):
            cube_axes.GetXAxesGridlinesProperty().SetColor(0.45, 0.45, 0.45)
            cube_axes.GetYAxesGridlinesProperty().SetColor(0.45, 0.45, 0.45)
            cube_axes.GetZAxesGridlinesProperty().SetColor(0.45, 0.45, 0.45)
            cube_axes.GetXAxesLinesProperty().SetColor(0.7, 0.7, 0.7)
            cube_axes.GetYAxesLinesProperty().SetColor(0.7, 0.7, 0.7)
            cube_axes.GetZAxesLinesProperty().SetColor(0.7, 0.7, 0.7)
        cube_axes.DrawXGridlinesOn()
        cube_axes.DrawYGridlinesOn()
        cube_axes.DrawZGridlinesOn()
        cube_axes.SetGridLineLocation(cube_axes.VTK_GRID_LINES_FURTHEST)
        cube_axes.SetFlyModeToOuterEdges()
        cube_axes.SetBounds(-1, 1, -1, 1, -1, 1)
        self._plotter.add_actor(cube_axes)
        self._cube_axes = cube_axes
        self._last_grid_update = 0.0
        self._cur_grid_bounds = (-1.0, 1.0, -1.0, 1.0, -1.0, 1.0)

    def _set_actor_points(self, actor, points, keepalive_dict):
        """Re-attach a new PolyData to the actor's mapper.

        Stores the polydata in `keepalive_dict` to keep it alive for the
        VTK mapper. When the cloud color transformer is "z", attaches the
        z coordinate as a scalar so the jet LUT can colour it.
        """
        polydata = pv.PolyData(points.astype(np.float32))
        transformer, _, _, _ = self._cloud_color_config
        if transformer == "z" and points.size:
            polydata["scalar"] = points[:, 2].astype(np.float32)
        actor.GetMapper().SetInputData(polydata)
        actor.GetMapper().Update()
        keepalive_dict[id(actor)] = polydata
        return polydata

    def _maybe_update_grid(self, bbox_points):
        """Resize the persistent vtkCubeAxesActor to enclose the cloud.

        Updating SetBounds() in place avoids the actor-recreation flicker.
        """
        if bbox_points.size == 0:
            return
        now = time.monotonic()
        if now - self._last_grid_update < self.GRID_UPDATE_INTERVAL_S:
            return
        mn = bbox_points.min(axis=0)
        mx = bbox_points.max(axis=0)
        margin = np.maximum((mx - mn) * 0.1, 0.5)
        new_bounds = (
            float(mn[0] - margin[0]), float(mx[0] + margin[0]),
            float(mn[1] - margin[1]), float(mx[1] + margin[1]),
            float(mn[2] - margin[2]), float(mx[2] + margin[2]),
        )
        # Only re-set if the change is meaningful (>5% of any extent), to avoid
        # constant tick-label re-layout on every minor cloud change.
        cur = self._cur_grid_bounds
        threshold = 0.05
        changed = any(
            abs(new_bounds[i] - cur[i]) > max(abs(cur[i]), 1.0) * threshold
            for i in range(6)
        )
        if not changed:
            self._last_grid_update = now
            return
        self._cube_axes.SetBounds(*new_bounds)
        self._cur_grid_bounds = new_bounds
        self._last_grid_update = now

    def update_cloud(self, points, color="#4fc3f7"):
        self._set_actor_points(self._cloud_actor, points, self._polydata_keepalive)
        self._cloud_actor.GetProperty().SetColor(*pv.Color(color).float_rgb)
        self._maybe_update_grid(points)

    def append_cloud(self, points, color="#4fc3f7"):
        if points.size == 0:
            return
        new_pts = points.astype(np.float32)
        combined = np.vstack([self._accum_points, new_pts])
        if combined.shape[0] > self.max_accum_points:
            combined = combined[-self.max_accum_points:]
        self._accum_points = combined
        self._set_actor_points(self._accum_actor, combined, self._polydata_keepalive)
        self._accum_actor.GetProperty().SetColor(*pv.Color(color).float_rgb)
        self._maybe_update_grid(combined)

    def clear_accum(self):
        self._accum_points = np.zeros((0, 3), dtype=np.float32)
        self._set_actor_points(self._accum_actor, self._accum_points,
                               self._polydata_keepalive)

    def update_markers(self, points, color="#ffb74d"):
        self._set_actor_points(self._marker_actor, points, self._polydata_keepalive)
        self._marker_actor.GetProperty().SetColor(*pv.Color(color).float_rgb)

    def update_robot_pose(self, position, quaternion):
        t = _quat_to_vtk_transform(position, quaternion)
        self._robot_axes.SetUserTransform(t)
        self._robot_axes.SetVisibility(True)
        # Place the label slightly above the axes triad
        self._robot_label.SetPosition(position[0], position[1],
                                      position[2] + self.ROBOT_AXES_LENGTH_M * 1.2)
        self._robot_label.SetVisibility(True)

    def reset_camera(self):
        self._plotter.reset_camera()

    @staticmethod
    def _hex_to_rgb01(color_hex: str) -> tuple[float, float, float]:
        h = color_hex.lstrip("#")
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    @staticmethod
    def _make_jet_lut():
        lut = vtk.vtkLookupTable()
        lut.SetHueRange(0.667, 0.0)   # blue → red
        lut.SetSaturationRange(1.0, 1.0)
        lut.SetValueRange(1.0, 1.0)
        lut.SetNumberOfTableValues(256)
        lut.Build()
        return lut

    def apply_display_settings(self, settings) -> None:
        self._plotter.set_background(settings.background)
        self._apply_frames(settings.frames)
        self._apply_cloud(settings.cloud)
        self._plotter.render()

    def _apply_frames(self, f) -> None:
        for axes, length, width in (
            (self._origin_axes, f.map_axes_length_m, f.map_axes_line_width),
            (self._robot_axes, f.robot_axes_length_m, f.robot_axes_line_width),
        ):
            axes.SetTotalLength(length, length, length)
            for shaft in (axes.GetXAxisShaftProperty(),
                          axes.GetYAxisShaftProperty(),
                          axes.GetZAxisShaftProperty()):
                shaft.SetLineWidth(width)

        self._origin_axes.SetVisibility(f.show_map_frame)
        self._origin_label.SetVisibility(f.show_map_frame)
        if not f.show_robot_frame:
            self._robot_axes.SetVisibility(False)
            self._robot_label.SetVisibility(False)

        for label, color in (
            (self._origin_label, f.map_label_color),
            (self._robot_label, f.robot_label_color),
        ):
            prop = label.GetTextProperty()
            prop.SetFontSize(f.label_font_size)
            prop.SetColor(*self._hex_to_rgb01(color))

    def _apply_cloud(self, c) -> None:
        self._cloud_color_config = (
            c.color_transformer, c.flat_color, c.color_min, c.color_max,
        )
        self.max_accum_points = c.decay_max_points
        if self._accum_points.shape[0] > self.max_accum_points:
            self._accum_points = self._accum_points[-self.max_accum_points:]
            self._set_actor_points(
                self._accum_actor, self._accum_points, self._polydata_keepalive)

        for actor in (self._cloud_actor, self._accum_actor):
            prop = actor.GetProperty()
            prop.SetPointSize(c.size)
            prop.SetOpacity(c.alpha)
            prop.SetRenderPointsAsSpheres(c.style == "spheres")
            mapper = actor.GetMapper()
            if c.color_transformer == "flat":
                prop.SetColor(*self._hex_to_rgb01(c.flat_color))
                mapper.ScalarVisibilityOff()
            else:
                mapper.ScalarVisibilityOn()
                mapper.SetScalarRange(c.color_min, c.color_max)
                mapper.SetLookupTable(self._jet_lut)
        if self._accum_points.size:
            self._set_actor_points(
                self._accum_actor, self._accum_points, self._polydata_keepalive)

    def closeEvent(self, event):
        self._plotter.close()
        super().closeEvent(event)
