"""ImageToolbar (v0.5.0) exposes only the Add Viewer button."""
from pkrc_visualizer.widgets.image_toolbar import ImageToolbar


def test_toolbar_has_add_button(qtbot):
    bar = ImageToolbar()
    qtbot.addWidget(bar)
    assert bar._add_btn.text().endswith("Add Viewer")


def test_toolbar_emits_add_viewer_clicked(qtbot):
    bar = ImageToolbar()
    qtbot.addWidget(bar)
    received = []
    bar.add_viewer_clicked.connect(lambda: received.append(True))
    bar._add_btn.click()
    assert received == [True]


def test_toolbar_no_layout_combobox(qtbot):
    # v0.5.0 removed the layout selector; ensure it's gone.
    bar = ImageToolbar()
    qtbot.addWidget(bar)
    assert not hasattr(bar, "_layout_combo")
    assert not hasattr(bar, "layout_changed")
    assert not hasattr(bar, "set_layout_value")
