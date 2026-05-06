"""2D Pose Estimate tool: click+drag on z=0 plane → (x, y, yaw) callback.

Attaches to PyVistaView's VTK interactor. Picking uses a ray from the
mouse cursor intersected with z=0 plane in world coordinates. A
temporary line actor is drawn during drag for visual feedback.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

import vtk


class PoseEstimateTool:
    def __init__(
        self,
        view,
        on_pose_picked: Callable[[float, float, float], None],
        min_drag_world_m: float = 0.05,
    ) -> None:
        self._view = view
        self._plotter = view._plotter
        self._on_pose_picked = on_pose_picked
        self._min_drag = min_drag_world_m

        self._start: Optional[tuple[float, float]] = None
        self._observer_ids: list[int] = []
        self._arrow_actor: Optional[vtk.vtkActor] = None
        # Saved while attached so detach() can put the user back where they
        # were. Without this, the default trackball style would race our
        # observers for LeftButtonRelease and steal it for `EndRotate`.
        self._saved_style = None

    # Higher than the default InteractorStyle (priority 0.0) so our callbacks
    # fire FIRST and can AbortFlagOn() to suppress camera rotation on drag.
    _OBSERVER_PRIORITY = 10.0

    def attach(self) -> None:
        if self._observer_ids:
            return
        iren = self._plotter.interactor
        # Swap the default trackball style for an empty one so it never grabs
        # mouse buttons (avoids LeftButtonRelease being consumed by EndRotate
        # before our observer fires).
        self._saved_style = iren.GetInteractorStyle()
        iren.SetInteractorStyle(vtk.vtkInteractorStyleUser())
        self._observer_ids.append(iren.AddObserver(
            "LeftButtonPressEvent", self._on_left_press, self._OBSERVER_PRIORITY))
        self._observer_ids.append(iren.AddObserver(
            "MouseMoveEvent", self._on_mouse_move, self._OBSERVER_PRIORITY))
        self._observer_ids.append(iren.AddObserver(
            "LeftButtonReleaseEvent", self._on_left_release, self._OBSERVER_PRIORITY))

    def detach(self) -> None:
        iren = self._plotter.interactor
        for oid in self._observer_ids:
            iren.RemoveObserver(oid)
        self._observer_ids.clear()
        if self._saved_style is not None:
            iren.SetInteractorStyle(self._saved_style)
            self._saved_style = None
        self._remove_arrow()
        self._start = None

    # ---- screen-to-world picking ---------------------------------------------------

    def _pick_z0(self, screen_x: int, screen_y: int) -> Optional[tuple[float, float]]:
        renderer = self._plotter.renderer
        coord = vtk.vtkCoordinate()
        coord.SetCoordinateSystemToDisplay()
        coord.SetValue(screen_x, screen_y, 0.0)
        near = coord.GetComputedWorldValue(renderer)
        coord.SetValue(screen_x, screen_y, 1.0)
        far = coord.GetComputedWorldValue(renderer)
        nx, ny, nz = near
        fx, fy, fz = far
        dz = fz - nz
        if abs(dz) < 1e-9:
            return None
        t = (-nz) / dz  # solve nz + t*dz = 0
        x = nx + t * (fx - nx)
        y = ny + t * (fy - ny)
        return (x, y)

    # ---- VTK observer callbacks ----------------------------------------------------

    def _on_left_press(self, obj, event) -> None:
        sx, sy = self._plotter.interactor.GetEventPosition()
        world = self._pick_z0(sx, sy)
        if world is None:
            return
        self._on_press_world(world[0], world[1])
        obj.AbortFlagOn()  # block camera rotation start

    def _on_mouse_move(self, obj, event) -> None:
        if self._start is None:
            return
        sx, sy = self._plotter.interactor.GetEventPosition()
        world = self._pick_z0(sx, sy)
        if world is None:
            return
        self._on_move_world(world[0], world[1])
        obj.AbortFlagOn()  # block camera rotation while dragging

    def _on_left_release(self, obj, event) -> None:
        if self._start is None:
            return
        sx, sy = self._plotter.interactor.GetEventPosition()
        world = self._pick_z0(sx, sy)
        if world is None:
            return
        self._on_release_world(world[0], world[1])
        obj.AbortFlagOn()  # block camera rotation end

    # ---- world-coordinate handlers (also unit-test entry points) -------------------

    def _on_press_world(self, x: float, y: float) -> None:
        self._start = (x, y)
        self._update_arrow(x, y, x, y)

    def _on_move_world(self, x: float, y: float) -> None:
        if self._start is None:
            return
        self._update_arrow(self._start[0], self._start[1], x, y)

    def _on_release_world(self, x: float, y: float) -> None:
        if self._start is None:
            return
        sx, sy = self._start
        self._start = None
        self._remove_arrow()
        dx = x - sx
        dy = y - sy
        if math.hypot(dx, dy) < self._min_drag:
            return
        yaw = math.atan2(dy, dx)
        self._on_pose_picked(sx, sy, yaw)

    # ---- arrow actor ---------------------------------------------------------------

    def _update_arrow(self, x0: float, y0: float, x1: float, y1: float) -> None:
        line = vtk.vtkLineSource()
        line.SetPoint1(x0, y0, 0.02)
        line.SetPoint2(x1, y1, 0.02)
        line.Update()
        if self._arrow_actor is None:
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(line.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(0.2, 0.9, 0.2)
            actor.GetProperty().SetLineWidth(3.0)
            self._plotter.add_actor(actor)
            self._arrow_actor = actor
        else:
            self._arrow_actor.GetMapper().SetInputConnection(line.GetOutputPort())
        self._plotter.render()

    def _remove_arrow(self) -> None:
        if self._arrow_actor is not None:
            self._plotter.remove_actor(self._arrow_actor)
            self._arrow_actor = None
            self._plotter.render()
