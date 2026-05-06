"""OccupancyGrid → RGBA texture conversion."""
import numpy as np
from nav_msgs.msg import OccupancyGrid

from pkrc_visualizer.widgets.prior_map_actor import occupancy_to_rgba


def _make_grid(width=4, height=3, cells=None):
    g = OccupancyGrid()
    g.info.resolution = 0.5
    g.info.width = width
    g.info.height = height
    g.info.origin.position.x = -1.0
    g.info.origin.position.y = -2.0
    if cells is None:
        cells = [0] * (width * height)
    g.data = list(cells)
    return g


def test_occupancy_to_rgba_shape_matches_grid():
    g = _make_grid(4, 3)
    rgba = occupancy_to_rgba(g, alpha=1.0)
    assert rgba.shape == (3, 4, 4)  # H, W, RGBA
    assert rgba.dtype == np.uint8


def test_occupied_cell_is_black():
    g = _make_grid(2, 1, cells=[100, 0])
    rgba = occupancy_to_rgba(g, alpha=1.0)
    assert tuple(rgba[0, 0]) == (0, 0, 0, 255)
    assert tuple(rgba[0, 1]) == (255, 255, 255, 255)


def test_unknown_cell_is_transparent():
    g = _make_grid(1, 1, cells=[-1])
    rgba = occupancy_to_rgba(g, alpha=1.0)
    assert rgba[0, 0, 3] == 0


def test_alpha_is_applied_to_known_cells_only():
    g = _make_grid(3, 1, cells=[0, 100, -1])
    rgba = occupancy_to_rgba(g, alpha=0.5)
    assert rgba[0, 0, 3] == 127      # free, alpha 0.5
    assert rgba[0, 1, 3] == 127      # occupied, alpha 0.5
    assert rgba[0, 2, 3] == 0        # unknown stays fully transparent


def test_intermediate_value_is_grayscale():
    g = _make_grid(1, 1, cells=[50])
    rgba = occupancy_to_rgba(g, alpha=1.0)
    # value=50 → 50% from white(255) to black(0) = ~127
    r = rgba[0, 0, 0]
    assert 120 <= r <= 135
    assert rgba[0, 0, 0] == rgba[0, 0, 1] == rgba[0, 0, 2]
