#!/usr/bin/env python3
"""Live status of a PUPPET session (ROS 1), started by `./puppet status`.

One screen, refreshed every couple of seconds. Every row is ok, wait (expected before the demo
starts, e.g. no headset yet) or FAIL, and every FAIL says what to do. Read-only: it subscribes,
lists, pings and asks TIAGo over SSH; it never starts, stops or commands anything.

  ./puppet status          live view (Ctrl+C closes the view; the session keeps running)
  ./puppet status --once   one pass, exit code 1 if anything FAILs (for scripts and tests)

Settings come from the environment that ./puppet exports from config/puppet.env.
"""

import os
import re
import socket
import subprocess
import sys
import threading
import time
from collections import deque

E = os.environ
PUPPET = os.path.join(E["PUPPET_ROOT"], "puppet")
SESSION = E.get("SESSION", "puppet")
TCP_PORT = E.get("TCP_PORT", "10000")
MASTER_HOST = re.sub(r"^\w+://|:\d+/?$", "", E["ROS_MASTER_URI"])
REFRESH = float(E.get("STATUS_REFRESH", "2"))
TP = ["arm_tp_controller", "head_tp_controller", "torso_tp_controller", "gripper_tp_controller"]
PAL = [c.replace("_tp_", "_") for c in TP]

socket.setdefaulttimeout(3)  # ROS master lookups: a switched-off TIAGo must not freeze the view

