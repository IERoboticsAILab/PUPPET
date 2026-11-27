#!/usr/bin/env python3
"""Hand TIAGo's joints to the telepresence controllers while this node runs, and back on exit.

ROS 2 port of the ROS 1 tp_controller_switcher.py. Pairs every `<x>_tp_controller` with PAL's
`<x>_controller` (arm, head, torso, gripper): on start, activates ours and deactivates PAL's;
on Ctrl+C, the reverse (best effort), so PlayMotion2 and PAL's tools work again.
"""

import signal
import sys

import rclpy
from controller_manager_msgs.srv import ListControllers, SwitchController
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import JointState

CM = "/controller_manager"


def pal_name(tp_name):
    return tp_name.replace("_tp_controller", "_controller")


class Switcher(Node):
    def __init__(self):
        super().__init__("tp_controller_switcher")
        self.list_cli = self.create_client(ListControllers, CM + "/list_controllers")
        self.switch_cli = self.create_client(SwitchController, CM + "/switch_controller")

    def call(self, client, request, timeout=10.0):
        if not client.wait_for_service(timeout_sec=timeout):
            raise RuntimeError(f"{client.srv_name} not available: is TIAGo's controller_manager running?")
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=timeout)
        if future.result() is None:
            raise RuntimeError(f"{client.srv_name} did not answer in {timeout} s")
        return future.result()

    def controllers(self):
        return {c.name: c.state for c in self.call(self.list_cli, ListControllers.Request()).controller}

    def switch(self, to_tp, strict=True):
        cs = self.controllers()
        tps = [n for n in cs if n.endswith("_tp_controller")]
        if not tps:
            raise RuntimeError("no *_tp_controller loaded: start telepresence_controllers.launch.py first")
        pals = [pal_name(n) for n in tps if pal_name(n) in cs]
        ours, theirs = (tps, pals) if to_tp else (pals, tps)
        activate = [n for n in ours if cs[n] != "active"]
        deactivate = [n for n in theirs if cs[n] == "active"]
        if not activate and not deactivate:
            self.get_logger().info("controllers already in place")
            return True
        req = SwitchController.Request()
        req.activate_controllers = activate
        req.deactivate_controllers = deactivate
        req.strictness = SwitchController.Request.STRICT if strict else SwitchController.Request.BEST_EFFORT
        self.get_logger().info(f"switching: activate {activate}, deactivate {deactivate}")
        ok = self.call(self.switch_cli, req).ok
        if not ok:
            self.get_logger().error(
                f"switch_controller refused (activate {activate}, deactivate {deactivate}). "
                f"Check `ros2 control list_controllers`: a controller may be unconfigured or hold the same joints.")
        return ok


def wait_for_joint_states(node, timeout=30.0):
    got = []
    sub = node.create_subscription(JointState, "/joint_states", lambda m: got.append(1), 1)
    end = node.get_clock().now().nanoseconds + int(timeout * 1e9)
    while rclpy.ok() and not got and node.get_clock().now().nanoseconds < end:
        rclpy.spin_once(node, timeout_sec=0.5)
    node.destroy_subscription(sub)
    return bool(got)


def raise_interrupt(*_):
    raise KeyboardInterrupt


def main():
    # rclpy's own SIGINT handler shuts the context down before `finally` runs, and then the
    # joints could not be handed back. Use Python's handlers instead (SIGTERM too, for tmux/launch).
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    signal.signal(signal.SIGINT, raise_interrupt)
    signal.signal(signal.SIGTERM, raise_interrupt)
    node = Switcher()
    try:
        if not wait_for_joint_states(node):
            node.get_logger().fatal("no /joint_states for 30 s: motors off or e-stop pressed?")
            return 1
        if not node.switch(to_tp=True):
            return 1
        node.get_logger().info("telepresence controllers active; Ctrl+C gives the joints back to PAL")
        while True:
            rclpy.spin_once(node, timeout_sec=0.5)  # returns regularly so Ctrl+C is seen
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        node.get_logger().fatal(str(e))
        return 1
    finally:
        try:
            if rclpy.ok():
                node.switch(to_tp=False, strict=False)
        except Exception as e:  # noqa: BLE001 - report and exit, never hang on shutdown
            print(f"tp_controller_switcher: could not give joints back: {e}", file=sys.stderr)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
