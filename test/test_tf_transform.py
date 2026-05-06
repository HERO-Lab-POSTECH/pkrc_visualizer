"""Pure-numpy 4x4 transform builder tests."""
import math

import numpy as np
import pytest


def test_identity_translation_and_no_rotation():
    from pkrc_visualizer.tf_transform import transform_to_matrix
    m = transform_to_matrix(
        translation=(0.0, 0.0, 0.0),
        quaternion=(0.0, 0.0, 0.0, 1.0),
    )
    assert m.shape == (4, 4)
    assert np.allclose(m, np.eye(4))


def test_pure_translation():
    from pkrc_visualizer.tf_transform import transform_to_matrix
    m = transform_to_matrix(
        translation=(1.0, 2.0, 3.0),
        quaternion=(0.0, 0.0, 0.0, 1.0),
    )
    assert np.allclose(m[:3, 3], [1.0, 2.0, 3.0])
    assert np.allclose(m[:3, :3], np.eye(3))


def test_yaw_90_rotates_x_to_y():
    """Quaternion (0,0,sin(45°),cos(45°)) is yaw=90°. Applied to (1,0,0) gives (0,1,0)."""
    from pkrc_visualizer.tf_transform import transform_to_matrix, apply_to_points
    half = math.pi / 4
    m = transform_to_matrix(
        translation=(0.0, 0.0, 0.0),
        quaternion=(0.0, 0.0, math.sin(half), math.cos(half)),
    )
    pts = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    out = apply_to_points(m, pts)
    assert out.shape == (1, 3)
    assert np.allclose(out[0], [0.0, 1.0, 0.0], atol=1e-6)


def test_apply_to_points_handles_empty_array():
    from pkrc_visualizer.tf_transform import apply_to_points
    m = np.eye(4)
    out = apply_to_points(m, np.zeros((0, 3), dtype=np.float32))
    assert out.shape == (0, 3)
    assert out.dtype == np.float32


def test_apply_to_pose_translates_and_rotates_quaternion():
    """A 90° yaw transform applied to pose at (1,0,0) with identity orientation
    should land at (0,1,0) with orientation = source TF's quaternion."""
    from pkrc_visualizer.tf_transform import transform_to_matrix, apply_to_pose
    half = math.pi / 4
    m = transform_to_matrix(
        translation=(0.0, 0.0, 0.0),
        quaternion=(0.0, 0.0, math.sin(half), math.cos(half)),
    )
    new_pos, new_quat = apply_to_pose(
        m, position=(1.0, 0.0, 0.0), quaternion=(0.0, 0.0, 0.0, 1.0))
    assert np.allclose(new_pos, [0.0, 1.0, 0.0], atol=1e-6)
    # 0 yaw composed with 90° yaw → 90° yaw
    assert abs(new_quat[2] - math.sin(half)) < 1e-6
    assert abs(new_quat[3] - math.cos(half)) < 1e-6
