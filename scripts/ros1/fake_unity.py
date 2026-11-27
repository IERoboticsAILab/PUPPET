#!/usr/bin/env python3
"""Talk to ROS-TCP-Endpoint (ROS 1) the way the Quest app (pxspatial) does, without Unity.

For the offline mock test only (scripts/ros1/mock_test.sh). NEVER run the commanding modes
against the real robot: they move the arm.

    fake_unity.py HOST[:PORT] --hold SECONDS
        Connect like the headset and stay connected (the status view shows "Quest connected").
    fake_unity.py HOST[:PORT] --arm-motion NAME
        Press B: call /tp_arm_motion/command with NAME (offer or home), print the reply and time.
    fake_unity.py HOST[:PORT] --arm-move DX DY DZ [--seconds S] [--gap G]
        Stream /arm_tp_controller/command like ArmCommander: a hand offset ramping to (DX, DY, DZ)
        metres, in the message's own axes. --gap pauses the stream for G seconds halfway (a WiFi
        hiccup), holding the offset.

Wire format (ROS-TCP-Endpoint): every frame is <u32 len><destination><u32 len><payload>; payload
is JSON for system commands ("__publish", "__request", ...), ROS 1 serialization otherwise.
"""

import argparse
import io
import json
import socket
import struct
import sys
import threading
import time


class Endpoint:
    def __init__(self, host, port, timeout=5.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(None)
        self.lock = threading.Lock()
        self.errors = []
        self.responses = {}
        self.pending = None
        self.cond = threading.Condition()
        threading.Thread(target=self._reader, daemon=True).start()

    def frame(self, dest, payload):
        d = dest.encode()
        with self.lock:
            self.sock.sendall(struct.pack("<I", len(d)) + d + struct.pack("<I", len(payload)) + payload)

    def command(self, name, **params):
        self.frame(name, json.dumps(params).encode())  # ROS 1 endpoint: plain JSON, no "\0"

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
                    if dest == "__error":
                        self.errors.append(payload.decode(errors="replace"))
                    elif dest == "__response":
                        self.pending = json.loads(payload.decode().rstrip("\0"))["srv_id"]
                    elif self.pending is not None and not dest.startswith("__"):
                        self.responses[self.pending] = payload
                        self.pending = None
                    self.cond.notify_all()
        except (EOFError, OSError):
            pass

    @staticmethod
    def ser(msg):
        b = io.BytesIO()
        msg.serialize(b)
        return b.getvalue()

    def call(self, topic, srv_type, request, srv_id=1, timeout=60.0):
        self.command("__ros_service", topic=topic, message_name=srv_type)
        time.sleep(0.2)
        self.command("__request", srv_id=srv_id)
        self.frame(topic, self.ser(request))
        with self.cond:
            self.cond.wait_for(lambda: srv_id in self.responses, timeout=timeout)
            return self.responses.pop(srv_id, None)


def arm_motion(ep, name):
    from tiago_telepresence_controllers.srv import ArmMotionRequest, ArmMotionResponse
    t0 = time.monotonic()
    raw = ep.call("/tp_arm_motion/command", "tiago_telepresence_controllers/ArmMotion", ArmMotionRequest(command=name))
    dt = time.monotonic() - t0
    if raw is None:
        print("FAIL  no reply to ArmMotion '%s' within 60 s" % name)
        return 1
    res = ArmMotionResponse()
    res.deserialize(raw)
    print("%s  ArmMotion '%s': success=%s after %.1f s %s" % ("ok  " if res.success else "FAIL", name, res.success, dt, res.message))
    return 0 if res.success else 3


def arm_move(ep, d, seconds, gap):
    from geometry_msgs.msg import PoseStamped
    ep.command("__publish", topic="/arm_tp_controller/command", message_name="geometry_msgs/PoseStamped", queue_size=1, latch=False)
    time.sleep(0.5)
    t0 = time.monotonic()
    paused = False
    while True:
        t = time.monotonic() - t0
        if t > seconds + (gap or 0) + 1.0:
            break
        if gap and seconds / 2 <= t < seconds / 2 + gap:
            if not paused:
                print("      stream paused for %.1f s (offset held at %.0f%%)" % (gap, 50))
                paused = True
            time.sleep(1 / 30)
            continue
        k = min(1.0, (t - (gap if gap and t >= seconds / 2 + gap else 0)) / seconds)
        p = PoseStamped()
        now = time.monotonic()  # Unity stamps with time since app start
        p.header.stamp.secs, p.header.stamp.nsecs = int(now), int((now % 1.0) * 1e9)
        p.header.frame_id = "base_footprint"
        p.pose.position.x, p.pose.position.y, p.pose.position.z = (k * c for c in d)
        p.pose.orientation.w = 1.0
        ep.frame("/arm_tp_controller/command", ep.ser(p))
        time.sleep(1 / 30)
    return 1 if ep.errors else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("endpoint")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--hold", type=float, metavar="SECONDS")
    g.add_argument("--arm-motion", metavar="NAME")
    g.add_argument("--arm-move", type=float, nargs=3, metavar=("DX", "DY", "DZ"))
    ap.add_argument("--seconds", type=float, default=2.0)
    ap.add_argument("--gap", type=float, default=0.0)
    a = ap.parse_args()
    host, _, port = a.endpoint.partition(":")
    try:
        ep = Endpoint(host, int(port or 10000))
    except OSError as e:
        print("FAIL  cannot connect to %s: %s" % (a.endpoint, e))
        return 1
    if a.hold is not None:
        time.sleep(a.hold)
        rc = 0
    elif a.arm_motion:
        rc = arm_motion(ep, a.arm_motion)
    else:
        rc = arm_move(ep, a.arm_move, a.seconds, a.gap)
    for e in ep.errors:
        print("FAIL  endpoint error: %s" % e)
    return rc or (1 if ep.errors else 0)


if __name__ == "__main__":
    sys.exit(main())
