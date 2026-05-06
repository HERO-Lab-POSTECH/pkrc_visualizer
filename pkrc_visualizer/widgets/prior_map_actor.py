"""OccupancyGrid -> vtkImageActor texture wrapper.

Pure-data helper `occupancy_to_rgba` is testable headless.
The VTK actor wrapper (`PriorMapActor`) requires a live render context.
"""
from __future__ import annotations

import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk
from nav_msgs.msg import OccupancyGrid


PLANE_Z = -0.01  # slight negative offset to avoid z-fighting with cloud at z=0


def occupancy_to_rgba(msg: OccupancyGrid, alpha: float) -> np.ndarray:
    """Convert OccupancyGrid (-1 unknown, 0..100 prob) to RGBA uint8 (H, W, 4).

    Mapping: occupied(100)→black, free(0)→white, intermediate → grayscale,
    unknown(-1)→fully transparent. `alpha` (0..1) scales known cells only.
    """
    width = msg.info.width
    height = msg.info.height
    data = np.array(msg.data, dtype=np.int16).reshape(height, width)

    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    known_mask = data >= 0
    # value 0 -> 255 (white free), value 100 -> 0 (black occupied)
    intensity = np.where(known_mask, 255 - (data * 255 // 100), 0).astype(np.uint8)
    rgba[..., 0] = intensity
    rgba[..., 1] = intensity
    rgba[..., 2] = intensity
    a = int(max(0.0, min(1.0, alpha)) * 255)
    rgba[..., 3] = np.where(known_mask, a, 0).astype(np.uint8)
    return rgba


class PriorMapActor:
    """Wraps a vtkImageActor whose texture is updated from OccupancyGrid messages."""

    def __init__(self, plotter):
        self._plotter = plotter
        self._actor: vtk.vtkImageActor | None = None
        self._alpha: float = 0.7
        self._last_msg: OccupancyGrid | None = None
        self._frame_warned: bool = False

    def set_grid(self, msg: OccupancyGrid) -> None:
        if msg.header.frame_id and msg.header.frame_id != "map" and not self._frame_warned:
            print(f"[prior_map] warning: frame_id '{msg.header.frame_id}' != 'map'; "
                  "rendering anyway in map frame")
            self._frame_warned = True
        self._last_msg = msg
        rgba = occupancy_to_rgba(msg, self._alpha)
        h, w, _ = rgba.shape

        image = vtk.vtkImageData()
        image.SetDimensions(w, h, 1)
        image.SetOrigin(msg.info.origin.position.x,
                        msg.info.origin.position.y,
                        PLANE_Z)
        image.SetSpacing(msg.info.resolution, msg.info.resolution, 1.0)
        flat = rgba.reshape(-1, 4)
        vtk_arr = numpy_to_vtk(flat, deep=True, array_type=vtk.VTK_UNSIGNED_CHAR)
        vtk_arr.SetNumberOfComponents(4)
        image.GetPointData().SetScalars(vtk_arr)

        if self._actor is None:
            self._actor = vtk.vtkImageActor()
            self._actor.GetProperty().SetInterpolationTypeToNearest()
            self._actor.SetInputData(image)
            self._plotter.add_actor(self._actor)
        else:
            self._actor.SetInputData(image)

    def clear(self) -> None:
        if self._actor is not None:
            self._plotter.remove_actor(self._actor)
            self._actor = None

    def set_alpha(self, alpha: float) -> None:
        self._alpha = alpha
        if self._last_msg is not None and self._actor is not None:
            self.set_grid(self._last_msg)

    def restore_if_cleared(self) -> None:
        """Re-create actor from the last seen message.

        Lets `show=False -> show=True` toggling rebuild the plane without
        needing a fresh OccupancyGrid (transient_local publishes only once)."""
        if self._actor is None and self._last_msg is not None:
            self.set_grid(self._last_msg)

    @property
    def has_actor(self) -> bool:
        return self._actor is not None
