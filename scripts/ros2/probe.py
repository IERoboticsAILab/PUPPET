#!/usr/bin/env python3
"""PUPPET health probe for ROS 2, run ON TIAGo (./puppet pipes it over SSH: nothing to install).

    python3 probe.py --mode doctor|check [--topic NAME ...] [--seconds 3]

Read-only: it lists the graph, asks controller_manager for its controllers, and listens to
topics. It never publishes, calls a switch or moves anything.
Prints one line per check: "ok|warn|FAIL<TAB>message<TAB>how to fix".
Exit code 1 if any FAIL.
"""

import argparse
import collections
import os
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.utilities import get_message

TP = ["arm_tp_controller", "head_tp_controller", "torso_tp_controller", "gripper_tp_controller"]
PAL = ["arm_controller", "head_controller", "torso_controller", "gripper_controller"]
PUPPET_NODES = ["/tp_controller_switcher", "/tp_arm_motion", "/UnityEndpoint", "/natnet_ros",
                "/optitrack_pose_to_odom", "/puck_pose_to_odom"]

results = []


def report(level, msg, fix=""):
    results.append(level)
    print(f"{level}\t{msg}\t{fix}", flush=True)


def listening(port):
    """Is something listening on TCP `port`? Reads /proc, so it does not poke the endpoint."""
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path) as f:
                for line in f.readlines()[1:]:
                    parts = line.split()
                    if parts[3] == "0A" and int(parts[1].rsplit(":", 1)[1], 16) == port:
                        return True
        except OSError:
            pass
    return False


def controllers(node):
    from controller_manager_msgs.srv import ListControllers
    cli = node.create_client(ListControllers, "/controller_manager/list_controllers")
    if not cli.wait_for_service(timeout_sec=5.0):
        return None
    fut = cli.call_async(ListControllers.Request())
    rclpy.spin_until_future_complete(node, fut, timeout_sec=5.0)
    return {c.name: c.state for c in fut.result().controller} if fut.done() else None


def sample(node, topics, seconds):
    """Counts messages per topic for `seconds` (best effort: matches any publisher)."""
    counts, last = collections.Counter(), {}
    types = dict(node.get_topic_names_and_types())
    subs = []
    for t in topics:
        if t not in types:
            continue
        cls = get_message(types[t][0])

        def cb(msg, t=t):
            counts[t] += 1
            last[t] = msg
        subs.append(node.create_subscription(cls, t, cb, qos_profile_sensor_data))
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
    return types, counts, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["doctor", "check"], required=True)
    ap.add_argument("--topic", action="append", default=[], help="mocap/odometry topics that must be live")
    ap.add_argument("--tcp-port", type=int, default=10000)
    ap.add_argument("--camera", default="/head_front_camera/rgb/image_raw/compressed")
    ap.add_argument("--seconds", type=float, default=3.0)
    args = ap.parse_args()

    rclpy.init()
    node = Node("puppet_probe")
    report("ok", f"ROS 2 {os.environ.get('ROS_DISTRO', '?')}, RMW {os.environ.get('RMW_IMPLEMENTATION', 'default')}, "
                 f"ROS_DOMAIN_ID {os.environ.get('ROS_DOMAIN_ID', '0')}")

    # --- controller_manager and e-stop
    cs = controllers(node)
    if cs is None:
        report("FAIL", "controller_manager not answering", "TIAGo still booting? check the robot's web GUI / `pal module_manager`")
    watch = ["/joint_states", "/power/is_emergency", args.camera] + args.topic
    time.sleep(1.0)  # let discovery settle before sampling
    types, counts, last = sample(node, watch, args.seconds)

    est = last.get("/power/is_emergency")
    if est is None:
        report("warn", "e-stop state unknown (/power/is_emergency silent)", "check the red button on the robot")
    elif est.data:
        report("FAIL", "E-stop pressed", "twist the red button up, then press the blinking green button")
    else:
        report("ok", "E-stop released")

    if counts["/joint_states"]:
        report("ok", f"/joint_states {counts['/joint_states'] / args.seconds:.0f} Hz")
    else:
        report("FAIL", "/joint_states silent", "motors off? if the green button blinks, press it")

    if cs is not None:
        def state(n):
            return cs.get(n, "missing")
        if args.mode == "doctor":
            pal_bad = [n for n in PAL if state(n) != "active"]
            if pal_bad:
                report("FAIL", "PAL controllers not active: " + ", ".join(f"{n}={state(n)}" for n in pal_bad),
                       "PlayMotion2 needs them for the start pose; reboot TIAGo or `ros2 control set_controller_state <name> active`")
            else:
                report("ok", "PAL arm/head/torso/gripper controllers active")
            stale = [n for n in TP if state(n) == "active"]
            if stale:
                report("FAIL", f"tp controllers still active from an earlier session: {stale}", "./puppet down, or Ctrl+C the old telepresence launch")
        else:
            bad = [n for n in TP if state(n) != "active"]
            if bad:
                report("FAIL", "tp controllers: " + ", ".join(f"{n}={state(n)}" for n in TP),
                       "after an e-stop PAL restarts its own controllers: ./puppet reset-arm")
            else:
                report("ok", "tp controllers active (headset drives the robot)")

    # --- PlayMotion2
    if "/play_motion2/_action/status" in types:
        report("ok", "play_motion2 running")
    else:
        report("FAIL" if args.mode == "doctor" else "warn", "play_motion2 not running", "PAL starts it at boot; check the web GUI's module list")

    # --- camera (Unity's video)
    if counts[args.camera]:
        report("ok", f"camera {args.camera} {counts[args.camera] / args.seconds:.0f} Hz")
    elif args.camera.rsplit("/", 1)[0] in types:
        report("warn", f"{args.camera} missing but the raw image exists", "compressed image_transport not running; see docs/ROS2.md (camera)")
    else:
        report("warn", f"camera {args.camera} silent", "head camera driver down? (ros2 topic list | grep camera)")

    # --- mocap / odometry topics
    for t in args.topic:
        n = counts[t]
        if n:
            report("ok", f"{t} {n / args.seconds:.0f} Hz")
        elif args.mode == "check":
            report("FAIL", f"{t} silent", "rigid body tracked and streaming in Motive (gaia)? names: ros2 topic list | grep natnet_ros")

    # --- endpoint and leftovers from an earlier session
    up = listening(args.tcp_port)
    if args.mode == "check":
        report("ok" if up else "FAIL", f"ROS-TCP-Endpoint {'listening' if up else 'not listening'} on port {args.tcp_port}",
               "" if up else "telepresence window: ./puppet attach")
    elif up:
        report("warn", f"something already listens on port {args.tcp_port} (old endpoint?)", "./puppet down first")

    names = [("/" + ns.strip("/") + "/" + n).replace("//", "/") for n, ns in node.get_node_names_and_namespaces()]
    dup = [n for n, c in collections.Counter(names).items() if c > 1 and n in PUPPET_NODES]
    if dup:
        report("FAIL", f"duplicate nodes: {dup}", "two sessions running? ./puppet down, then check `ros2 node list`")
    if args.mode == "doctor":
        old = [n for n in PUPPET_NODES if n in names]
        if old:
            report("warn", f"PUPPET nodes already running: {old}", "./puppet down first")

    node.destroy_node()
    rclpy.shutdown()
    return 1 if "FAIL" in results else 0


if __name__ == "__main__":
    sys.exit(main())
