"""PoseEstimateTool — simulated press/move/release."""
import math
import pytest


@pytest.fixture
def view(qtbot):
    from pkrc_visualizer.widgets.pyvista_view import PyVistaView
    v = PyVistaView()
    qtbot.addWidget(v)
    return v


def test_drag_emits_pose_with_correct_xy_and_yaw(view):
    from pkrc_visualizer.widgets.pose_estimate_tool import PoseEstimateTool
    received: list[tuple[float, float, float]] = []
    tool = PoseEstimateTool(view, on_pose_picked=lambda x, y, yaw: received.append((x, y, yaw)))
    tool.attach()

    # Force a known top-down camera so screen→world picking is deterministic.
    view.force_top_down(height_m=20.0)

    # Simulate press at world (1, 0) and release at world (1, 1) → yaw = pi/2.
    tool._on_press_world(1.0, 0.0)
    tool._on_move_world(1.0, 1.0)
    tool._on_release_world(1.0, 1.0)

    assert len(received) == 1
    x, y, yaw = received[0]
    assert abs(x - 1.0) < 1e-3
    assert abs(y - 0.0) < 1e-3
    assert abs(yaw - math.pi / 2) < 1e-3


def test_short_drag_is_ignored(view):
    from pkrc_visualizer.widgets.pose_estimate_tool import PoseEstimateTool
    received: list[tuple[float, float, float]] = []
    tool = PoseEstimateTool(view, on_pose_picked=lambda x, y, yaw: received.append((x, y, yaw)),
                            min_drag_world_m=0.1)
    tool.attach()
    view.force_top_down(height_m=20.0)

    tool._on_press_world(0.0, 0.0)
    tool._on_release_world(0.001, 0.001)  # 1mm drag — below threshold
    assert received == []


def test_detach_removes_observers(view):
    from pkrc_visualizer.widgets.pose_estimate_tool import PoseEstimateTool
    tool = PoseEstimateTool(view, on_pose_picked=lambda *a: None)
    tool.attach()
    assert tool._observer_ids
    tool.detach()
    assert not tool._observer_ids


def test_observer_priority_above_default_style(view):
    """Higher priority than the default InteractorStyle (0.0) is what lets
    AbortFlagOn() actually suppress camera rotation. Regression guard."""
    from pkrc_visualizer.widgets.pose_estimate_tool import PoseEstimateTool
    assert PoseEstimateTool._OBSERVER_PRIORITY > 0.0


def test_abort_tolerates_missing_AbortFlagOn():
    """Some VTK 9.x interactor objects don't expose AbortFlagOn. Calling
    `_abort` against such an object must not raise — release publish was
    happening but every drag spammed the console with AttributeError tracebacks."""
    from pkrc_visualizer.widgets.pose_estimate_tool import PoseEstimateTool

    class _NoAbortFlagOn:
        pass

    PoseEstimateTool._abort(_NoAbortFlagOn())  # must not raise


def test_abort_calls_AbortFlagOn_when_available():
    from pkrc_visualizer.widgets.pose_estimate_tool import PoseEstimateTool

    class _Spy:
        called = False
        def AbortFlagOn(self):
            self.called = True

    spy = _Spy()
    PoseEstimateTool._abort(spy)
    assert spy.called is True
