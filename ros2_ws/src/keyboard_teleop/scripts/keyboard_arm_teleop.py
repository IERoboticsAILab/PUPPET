#!/usr/bin/env python3
"""Keyboard arm teleoperation for TIAGo, ROS 2 (the study's keyboard condition).

Same keys and steps as the ROS 1 version (ros_ws/src/keyboard_teleop), but without MoveIt:
it drives the same arm_tp_controller as the headset, so telepresence must be running
(./puppet up, or telepresence.launch.py). Do not use the headset's arm control at the same time.

    i / k   hand forward / backward        (x of torso_lift_link, i.e. the robot's forward)
    j / l   hand left / right              (y)
    w / s   hand up / down                 (z)
    + or =  step + 1 mm (max 20 mm)        -   step - 1 mm (min 1 mm)
    x       software stop (the arm holds where it is)
    q       quit

Each key moves the hand by `step` (3 mm at start) at `speed` (1 cm/s), with the hand orientation
held. As in ROS 1, keys are ignored while the previous move is still running.

How it works: arm_tp_controller follows a pose offset relative to the hand pose at the moment it
starts receiving commands (H_0_N = H_0_N_initial * H_N), and holds when commands stop for 0.25 s.
This node streams that offset at 30 Hz, compensating for how the controller rotates it (see tick()).
"""

import argparse
import math
import select
import sys
import termios
import threading
import time
import tty

import rclpy
from controller_manager_msgs.srv import ListControllers
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.utilities import remove_ros_args
from tf2_ros import Buffer, TransformListener

TOPIC = "/arm_tp_controller/command"
BASE, TCP = "torso_lift_link", "gripper_grasping_frame"  # arm_tp_controller's start_link / end_link


def quat_rotate_inverse(q, v):
    """Rotate vector v by the inverse of unit quaternion q = (x, y, z, w)."""
    x, y, z, w = -q[0], -q[1], -q[2], q[3]
    # v' = q v q*, written out
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx))


class KeyboardArmTeleop(Node):
    def __init__(self, args):
        super().__init__("keyboard_arm_teleop")
        self.args = args
        self.step = 0.003
        self.speed = args.speed
        self.pub = self.create_publisher(PoseStamped, TOPIC, 1)
        self.tf = Buffer()
        self.tf_listener = TransformListener(self.tf, self)
        self.lock = threading.Lock()
        self.streaming = False
        self.q0 = None                  # hand orientation in BASE when streaming started
        self.target = [0.0, 0.0, 0.0]   # requested offset, BASE axes [m]
        self.cmd = [0.0, 0.0, 0.0]      # offset being streamed, moves toward target at `speed`
        self.create_timer(1.0 / args.rate, self.tick)

    # ------------------------------------------------------------------ checks
    def tp_controller_active(self):
        cli = self.create_client(ListControllers, "/controller_manager/list_controllers")
        if not cli.wait_for_service(timeout_sec=5.0):
            return None
        fut = cli.call_async(ListControllers.Request())
        rclpy.spin_until_future_complete(self, fut, timeout_sec=5.0)
        if not fut.done():
            return None
        return any(c.name == "arm_tp_controller" and c.state == "active" for c in fut.result().controller)

    def hand_orientation(self, timeout=5.0):
        # Called from the key thread; the main thread spins the node, which fills the TF buffer.
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            time.sleep(0.05)
            try:
                t = self.tf.lookup_transform(BASE, TCP, rclpy.time.Time())
                r = t.transform.rotation
                return (r.x, r.y, r.z, r.w)
            except Exception:  # noqa: BLE001 - not available yet
                continue
        return None

    # ------------------------------------------------------------------ streaming
    def tick(self):
        with self.lock:
            if not self.streaming:
                return
            # move cmd toward target, at most speed/rate per tick
            d = [t - c for t, c in zip(self.target, self.cmd)]
            dist = math.sqrt(sum(x * x for x in d))
            max_step = self.speed / self.args.rate
            if dist > max_step:
                self.cmd = [c + x * max_step / dist for c, x in zip(self.cmd, d)]
            else:
                self.cmd = list(self.target)
            # arm_tp_controller (unchanged from ROS 1) turns the commanded change into a twist as
            # R0 * diff(H_prev, H), and diff() is already in base axes: the hand moves by
            # R0 * (R0 * p_N). To move it by `cmd` in torso_lift_link axes, send R0^T R0^T cmd.
            p = quat_rotate_inverse(self.q0, quat_rotate_inverse(self.q0, self.cmd))
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = TCP  # offset in the initial hand frame (what the controller expects)
        msg.pose.position.x, msg.pose.position.y, msg.pose.position.z = p
        msg.pose.orientation.w = 1.0  # hand orientation held
        self.pub.publish(msg)

    def busy(self):
        return any(abs(t - c) > 1e-6 for t, c in zip(self.target, self.cmd))

    def move(self, dx=0.0, dy=0.0, dz=0.0):
        with self.lock:
            if self.streaming and self.busy():
                self.get_logger().warn("Still executing previous move. Ignoring key.")
                return
            start = not self.streaming
        if start:  # (re)start streaming from where the hand is now; no lock while waiting for TF
            q0 = self.hand_orientation()
            if q0 is None:
                self.get_logger().error(f"no TF {BASE} -> {TCP}: is robot_state_publisher running?")
                return
            with self.lock:
                self.q0, self.target, self.cmd, self.streaming = q0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], True
            self.get_logger().info("streaming to arm_tp_controller (the arm follows from here)")
        with self.lock:
            self.target = [self.target[0] + dx, self.target[1] + dy, self.target[2] + dz]
        self.get_logger().info(f"Moving dx={dx:.4f} dy={dy:.4f} dz={dz:.4f}")

    def stop(self):
        with self.lock:
            was = self.streaming
            self.streaming = False
        if was:
            self.get_logger().warn("SOFTWARE STOP: commands stopped, the arm holds (arm_tp_controller times out in 0.25 s)")

    # ------------------------------------------------------------------ keys
    def on_key(self, key):  # not "handle": that is rclpy.Node.handle
        s = self.step
        moves = {"i": (s, 0, 0), "k": (-s, 0, 0), "j": (0, s, 0), "l": (0, -s, 0), "w": (0, 0, s), "s": (0, 0, -s)}
        if key in moves:
            self.move(*moves[key])
        elif key in ("+", "="):
            self.step = min(0.02, self.step + 0.001)
            self.get_logger().info(f"Step increased to {self.step:.4f} m")
        elif key == "-":
            self.step = max(0.001, self.step - 0.001)
            self.get_logger().info(f"Step decreased to {self.step:.4f} m")
        elif key == "x":
            self.stop()
        elif key == "q":
            return False
        return True


