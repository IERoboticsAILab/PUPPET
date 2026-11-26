#!/usr/bin/env python3
"""Minimal fake ROS-TCP-Endpoint for testing PUPPET's status HUD without a robot.

  fake_endpoint.py --protocol ROS1|ROS2 [--port 10000] [--joint-states] [--die-after N]

Sends the v0.7.0 handshake, logs what Unity registers, and with --joint-states publishes an
empty ROS 1 sensor_msgs/JointState on /joint_states at 10 Hz (ROS 1 serialization only).
"""
import argparse, json, socket, struct, threading, time


def frame(topic: str, payload: bytes) -> bytes:
    t = topic.encode()
    return struct.pack("<I", len(t)) + t + struct.pack("<I", len(payload)) + payload


def ros1_empty_joint_state(seq: int) -> bytes:
    now = time.time()
    header = struct.pack("<III", seq, int(now), int((now % 1) * 1e9)) + struct.pack("<I", 0)
    return header + struct.pack("<IIII", 0, 0, 0, 0)


def recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf


def reader(conn, log):
    try:
        while True:
            tl = struct.unpack("<I", recv_exact(conn, 4))[0]
            topic = recv_exact(conn, tl).decode(errors="replace")
            pl = struct.unpack("<I", recv_exact(conn, 4))[0]
            payload = recv_exact(conn, pl)
            if topic.startswith("__"):
                log(f"<- {topic} {payload[:160].decode(errors='replace')}")
    except Exception as e:
        log(f"reader done: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", default="ROS1")
    ap.add_argument("--port", type=int, default=10000)
    ap.add_argument("--joint-states", action="store_true")
    ap.add_argument("--die-after", type=float, default=0)
    ap.add_argument("--error-after", type=float, default=0, help="send an __error sys command after N s")
    a = ap.parse_args()
    log = lambda m: print(f"[fake {a.protocol}] {m}", flush=True)

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", a.port))
    srv.listen(1)
    start = time.time()
    log(f"listening on {a.port}")
    while True:
        conn, addr = srv.accept()
        log(f"client {addr}")
        start = time.time()  # timers count from the client connecting
        hs = {"version": "v0.7.0", "metadata": json.dumps({"protocol": a.protocol})}
        conn.sendall(frame("__handshake", json.dumps(hs).encode()))
        threading.Thread(target=reader, args=(conn, log), daemon=True).start()
        seq = 0
        sent_error = False
        try:
            while True:
                if a.die_after and time.time() - start > a.die_after:
                    log("dying (simulated endpoint crash)")
                    conn.close(); srv.close(); return
                if a.error_after and not sent_error and time.time() - start > a.error_after:
                    conn.sendall(frame("__error", json.dumps({"text": "Service /tp_arm_motion/command is not available (fake)"}).encode()))
                    sent_error = True
                if a.joint_states:
                    conn.sendall(frame("/joint_states", ros1_empty_joint_state(seq)))
                    seq += 1
                else:
                    conn.sendall(frame("", b""))  # keepalive
                time.sleep(0.1)
        except Exception as e:
            log(f"client gone: {e}")


if __name__ == "__main__":
    main()
