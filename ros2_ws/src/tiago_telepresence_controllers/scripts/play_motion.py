#!/usr/bin/env python3
"""PlayMotion2 helper for PUPPET (ROS 2), used by ./puppet and arm_motion.py.

    play_motion.py add                 register PUPPET's motions (config/telepresence_motions.yaml)
                                       with the running play_motion2, if missing
    play_motion.py run extend          add, then play `extend` and wait for it
    play_motion.py list                motions play_motion2 knows

Nothing on the robot is edited: motions are added at runtime with /play_motion2/add_motion.
Exit code 0 on success; errors are printed with what to check.
"""

import argparse
import os
import sys
import time

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from play_motion2_msgs.action import PlayMotion2
from play_motion2_msgs.msg import Motion
from play_motion2_msgs.srv import AddMotion, ListMotions
from rclpy.action import ActionClient
from rclpy.node import Node


def default_motions_file():
    return os.path.join(get_package_share_directory("tiago_telepresence_controllers"), "config", "telepresence_motions.yaml")


def load_motions(path):
    with open(path) as f:
        doc = yaml.safe_load(f)
    params = next(iter(doc.values()))["ros__parameters"]
    return params["motions"]


def spin_until(node, future, timeout):
    rclpy.spin_until_future_complete(node, future, timeout_sec=timeout)
    return future.result() if future.done() else None


def list_motions(node, timeout=5.0):
    cli = node.create_client(ListMotions, "/play_motion2/list_motions")
    if not cli.wait_for_service(timeout_sec=timeout):
        raise RuntimeError("/play_motion2/list_motions not available: is play_motion2 running? (ros2 node list | grep play_motion2)")
    res = spin_until(node, cli.call_async(ListMotions.Request()), timeout)
    if res is None:
        raise RuntimeError("/play_motion2/list_motions did not answer")
    return list(res.motion_keys)


def add_motions(node, path, timeout=5.0):
    """Adds every motion of `path` that play_motion2 does not know yet. Returns the added keys."""
    known = set(list_motions(node, timeout))
    cli = node.create_client(AddMotion, "/play_motion2/add_motion")
    if not cli.wait_for_service(timeout_sec=timeout):
        raise RuntimeError("/play_motion2/add_motion not available (play_motion2 older than 1.1?)")
    added = []
    for key, m in load_motions(path).items():
        if key in known:
            continue
        req = AddMotion.Request()
        req.motion = Motion(key=key, joints=m["joints"], positions=[float(x) for x in m["positions"]],
                            times_from_start=[float(t) for t in m["times_from_start"]])
        meta = m.get("meta", {})
        req.motion.name, req.motion.usage, req.motion.description = (str(meta.get(k, "")) for k in ("name", "usage", "description"))
        req.overwrite = False
        res = spin_until(node, cli.call_async(req), timeout)
        if res is None or not res.success:
            raise RuntimeError(f"play_motion2 refused motion '{key}' (joints or positions wrong for this robot?)")
        added.append(key)
    return added


def run_motion(node, name, skip_planning, timeout):
    client = ActionClient(node, PlayMotion2, "/play_motion2")
    if not client.wait_for_server(timeout_sec=5.0):
        raise RuntimeError("/play_motion2 action not available")
    goal = PlayMotion2.Goal(motion_name=name, skip_planning=skip_planning)
    handle = spin_until(node, client.send_goal_async(goal), 5.0)
    if handle is None or not handle.accepted:
        raise RuntimeError(f"play_motion2 rejected '{name}'. Are PAL's arm/torso controllers active? (ros2 control list_controllers)")
    start = time.monotonic()
    result = spin_until(node, handle.get_result_async(), timeout)
    if result is None:
        raise RuntimeError(f"'{name}' did not finish in {timeout:.0f} s")
    if not result.result.success:
        raise RuntimeError(f"'{name}' failed: {result.result.error}")
    return time.monotonic() - start


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["add", "run", "list"])
    ap.add_argument("motion", nargs="?")
    ap.add_argument("--motions-file", default=None)
    ap.add_argument("--skip-planning", action="store_true")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args(rclpy.utilities.remove_ros_args(sys.argv)[1:])

    rclpy.init()
    node = Node("puppet_play_motion")
    try:
        if args.command == "list":
            print("\n".join(sorted(list_motions(node))))
            return 0
        added = add_motions(node, args.motions_file or default_motions_file())
        print(f"added motions: {', '.join(added)}" if added else "PUPPET motions already known to play_motion2")
        if args.command == "run":
            if not args.motion:
                ap.error("run needs a motion name")
            secs = run_motion(node, args.motion, args.skip_planning, args.timeout)
            print(f"'{args.motion}' done in {secs:.1f} s")
        return 0
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
