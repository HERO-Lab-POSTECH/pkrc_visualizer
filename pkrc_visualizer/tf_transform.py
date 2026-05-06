"""Pure-numpy 4x4 homogeneous transforms from ROS quaternion+translation tuples.

Used by RosClient to expose `map ← odom` lookups as cheap matrices that pages
can apply to point clouds and poses without pulling in tf_transformations.
"""
from __future__ import annotations

import math
from typing import Tuple

import numpy as np


def transform_to_matrix(
    translation: Tuple[float, float, float],
    quaternion: Tuple[float, float, float, float],
) -> np.ndarray:
    """Build a 4×4 homogeneous transform from (x, y, z) and (qx, qy, qz, qw).

    No ROS imports — caller extracts the components from `TransformStamped.transform`.
    """
    qx, qy, qz, qw = quaternion
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    m = np.eye(4, dtype=np.float64)
    m[0, 0] = 1.0 - 2.0 * (yy + zz)
    m[0, 1] = 2.0 * (xy - wz)
    m[0, 2] = 2.0 * (xz + wy)
    m[1, 0] = 2.0 * (xy + wz)
    m[1, 1] = 1.0 - 2.0 * (xx + zz)
    m[1, 2] = 2.0 * (yz - wx)
    m[2, 0] = 2.0 * (xz - wy)
    m[2, 1] = 2.0 * (yz + wx)
    m[2, 2] = 1.0 - 2.0 * (xx + yy)
    m[0, 3] = translation[0]
    m[1, 3] = translation[1]
    m[2, 3] = translation[2]
    return m


def apply_to_points(matrix: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Apply a 4×4 transform to an (N, 3) point cloud, returning (N, 3) float32.

    Empty input is preserved as an empty (0, 3) float32 array.
    """
    if points.size == 0:
        return np.zeros((0, 3), dtype=np.float32)
    n = points.shape[0]
    homog = np.empty((n, 4), dtype=np.float64)
    homog[:, :3] = points
    homog[:, 3] = 1.0
    out = (matrix @ homog.T).T[:, :3]
    return out.astype(np.float32)


def apply_to_pose(
    matrix: np.ndarray,
    position: Tuple[float, float, float],
    quaternion: Tuple[float, float, float, float],
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float, float]]:
    """Transform a (position, quaternion) pose by `matrix`.

    Returns ((x, y, z), (qx, qy, qz, qw)).
    """
    p_h = np.array([position[0], position[1], position[2], 1.0], dtype=np.float64)
    new_p = matrix @ p_h
    new_pos = (float(new_p[0]), float(new_p[1]), float(new_p[2]))

    # Compose quaternions: q_out = q_matrix * q_in
    qm = _matrix_to_quaternion(matrix)
    new_quat = _quat_mul(qm, quaternion)
    return new_pos, new_quat


def _matrix_to_quaternion(m: np.ndarray) -> Tuple[float, float, float, float]:
    """Extract (qx, qy, qz, qw) from the rotation block of a 4×4 transform."""
    r = m[:3, :3]
    trace = r[0, 0] + r[1, 1] + r[2, 2]
    if trace > 0.0:
        s = 0.5 / math.sqrt(trace + 1.0)
        qw = 0.25 / s
        qx = (r[2, 1] - r[1, 2]) * s
        qy = (r[0, 2] - r[2, 0]) * s
        qz = (r[1, 0] - r[0, 1]) * s
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = 2.0 * math.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2])
        qw = (r[2, 1] - r[1, 2]) / s
        qx = 0.25 * s
        qy = (r[0, 1] + r[1, 0]) / s
        qz = (r[0, 2] + r[2, 0]) / s
    elif r[1, 1] > r[2, 2]:
        s = 2.0 * math.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2])
        qw = (r[0, 2] - r[2, 0]) / s
        qx = (r[0, 1] + r[1, 0]) / s
        qy = 0.25 * s
        qz = (r[1, 2] + r[2, 1]) / s
    else:
        s = 2.0 * math.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1])
        qw = (r[1, 0] - r[0, 1]) / s
        qx = (r[0, 2] + r[2, 0]) / s
        qy = (r[1, 2] + r[2, 1]) / s
        qz = 0.25 * s
    return (qx, qy, qz, qw)


def _quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )
