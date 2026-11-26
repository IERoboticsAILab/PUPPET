#!/usr/bin/env python3
"""Checks for the mock-robot session test (scripts/ros2/mock_test.sh).

    check.py owner tp|pal [TIMEOUT]   wait until the joints belong to our tp controllers / PAL's
    check.py snapshot FILE            save /joint_states positions as JSON
    check.py moved BEFORE AFTER       assert the drive test moved each group the right way
    check.py at-motion NAME           assert the arm is at the motion's final pose (PUPPET's or PAL's)
    check.py ee-snapshot FILE         save the hand position (torso_lift_link -> gripper_grasping_frame)
    check.py ee-moved BEFORE AFTER DX DY DZ   assert the hand moved by (DX, DY, DZ) m, +-3 mm
"""

import json
import sys
import time

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from controller_manager_msgs.srv import ListControllers
from rclpy.node import Node
from sensor_msgs.msg import JointState

TP = ["arm_tp_controller", "head_tp_controller", "torso_tp_controller", "gripper_tp_controller"]
PAL = ["arm_controller", "head_controller", "torso_controller", "gripper_controller"]


def ok(msg):
    print(f"  ok    {msg}")


def fail(msg):
    print(f"  FAIL  {msg}")
    sys.exit(1)


def controllers(node):
    cli = node.create_client(ListControllers, "/controller_manager/list_controllers")
    if not cli.wait_for_service(timeout_sec=10):
        fail("no controller_manager")
    fut = cli.call_async(ListControllers.Request())
    rclpy.spin_until_future_complete(node, fut, timeout_sec=10)
    return {c.name: c.state for c in fut.result().controller}


def owner(node, who, timeout):
    want_active, want_inactive = (TP, PAL) if who == "tp" else (PAL, TP)
    end = time.monotonic() + timeout
    while True:
        cs = controllers(node)
        if all(cs.get(n) == "active" for n in want_active) and all(cs.get(n) != "active" for n in want_inactive):
            ok(f"joints owned by {who}: " + ", ".join(f"{n}={cs.get(n)}" for n in TP + PAL))
            return
        if time.monotonic() > end:
            fail(f"after {timeout}s still: " + ", ".join(f"{n}={cs.get(n, 'missing')}" for n in TP + PAL))
        time.sleep(0.5)


def joint_positions(node):
    got = {}
    node.create_subscription(JointState, "/joint_states", lambda m: got.update(dict(zip(m.name, m.position))), 10)
    end = time.monotonic() + 10
    while not got and time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.2)
    if not got:
        fail("no /joint_states")
    return got


def moved(before, after):
    d = {k: after[k] - before[k] for k in before}
    checks = [
        ("torso up (Int32 +1)", d["torso_lift_joint"] > 0.01),
        ("gripper closing (Int32 -1)", d["gripper_left_finger_joint"] < -0.005 and d["gripper_right_finger_joint"] < -0.005),
        ("head turns (QuaternionStamped)", max(abs(d["head_1_joint"]), abs(d["head_2_joint"])) > 0.05),
        ("arm follows the hand pose (PoseStamped)", max(abs(d[f"arm_{i}_joint"]) for i in range(1, 8)) > 0.01),
    ]
    for what, good in checks:
        (ok if good else fail)(f"{what}: " + ", ".join(f"{k}={v:+.3f}" for k, v in d.items() if abs(v) > 1e-4))


PAL_GENERAL = "/opt/pal/alum/share/tiago_bringup/config/motions/tiago_motions_general.yaml"


def at_motion(node, name):
    """The arm is at the last point of `name`, from PUPPET's motions or PAL's general motions."""
    m = None
    for path in (get_package_share_directory("tiago_telepresence_controllers") + "/config/telepresence_motions.yaml", PAL_GENERAL):
        motions = next(iter(yaml.safe_load(open(path)).values()))["ros__parameters"]["motions"]
        m = m or motions.get(name)
    if m is None:
        fail(f"motion {name} not defined")
    target = dict(zip(m["joints"], m["positions"][-len(m["joints"]):]))
    q = joint_positions(node)
    err = max(abs(q[j] - v) for j, v in target.items())
    (ok if err < 0.02 else fail)(f"arm at '{name}' (max error {err:.3f} rad)")


def ee_position(node):
    from tf2_ros import Buffer, TransformListener
    buf = Buffer()
    TransformListener(buf, node)
    end = time.monotonic() + 10
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
        try:
            t = buf.lookup_transform("torso_lift_link", "gripper_grasping_frame", rclpy.time.Time()).transform.translation
            return [t.x, t.y, t.z]
        except Exception:  # noqa: BLE001
            continue
    fail("no TF torso_lift_link -> gripper_grasping_frame")


def main():
    rclpy.init()
    node = Node("mock_check")
    cmd = sys.argv[1]
    if cmd == "owner":
        owner(node, sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 30)
    elif cmd == "snapshot":
        json.dump(joint_positions(node), open(sys.argv[2], "w"))
    elif cmd == "moved":
        moved(json.load(open(sys.argv[2])), json.load(open(sys.argv[3])))
    elif cmd == "ee-snapshot":
        time.sleep(2.0)  # let the arm settle
        json.dump(ee_position(node), open(sys.argv[2], "w"))
    elif cmd == "ee-moved":
        b, a = json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
        want = [float(x) for x in sys.argv[4:7]]
        got = [y - x for x, y in zip(b, a)]
        good = all(abs(g - w) < 0.003 for g, w in zip(got, want))
        (ok if good else fail)("keyboard teleop moved the hand by " + " ".join(f"{g * 1000:+.1f}" for g in got)
                               + " mm (wanted " + " ".join(f"{w * 1000:+.1f}" for w in want) + ")")
    elif cmd == "at-motion":
        at_motion(node, sys.argv[2])
    rclpy.shutdown()


if __name__ == "__main__":
    main()
