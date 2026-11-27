#!/usr/bin/env python3
"""/tp_arm_motion/command (tiago_telepresence_controllers/ArmMotion): play a PlayMotion2 motion
mid-session, as asked by the Quest (extend-arm button: "offer" / "home").

ROS 2 port of the ROS 1 arm_motion.py, same behaviour:
  1. hand the joints back to PAL's controllers (PlayMotion2 drives those),
  2. wait 3 s, play the motion, wait up to --timeout s,
  3. hand the joints to the telepresence controllers again.
The tp controller list is read on every call, never cached at startup (that was the B-button bug).
"""

import argparse
import os
import signal
import sys
import threading
import time

import rclpy
from controller_manager_msgs.srv import ListControllers, SwitchController
from play_motion2_msgs.action import PlayMotion2
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.utilities import remove_ros_args

from tiago_telepresence_controllers.srv import ArmMotion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from play_motion import add_motions, default_motions_file  # noqa: E402  (installed next to this script)

CM = "/controller_manager"


def pal_name(tp_name):
    return tp_name.replace("_tp_controller", "_controller")


def wait(future, timeout):
    end = time.monotonic() + timeout
    while not future.done() and time.monotonic() < end:
        time.sleep(0.05)
    return future.result() if future.done() else None


class ArmMotionNode(Node):
    def __init__(self, args):
        super().__init__("tp_arm_motion")
        self.args = args
        self.current = args.initial_state
        self.lock = threading.Lock()
        group = ReentrantCallbackGroup()
        self.list_cli = self.create_client(ListControllers, CM + "/list_controllers", callback_group=group)
        self.switch_cli = self.create_client(SwitchController, CM + "/switch_controller", callback_group=group)
        self.motion_cli = ActionClient(self, PlayMotion2, args.action, callback_group=group)
        self.srv = self.create_service(ArmMotion, "/tp_arm_motion/command", self.on_request, callback_group=group)

    # ------------------------------------------------------------------ controllers
    def controllers(self):
        res = wait(self.list_cli.call_async(ListControllers.Request()), 5.0)
        if res is None:
            raise RuntimeError("controller_manager/list_controllers did not answer")
        return {c.name: c.state for c in res.controller}

    def switch(self, to_tp, label):
        cs = self.controllers()
        tps = [n for n in cs if n.endswith("_tp_controller")]
        pals = [pal_name(n) for n in tps if pal_name(n) in cs]
        ours, theirs = (tps, pals) if to_tp else (pals, tps)
        req = SwitchController.Request()
        req.activate_controllers = [n for n in ours if cs[n] != "active"]
        req.deactivate_controllers = [n for n in theirs if cs[n] == "active"]
        req.strictness = SwitchController.Request.STRICT
        self.get_logger().info(
            f"switching ({label}): activate {req.activate_controllers}, deactivate {req.deactivate_controllers}")
        if not req.activate_controllers and not req.deactivate_controllers:
            return True
        res = wait(self.switch_cli.call_async(req), 5.0)
        if res is None or not res.ok:
            self.get_logger().error(f"failed to switch controllers ({label}); see `ros2 control list_controllers`")
            return False
        return True

    # ------------------------------------------------------------------ motion
    def play(self, name):
        if name == self.current:
            self.get_logger().info(f"motion '{name}' already completed")
            return True, ""

        if not self.motion_cli.wait_for_server(timeout_sec=5.0):
            return False, f"PlayMotion2 action {self.args.action} not available (is play_motion2 running?)"

        self.get_logger().info(f"executing motion: {name}")
        if not self.switch(to_tp=False, label="pre"):
            return False, "could not hand the joints to PAL's controllers"
        time.sleep(3.0)  # important (as in ROS 1): let the controllers settle

        ok, err = False, ""
        try:
            goal = PlayMotion2.Goal()
            goal.motion_name = name
            goal.skip_planning = self.args.skip_planning
            handle = wait(self.motion_cli.send_goal_async(goal), 5.0)
            if handle is None or not handle.accepted:
                err = f"PlayMotion2 rejected '{name}' (unknown motion? `ros2 service call /play_motion2/list_motions ...`)"
            else:
                result = wait(handle.get_result_async(), self.args.timeout)
                if result is None:
                    err = f"motion '{name}' did not finish in {self.args.timeout} s"
                elif result.result.success:
                    ok = True
                else:
                    err = result.result.error or f"motion '{name}' failed"
        finally:
            if not self.switch(to_tp=True, label="post"):
                err = (err + "; " if err else "") + "could not hand the joints back to the tp controllers"
                ok = False

        if ok:
            self.get_logger().info(f"motion '{name}' completed")
            self.current = name
        else:
            self.get_logger().error(err)
        return ok, err

    def on_request(self, req, res):
        if not self.lock.acquire(blocking=False):
            res.success, res.message = False, "another arm motion is still running"
            return res
        try:
            res.success, res.message = self.play(req.command)
        except RuntimeError as e:
            res.success, res.message = False, str(e)
            self.get_logger().error(str(e))
        finally:
            self.lock.release()
        return res


def raise_interrupt(*_):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--motion", default="", help="motion to play once at startup")
    parser.add_argument("--initial-state", default="home", help="motion the arm is assumed to be in")
    parser.add_argument("--action", default="/play_motion2")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="seconds to wait for a motion (PAL home from offer takes ~13 s; ROS 1 waited 10 s and cut it)")
    parser.add_argument("--skip-planning", nargs="?", const="true", default="false",
                        type=lambda v: str(v).lower() in ("1", "true", "yes"),
                        help="play motions without MoveIt planning (true/false)")
    parser.add_argument("--motions-file", default=None, help="PUPPET motions to register with play_motion2")
    args, _ = parser.parse_known_args(remove_ros_args(sys.argv)[1:])

    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    signal.signal(signal.SIGINT, raise_interrupt)
    signal.signal(signal.SIGTERM, raise_interrupt)

    # Register PUPPET's motions (e.g. `extend`) with PAL's running play_motion2; nothing on disk changes.
    helper = Node("tp_arm_motion_setup")
    try:
        added = add_motions(helper, args.motions_file or default_motions_file(), timeout=30.0)
        helper.get_logger().info(f"added PUPPET motions to play_motion2: {added}" if added else "PUPPET motions already known")
    except RuntimeError as e:
        helper.get_logger().error(f"{e}. The B button only plays motions play_motion2 already knows.")
    helper.destroy_node()

    node = ArmMotionNode(args)
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True)
    spinner.start()

    try:
        if not node.list_cli.wait_for_service(timeout_sec=30.0) or not node.switch_cli.wait_for_service(timeout_sec=5.0):
            node.get_logger().fatal("controller_manager services not available after 30 s")
            return 1
        if args.motion:
            node.play(args.motion)
        node.get_logger().info("ready: /tp_arm_motion/command")
        while spinner.is_alive():
            spinner.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown(timeout_sec=1.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
