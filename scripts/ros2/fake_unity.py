#!/usr/bin/env python3
"""Talk to ROS-TCP-Endpoint the way the Quest app does, without Unity.

    fake_unity.py HOST[:PORT] --listen [SECONDS]
        Read-only. Subscribes to what the headset shows (joint states, camera, odometry, mocap)
        and prints how many messages arrived per topic. No ROS needed (bytes are only counted),
        so it runs on any machine; used by ./puppet doctor/check for the "Unity's view" line.

    fake_unity.py HOST[:PORT] --drive-test
        Used by the mock-robot test only (needs rclpy): publishes tp controller commands and calls
        /tp_arm_motion/command through the endpoint. NEVER run it against the real robot.

Wire format (ROS-TCP-Endpoint v0.7): every frame is
  <u32 len><destination utf-8><u32 len><payload>,
where payload is JSON + "\\0" for system commands ("__subscribe", ...), CDR otherwise.
"""

import argparse
import json
import socket
import struct
import sys
import threading
import time

# Topic -> type, as the ROS 2 APK subscribes (docs/ROS2_INTERFACE.md).
LISTEN_ROS2 = {
    "/joint_states": "sensor_msgs/JointState",
    "/head_front_camera/rgb/image_raw/compressed": "sensor_msgs/CompressedImage",
    "/mobile_base_controller/odom": "nav_msgs/Odometry",
    "/odom_mocap": "nav_msgs/Odometry",
    "/puck_mocap": "nav_msgs/Odometry",
}