if sys.stdout.isatty():
    G, Y, R, B, D, N = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[2m", "\033[0m"
else:
    G = Y = R = B = D = N = ""


def run(cmd, timeout):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (subprocess.TimeoutExpired, OSError):
        return None


def ping(host):
    try:
        return subprocess.call(["ping", "-c", "1", "-W", "1", host], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=3) == 0
    except subprocess.TimeoutExpired:
        return False


# ------------------------------------------------------------------ slow facts, in a thread
class Background:
    """TIAGo-side facts over SSH, pings and tmux; refreshed in the background so the view never
    stalls on a slow robot."""

    def __init__(self):
        self.facts = {}
        self.lock = threading.Lock()

    def poll(self):
        f = {"tiago_ping": ping(MASTER_HOST), "motive_ping": ping(E.get("MOTIVE_IP", "")) if E.get("MOTIVE_IP") else None}
        remote = (
            "echo estop=$(timeout 4 rostopic echo -n 1 /power_status/is_emergency 2>/dev/null | head -1); "
            "echo listen=$(ss -Hltn 'sport = :%s' | wc -l); "
            "echo peers=$(ss -Htn state established '( sport = :%s )' | awk '{print $4}' "
            "| sed 's/^\\[::ffff://; s/\\]:/:/; s/:[0-9]*$//' | sort -u | tr '\\n' ' ')" % (TCP_PORT, TCP_PORT))
        out = run([PUPPET, "_tiago_batch", remote], 20) if f["tiago_ping"] else None
        f["ssh"] = out is not None and "listen=" in out
        for line in (out or "").splitlines():
            k, _, v = line.partition("=")
            f[k] = v.strip()
        f["windows"] = self.windows()
        with self.lock:
            self.facts = f

    @staticmethod
    def windows():
        try:
            p = subprocess.run(["tmux", "-L", "puppet", "list-windows", "-t", SESSION, "-F",
                                "#{window_name} #{pane_dead} #{pane_dead_status}"], capture_output=True, text=True, timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            return None
        if p.returncode != 0:
            return None  # no session
        out = p.stdout
        w = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                w[parts[0]] = (parts[1] == "1", parts[2] if len(parts) > 2 else "")
        return w

    def loop(self):
        while True:
            self.poll()
            time.sleep(max(REFRESH, 2.0))

    def get(self):
        with self.lock:
            return dict(self.facts)


def tail(window, lines=40):
    out = run(["tmux", "-L", "puppet", "capture-pane", "-p", "-t", "%s:%s" % (SESSION, window), "-S", "-%d" % lines], 5) or ""
    return [l.rstrip() for l in out.splitlines() if l.strip()]


# ------------------------------------------------------------------ ROS facts
class Ros:
    def __init__(self):
        import rosgraph
        import rospy
        self.rospy, self.rosgraph = rospy, rosgraph
        self.master = rosgraph.Master("/puppet_status")
        self.pid = None
        self.stamps = {}
        self.started = False

    def master_pid(self):
        try:
            return self.master.getPid()
        except Exception:
            return None

    def start(self):
        rospy = self.rospy
        rospy.init_node("puppet_status", anonymous=True, disable_signals=True)
        for t in ["/joint_states", E["BASE_TOPIC"], E["PUCK_TOPIC"], "/odom_mocap", "/puck_mocap"]:
            self.stamps[t] = deque(maxlen=2000)
            rospy.Subscriber(t, rospy.AnyMsg, lambda _m, t=t: self.stamps[t].append(time.time()), queue_size=50)
        self.started = True

    def rate(self, topic, window=2.0):
        now = time.time()
        return sum(1 for s in list(self.stamps.get(topic, ())) if now - s <= window) / window

    def controllers(self):
        try:
            from controller_manager_msgs.srv import ListControllers
            self.rospy.wait_for_service("/controller_manager/list_controllers", timeout=2)
            cs = self.rospy.ServiceProxy("/controller_manager/list_controllers", ListControllers)().controller
            # stock Noetic says "initialized" for loaded-but-never-started; TIAGo says "stopped"
            return {c.name: "stopped" if c.state == "initialized" else c.state for c in cs}
        except Exception:
            return None

    def service(self, name):
        try:
            self.master.lookupService(name)
            return True
        except Exception:
            return False

    def topics(self, pattern):
        try:
            return sorted(t for t, _ in self.master.getPublishedTopics("/") if re.match(pattern, t))
        except Exception:
            return []


# ------------------------------------------------------------------ the rows
def rows(ros, bg):
    """List of (state, label, text, hint). state: ok / wait / fail / info."""
    f = bg.get()
    out = []
    add = lambda *r: out.append(r)

    # TIAGo and its ROS master
    if not f:
        add("wait", "TIAGo", "checking...", "")
    elif not f.get("tiago_ping"):
        add("fail", "TIAGo", "%s does not answer" % MASTER_HOST, "TIAGo on and on the lab WiFi? This PC on the same network?")
    elif not f.get("ssh"):
        add("fail", "TIAGo", "reachable, but SSH to %s fails" % E["TIAGO_SSH"], "ssh %s once by hand (password/host key), or ssh-copy-id" % E["TIAGO_SSH"])
    else:
        add("ok", "TIAGo", "%s reachable, SSH ok" % MASTER_HOST, "")

    pid = ros.master_pid()
    if pid is None:
        add("fail", "ROS master", "%s not answering" % E["ROS_MASTER_URI"], "TIAGo still booting? Wait 2 min after power-on. Never start a roscore here.")
        return out, False
    if ros.pid is not None and pid != ros.pid:
        return out, True  # master restarted (TIAGo rebooted): start over
    ros.pid = pid
    if not ros.started:
        ros.start()
    add("ok", "ROS master", E["ROS_MASTER_URI"], "")

    e = f.get("estop", "").replace("data: ", "")  # bare value or "data: <value>", by message type
    if e == "True":
        add("fail", "E-stop", "PRESSED", "Twist the red button to release it, then press the blinking green button.")
    elif e == "False":
        add("ok", "E-stop", "released", "")
    elif f:
        add("wait", "E-stop", "unknown", "Look at the robot: red button up, green button lit.")

    hz = ros.rate("/joint_states")
    if hz >= 20:
        add("ok", "Joint states", "%.0f Hz" % hz, "")
    else:
        add("fail", "Joint states", "silent" if hz == 0 else "%.0f Hz" % hz, "Motors off? If the green button blinks, press it.")

    cs = ros.controllers()
    if cs is None:
        add("fail", "Controllers", "controller_manager not answering", "TIAGo still booting, or its controllers crashed: reboot TIAGo.")
    else:
        tp = [cs.get(c, "missing") for c in TP]
        pal = [cs.get(c, "missing") for c in PAL]
        if all(s == "running" for s in tp):
            add("ok", "Controllers", "headset drives the robot (4 tp controllers running)", "")
        elif all(s == "missing" for s in tp):
            add("wait" if all(s == "running" for s in pal) else "fail", "Controllers",
                "telepresence not started; PAL controllers %s" % ("running" if all(s == "running" for s in pal) else "/".join(pal)),
                "./puppet up" if all(s == "running" for s in pal) else "Reboot TIAGo if PAL controllers stay stopped.")
        elif cs.get("arm_controller") == "running" and cs.get("arm_tp_controller") == "stopped":
            add("wait", "Controllers", "PlayMotion has the arm (B-button motion, up to 30 s)",
                "If this lasts longer than a minute: ./puppet reset-arm")
        else:
            add("fail", "Controllers", ", ".join("%s=%s" % (c.replace("_controller", ""), s) for c, s in zip(TP, tp) if s != "running"),
                "./puppet reset-arm")

    # Nothing below runs without a session: say that once instead of failing every row.
    if f and f.get("windows") is None:
        add("fail", "Session", "no PUPPET session running on this PC", "./puppet up")
        return out, False

    # Headset link
    if f.get("listen") is None:
        add("wait", "ROS-TCP endpoint", "unknown (no SSH)", "")
    elif f.get("listen", "0") != "0":
        add("ok", "ROS-TCP endpoint", "listening on %s:%s" % (E["TCP_IP"], TCP_PORT), "")
    else:
        add("fail", "ROS-TCP endpoint", "nothing listens on %s:%s" % (E["TCP_IP"], TCP_PORT), "./puppet logs telepresence, then ./puppet reset-arm")
    peers = [p for p in f.get("peers", "").split() if p and p != E.get("ROS_IP")]
    if peers:
        add("ok", "Quest", "connected from %s" % ", ".join(peers), "")
    elif f.get("listen", "0") != "0":
        add("wait", "Quest", "not connected", "Quest on the lab WiFi, then Library > Unknown Sources > pxspatial. Restart the app if it was open before telepresence started.")

    # OptiTrack
    if E.get("MOTIVE_IP"):
        if f.get("motive_ping") is False:
            add("fail", "Motive (gaia)", "%s does not answer" % E["MOTIVE_IP"], "gaia on? Same network?")
    for label, topic in (("OptiTrack base", E["BASE_TOPIC"]), ("OptiTrack puck", E["PUCK_TOPIC"])):
        hz = ros.rate(topic)
        if hz > 0:
            add("ok", label, "%s %.0f Hz" % (topic, hz), "")
        else:
            seen = ros.topics(r"^/natnet_ros/.*/pose$")
            add("fail", label, "%s silent" % topic,
                "Motive streaming, rigid body visible?" + (" Published: %s" % " ".join(seen) if seen else " (no /natnet_ros/*/pose at all: ./puppet logs mocap)"))
    for topic in ("/odom_mocap", "/puck_mocap"):
        src = E["BASE_TOPIC"] if topic == "/odom_mocap" else E["PUCK_TOPIC"]
        if ros.rate(topic) > 0:
            add("ok", topic, "%.0f Hz" % ros.rate(topic), "")
        elif ros.rate(src) > 0:
            add("fail", topic, "silent although its input streams", "./puppet logs mocap")

    # B button
    if ros.service("/tp_arm_motion/command"):
        last = [l for l in tail("arm_motion", 60) if re.search(r"Executing motion|completed|did not finish|Failed|ERROR|FATAL", l)]
        add("ok", "B button", "ready" + (" (last: %s)" % re.sub(r"^\[[^\]]*\]\s*\[[^\]]*\]:\s*", "", last[-1])[:60] if last else ""), "")
    else:
        add("fail", "B button", "/tp_arm_motion/command missing", "./puppet logs arm_motion, then ./puppet reset-arm")

    # The tmux windows: a dead one is the most direct "what broke"
    w = f.get("windows")
    if w:
        dead = [n for n, (d, _) in w.items() if d]
        live = [n for n, (d, _) in w.items() if not d and n != "control"]
        if dead:
            for n in dead:
                lines = tail(n, 40)
                add("fail", "Process %s" % n, "exited (code %s)" % (w[n][1] or "?"),
                    "last log line: %s  (./puppet logs %s)" % (lines[-1][:90] if lines else "-", n))
        else:
            add("ok", "Processes", ", ".join(live) or "-", "")
    return out, False


def render(out, live):
    marks = {"ok": G + "ok  " + N, "wait": Y + "wait" + N, "fail": R + "FAIL" + N, "info": "    "}
    lines = []
    if live:
        lines.append("%sPUPPET status%s  %s   %s(refresh %gs. Ctrl+C closes this view; the demo keeps running)%s"
                     % (B, N, time.strftime("%H:%M:%S"), D, REFRESH, N))
    for state, label, text, hint in out:
        lines.append("  %s  %-17s %s" % (marks[state], label, text))
        if hint and state != "ok":
            lines.append("        %s-> %s%s" % (Y if state == "wait" else R, hint, N))
    if live:
        lines.append("")
        lines.append("%s./puppet down%s stop   %s./puppet reset-arm%s arm back to start   %s./puppet logs [window]%s logs"
                     % (B, N, B, N, B, N))
    return "\n".join(lines)


def main():
    once = "--once" in sys.argv
    bg = Background()
    bg.poll()
    try:
        ros = Ros()
    except ImportError:
        print("ROS 1 Python (rospy) not found: run this through ./puppet status")
        return 2
    if once:
        out, _ = rows(ros, bg)
        if ros.started:  # rates need a moment of subscription
            time.sleep(2.5)
            out, _ = rows(ros, bg)
        print(render(out, False))
        return 1 if any(r[0] == "fail" for r in out) else 0

    threading.Thread(target=bg.loop, daemon=True).start()
    try:
        while True:
            out, restart = rows(ros, bg)
            if restart:  # TIAGo's master came back with a new PID: subscriptions are stale
                os.execv(sys.executable, [sys.executable] + sys.argv)
            sys.stdout.write("\033[H\033[J" + render(out, True) + "\n")
            sys.stdout.flush()
            time.sleep(REFRESH)
    except KeyboardInterrupt:
        running = bg.get().get("windows") is not None
        print("\nStatus view closed." + (" The demo keeps running (./puppet down stops it)." if running else ""))
        return 0


if __name__ == "__main__":
    sys.exit(main())
