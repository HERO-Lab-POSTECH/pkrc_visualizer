"""TopdownMapWidget: occupancy-grid → QImage conversion + state caching."""
import numpy as np
from nav_msgs.msg import OccupancyGrid

from pkrc_visualizer.pages.monitoring.topdown_map_widget import (
    TopdownMapWidget, _occupancy_grid_to_qimage)


def _make_grid(width, height, cells, resolution=0.1, ox=0.0, oy=0.0):
    msg = OccupancyGrid()
    msg.info.width = width
    msg.info.height = height
    msg.info.resolution = resolution
    msg.info.origin.position.x = ox
    msg.info.origin.position.y = oy
    msg.info.origin.orientation.w = 1.0
    msg.data = list(cells)
    return msg


def test_grid_to_qimage_unknown_is_grey():
    cells = [-1] * (3 * 3)
    img = _occupancy_grid_to_qimage(_make_grid(3, 3, cells))
    assert img.width() == 3 and img.height() == 3
    assert img.pixel(0, 0) & 0xFF == 127


def test_grid_to_qimage_free_is_white():
    cells = [0] * (3 * 3)
    img = _occupancy_grid_to_qimage(_make_grid(3, 3, cells))
    assert img.pixel(0, 0) & 0xFF == 255


def test_grid_to_qimage_occupied_is_black():
    cells = [100] * (3 * 3)
    img = _occupancy_grid_to_qimage(_make_grid(3, 3, cells))
    assert img.pixel(0, 0) & 0xFF == 0


def test_grid_to_qimage_y_flipped():
    # Bottom row (data row 0) is occupied; top row (row H-1) is free.
    cells = [100, 100, 100,    # row 0 = bottom in world
             50, 50, 50,
             0, 0, 0]           # row 2 = top in world
    img = _occupancy_grid_to_qimage(_make_grid(3, 3, cells))
    # In QImage coords (y=0 is top), pixel(0,0) should be the FREE row.
    assert img.pixel(0, 0) & 0xFF == 255
    assert img.pixel(0, 2) & 0xFF == 0


def test_set_occupancy_grid_caches_metadata(qtbot):
    w = TopdownMapWidget()
    qtbot.addWidget(w)
    msg = _make_grid(4, 5, [0] * 20, resolution=0.25, ox=-1.0, oy=-2.0)
    w.set_occupancy_grid(msg)
    canvas = w._canvas
    assert canvas._grid_size == (4, 5)
    assert canvas._grid_resolution == 0.25
    assert canvas._grid_origin_xy == (-1.0, -2.0)
    assert canvas._grid_image is not None


def test_world_to_screen_autofits_grid(qtbot):
    """With a grid loaded, the grid bounding box must fit inside the panel."""
    w = TopdownMapWidget()
    qtbot.addWidget(w)
    w.show()
    w.resize(400, 300)

    msg = _make_grid(10, 10, [0] * 100, resolution=0.5, ox=0.0, oy=0.0)
    w.set_occupancy_grid(msg)
    canvas = w._canvas

    bl = canvas._world_to_screen(0.0, 0.0)
    tr = canvas._world_to_screen(5.0, 5.0)

    assert 0 <= bl.x() <= canvas.width()
    assert 0 <= bl.y() <= canvas.height()
    assert 0 <= tr.x() <= canvas.width()
    assert 0 <= tr.y() <= canvas.height()
    assert tr.x() > bl.x()
    assert tr.y() < bl.y()


def test_world_to_screen_centers_grid_in_wide_panel(qtbot):
    w = TopdownMapWidget()
    qtbot.addWidget(w)
    w.show()
    w.resize(400, 200)
    msg = _make_grid(10, 10, [0] * 100, resolution=0.5)
    w.set_occupancy_grid(msg)
    canvas = w._canvas

    bl = canvas._world_to_screen(0.0, 0.0)
    br = canvas._world_to_screen(5.0, 0.0)
    grid_pix_width = br.x() - bl.x()
    left_margin = bl.x()
    right_margin = canvas.width() - br.x()
    assert abs(left_margin - right_margin) < 1.0
    assert grid_pix_width < canvas.width()


def test_world_to_screen_falls_back_without_grid(qtbot):
    w = TopdownMapWidget()
    qtbot.addWidget(w)
    w.show()
    w.resize(400, 400)
    canvas = w._canvas
    canvas.update_pose(0.0, 0.0, 0.0)
    centre = canvas._world_to_screen(0.0, 0.0)
    assert abs(centre.x() - canvas.width() / 2) < 1.0
    assert abs(centre.y() - canvas.height() / 2) < 1.0