class Endpoint:
    def __init__(self, host, port, timeout=5.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(None)
        self.lock = threading.Lock()
        self.counts = {}
        self.handshake = None
        self.errors = []
        self.responses = {}
        self.pending_response = None
        self.cond = threading.Condition()
        threading.Thread(target=self._reader, daemon=True).start()

    # ------------------------------------------------------------------ framing
    def _send_frame(self, dest, payload):
        d = dest.encode()
        with self.lock:
            self.sock.sendall(struct.pack("<I", len(d)) + d + struct.pack("<I", len(payload)) + payload)

    def command(self, name, **params):
        self._send_frame(name, json.dumps(params).encode() + b"\0")

    def _recv(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise EOFError
            buf += chunk
        return buf

    def _reader(self):
        try:
            while True:
                dest = self._recv(struct.unpack("<I", self._recv(4))[0]).decode()
                payload = self._recv(struct.unpack("<I", self._recv(4))[0])
                with self.cond:
                    if dest == "__handshake":
                        self.handshake = json.loads(payload.decode().rstrip("\0"))
                    elif dest == "__error":
                        self.errors.append(payload.decode(errors="replace"))
                    elif dest == "__response":
                        self.pending_response = json.loads(payload.decode().rstrip("\0"))["srv_id"]
                    elif self.pending_response is not None:
                        self.responses[self.pending_response] = payload
                        self.pending_response = None
                    elif not dest.startswith("__"):
                        self.counts[dest] = self.counts.get(dest, 0) + 1
                    self.cond.notify_all()
        except (EOFError, OSError):
            pass

    # ------------------------------------------------------------------ Unity-like API
    def subscribe(self, topic, msg_type):
        self.command("__subscribe", topic=topic, message_name=msg_type)

    def register_publisher(self, topic, msg_type):
        self.command("__publish", topic=topic, message_name=msg_type, queue_size=1, latch=False)

    def publish(self, topic, cdr):
        self._send_frame(topic, cdr)

    def call_service(self, topic, srv_type, cdr_request, srv_id=1, timeout=30.0):
        self.command("__ros_service", topic=topic, message_name=srv_type)
        self.command("__request", srv_id=srv_id)
        self._send_frame(topic, cdr_request)
        with self.cond:
            self.cond.wait_for(lambda: srv_id in self.responses, timeout=timeout)
            return self.responses.pop(srv_id, None)


def parse_host(s):
    host, _, port = s.partition(":")
    return host, int(port or 10000)


def listen(ep, seconds):
    with ep.cond:
        ep.cond.wait_for(lambda: ep.handshake is not None, timeout=5.0)
    if ep.handshake is None:
        print("FAIL  no handshake from the endpoint (is it ROS-TCP-Endpoint?)")
        return 1
    proto = json.loads(ep.handshake.get("metadata", "{}")).get("protocol", "?")
    print(f"ok    endpoint {ep.handshake.get('version')} protocol {proto}")
    for topic, msg_type in LISTEN_ROS2.items():
        ep.subscribe(topic, msg_type)
    time.sleep(seconds)
    bad = 0
    for topic in LISTEN_ROS2:
        n = ep.counts.get(topic, 0)
        rate = n / seconds
        print(f"{'ok  ' if n else 'none'}  {topic}: {n} msgs ({rate:.1f}/s)")
        bad |= topic == "/joint_states" and n == 0
    for e in ep.errors:
        print(f"FAIL  endpoint error: {e}")
    return 1 if bad or ep.errors else 0


def drive_test(ep, motion=None):
    """Mock robot only: 3 s of tp controller commands, or (motion) one ArmMotion call."""
    from geometry_msgs.msg import PoseStamped, QuaternionStamped
    from rclpy.serialization import deserialize_message, serialize_message
    from std_msgs.msg import Int32

    if motion:
        return arm_motion(ep, motion)
    ep.register_publisher("/torso_tp_controller/command", "std_msgs/Int32")
    ep.register_publisher("/head_tp_controller/command", "geometry_msgs/QuaternionStamped")
    ep.register_publisher("/arm_tp_controller/command", "geometry_msgs/PoseStamped")
    ep.register_publisher("/gripper_tp_controller/command", "std_msgs/Int32")
    time.sleep(1.0)

    t0 = time.monotonic()
    while time.monotonic() - t0 < 3.0:
        t = time.monotonic() - t0  # Unity stamps with time since app start, like this
        stamp = {"sec": int(t), "nanosec": int((t % 1.0) * 1e9)}
        ep.publish("/torso_tp_controller/command", serialize_message(Int32(data=1)))
        ep.publish("/gripper_tp_controller/command", serialize_message(Int32(data=-1)))
        q = QuaternionStamped()
        q.header.stamp.sec, q.header.stamp.nanosec = stamp["sec"], stamp["nanosec"]
        q.quaternion.y, q.quaternion.w = -0.0998, 0.995  # ~11 deg about y
        ep.publish("/head_tp_controller/command", serialize_message(q))
        p = PoseStamped()
        p.header.stamp = q.header.stamp
        p.header.frame_id = "base_footprint"
        p.pose.position.x = min(0.05, 0.05 * t)  # 5 cm forward, relative to the start pose
        p.pose.orientation.w = 1.0
        ep.publish("/arm_tp_controller/command", serialize_message(p))
        time.sleep(1 / 30)
    time.sleep(0.5)
    for e in ep.errors:
        print(f"FAIL  endpoint error: {e}")
    return 1 if ep.errors else 0


def arm_motion(ep, motion):
    from rclpy.serialization import deserialize_message, serialize_message
    from tiago_telepresence_controllers.srv import ArmMotion

    raw = ep.call_service("/tp_arm_motion/command", "tiago_telepresence_controllers/ArmMotion",
                          serialize_message(ArmMotion.Request(command=motion)), timeout=40.0)
    if raw is None:
        print("FAIL  no ArmMotion response through the endpoint")
        return 1
    res = deserialize_message(raw, ArmMotion.Response)
    print(f"{'ok  ' if res.success else 'FAIL'}  ArmMotion '{motion}' via endpoint: success={res.success} {res.message}")
    for e in ep.errors:
        print(f"FAIL  endpoint error: {e}")
    return 0 if res.success and not ep.errors else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("endpoint", help="HOST[:PORT], e.g. 10.205.3.26:10000")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--listen", type=float, nargs="?", const=3.0, metavar="SECONDS")
    g.add_argument("--drive-test", action="store_true")
    g.add_argument("--arm-motion", metavar="MOTION", help="mock robot only: call /tp_arm_motion/command")
    args = ap.parse_args()
    try:
        ep = Endpoint(*parse_host(args.endpoint))
    except OSError as e:
        print(f"FAIL  cannot connect to {args.endpoint}: {e}")
        return 1
    if args.listen is not None:
        return listen(ep, args.listen)
    return drive_test(ep, args.arm_motion)


if __name__ == "__main__":
    sys.exit(main())
