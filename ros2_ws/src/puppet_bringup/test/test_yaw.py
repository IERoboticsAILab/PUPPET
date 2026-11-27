"""The ROS 2 pose-to-odom maths must match the ROS 1 scripts (tf.transformations)."""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

try:
    import rclpy  # noqa: F401
except ImportError:  # run the maths tests without ROS too (e.g. on a laptop)
    import types
    for mod in ("rclpy", "rclpy.node", "geometry_msgs", "geometry_msgs.msg", "nav_msgs", "nav_msgs.msg"):
        sys.modules[mod] = types.ModuleType(mod)
    sys.modules["rclpy.node"].Node = object
    sys.modules["geometry_msgs.msg"].PoseStamped = object
    sys.modules["nav_msgs.msg"].Odometry = object
from mocap_pose_to_odom import YawFilter, yaw_from_quaternion  # noqa: E402


def quat_from_rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = (math.cos(r / 2), math.sin(r / 2), math.cos(p / 2), math.sin(p / 2),
                              math.cos(y / 2), math.sin(y / 2))
    return (sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy)


def test_yaw_extraction():
    for yaw in (-3.0, -1.0, 0.0, 0.5, 2.9):
        for r, p in ((0, 0), (0.05, -0.03)):
            assert abs(yaw_from_quaternion(*quat_from_rpy(r, p, yaw)) - yaw) < 1e-9


def test_first_sample_sets_reference():
    f = YawFilter()
    assert f.update(1.0) is None
    assert abs(f.update(1.0)) < 1e-12


def test_wraps_across_pi():
    f = YawFilter()
    f.update(3.1)
    out = f.update(-3.1)  # 0.083 rad further, across the +-pi seam
    assert -0.1 < out < 0.1
