"""ImageToolbar: + Add Viewer + Layout 콤보."""
from pkrc_visualizer.widgets.image_toolbar import ImageToolbar, LAYOUT_OPTIONS


def test_toolbar_layout_options(qtbot):
    bar = ImageToolbar()
    qtbot.addWidget(bar)
    items = [bar._layout_combo.itemText(i) for i in range(bar._layout_combo.count())]
    assert items == LAYOUT_OPTIONS


def test_add_viewer_signal(qtbot):
    bar = ImageToolbar()
    qtbot.addWidget(bar)
    spy = []
    bar.add_viewer_clicked.connect(lambda: spy.append(1))
    bar._add_btn.click()
    assert spy == [1]


def test_layout_changed_signal(qtbot):
    bar = ImageToolbar()
    qtbot.addWidget(bar)
    spy = []
    bar.layout_changed.connect(lambda v: spy.append(v))
    bar._layout_combo.setCurrentText("3x2")
    assert spy[-1] == "3x2"
