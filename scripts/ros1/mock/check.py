#!/usr/bin/env python3
"""Checks against the mock TIAGo, for scripts/ros1/mock_test.sh (read-only).

    check.py owner tp|pal          who drives the joints (exit 1 if not as expected)
    check.py at MOTION             the arm is at /play_motion/motions/MOTION (max error 0.01 rad)
    check.py ee-save FILE          save the hand pose (gripper_grasping_frame in torso_lift_link)
    check.py ee-moved FILE DX DY DZ [--expect-jump]
                                   how the hand moved since ee-save, for a headset offset (DX, DY, DZ),
                                   next to what arm_tp_controller's maths predicts (R0 R0 d)
"""
import json
import math
import sys

import rospy
import tf2_ros
from controller_manager_msgs.srv import ListControllers
from sensor_msgs.msg import JointState

TP = ["arm_tp_controller", "head_tp_controller", "torso_tp_controller", "gripper_tp_controller"]
AXES = ("forward", "left", "up")


def controllers():
    rospy.wait_for_service("/controller_manager/list_controllers", timeout=10)
    return {c.name: c.state for c in rospy.ServiceProxy("/controller_manager/list_controllers", ListControllers)().controller}


def rot(q):
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def mul(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def ee():
    buf = tf2_ros.Buffer()
    tf2_ros.TransformListener(buf)
    t = buf.lookup_transform("torso_lift_link", "gripper_grasping_frame", rospy.Time(0), rospy.Duration(5)).transform
    return [t.translation.x, t.translation.y, t.translation.z], [t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w]


def fmt(v):
    return " ".join("%+5.1f cm %s" % (100 * c, AXES[i]) for i, c in enumerate(v))


def main():
    rospy.init_node("mock_check", anonymous=True)
    cmd = sys.argv[1]
    if cmd == "owner":
        cs = controllers()
        want = sys.argv[2]
        tp_on = all(cs.get(c) == "running" for c in TP)
        pal_on = all(cs.get(c.replace("_tp_", "_")) == "running" for c in TP)
        good = tp_on and not pal_on if want == "tp" else pal_on and not tp_on
        print("  %s  joints owned by %s: %s" % ("ok  " if good else "FAIL", want, ", ".join("%s=%s" % kv for kv in sorted(cs.items()))))
        return 0 if good else 1
    if cmd == "at":
        m = rospy.get_param("/play_motion/motions/%s" % sys.argv[2])
        js = rospy.wait_for_message("/joint_states", JointState, timeout=5)
        pos = dict(zip(js.name, js.position))
        err = max(abs(pos[j] - p) for j, p in zip(m["joints"], m["points"][-1]["positions"]))
        print("  %s  arm at '%s' (max error %.3f rad)" % ("ok  " if err < 0.01 else "FAIL", sys.argv[2], err))
        return 0 if err < 0.01 else 1
    if cmd == "ee-save":
        p, q = ee()
        json.dump({"p": p, "q": q}, open(sys.argv[2], "w"))
        return 0
    if cmd == "ee-moved":
        s = json.load(open(sys.argv[2]))
        d = [float(v) for v in sys.argv[3:6]]
        p, _ = ee()
        moved = [a - b for a, b in zip(p, s["p"])]
        r0 = rot(s["q"])
        predicted = mul(r0, mul(r0, d))
        err = math.dist(moved, predicted)
        print("      headset offset %s" % fmt(d))
        print("      hand moved     %s" % fmt(moved))
        print("      maths predicts %s" % fmt(predicted))
        if "--expect-jump" in sys.argv:
            return 0
        print("  %s  hand moved as arm_tp_controller's maths predicts (off by %.1f cm)" % ("ok  " if err < 0.01 else "FAIL", 100 * err))
        return 0 if err < 0.01 else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