def read_keys(node, stop_event):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)  # keys without Enter; Ctrl+C still works
        while not stop_event.is_set():
            if select.select([sys.stdin], [], [], 0.1)[0]:
                if not node.on_key(sys.stdin.read(1).lower()):
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        stop_event.set()


def scripted_keys(node, keys, stop_event):
    """--keys: for tests. Waits for each move to finish, like an operator would."""
    for k in keys:
        if not node.on_key(k):
            break
        time.sleep(0.2)
        while node.streaming and node.busy():
            time.sleep(0.05)
    time.sleep(1.0)
    stop_event.set()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speed", type=float, default=0.01, help="hand speed [m/s] (default 0.01)")
    ap.add_argument("--rate", type=float, default=30.0, help="command rate [Hz]")
    ap.add_argument("--yes", action="store_true", help="do not ask when another node also commands the arm")
    ap.add_argument("--keys", help="tests only: type these keys instead of reading the keyboard")
    args = ap.parse_args(remove_ros_args(sys.argv)[1:])

    rclpy.init()
    node = KeyboardArmTeleop(args)
    print(__doc__.split("\n\n")[1])
    try:
        active = node.tp_controller_active()
        if active is None:
            node.get_logger().fatal("controller_manager not answering: is TIAGo up?")
            return 1
        if not active:
            node.get_logger().fatal("arm_tp_controller is not active: start telepresence first (./puppet up)")
            return 1
        time.sleep(1.0)
        others = node.count_publishers(TOPIC) - 1
        if others > 0:
            node.get_logger().warn(f"{others} other publisher(s) on {TOPIC} (the headset, via ROS-TCP-Endpoint?). "
                                   "Two sources must not command the arm at once.")
            if not args.yes and not args.keys:
                ans = input("Is the headset's arm control off? [y/N] ")
                if not ans.lower().startswith("y"):
                    return 1
        print(f"Step: {node.step} m, speed: {node.speed} m/s. Ready.\n")

        stop_event = threading.Event()
        worker = threading.Thread(target=scripted_keys if args.keys else read_keys,
                                  args=(node, args.keys, stop_event) if args.keys else (node, stop_event), daemon=True)
        worker.start()
        while not stop_event.is_set():
            rclpy.spin_once(node, timeout_sec=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        print("Exiting.")
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
