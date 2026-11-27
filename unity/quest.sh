#!/usr/bin/env bash
# Quest helper for the PUPPET APKs (USB cable or adb over WiFi).
#
#   unity/quest.sh install ros2|ros1        install Builds/PUPPET-<ros>.apk (keeps its settings)
#   unity/quest.sh set-ip <ip> [ros2|ros1] [port]   robot endpoint address, then restart the app
#   unity/quest.sh show [ros2|ros1]         print the app's puppet_settings.json
#   unity/quest.sh edit [ros2|ros1]         edit puppet_settings.json in $EDITOR and push it back
#   unity/quest.sh start|stop [ros2|ros1]
#   unity/quest.sh logs                     follow the app's [PUPPET] and ROS log lines
#
# The ROS flavour defaults to ros2. Both apps can be installed side by side.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BUILDS="$REPO/unity/PUPPET_Unity/Builds"
ADB="${ADB:-$(command -v adb || echo "$HOME/Library/Android/sdk/platform-tools/adb")}"

app_id() {
  case "${1:-ros2}" in
    ros2) echo com.ProjectX.pxspatialversion.ros2 ;;
    ros1) echo com.ProjectX.pxspatialversion.ros1 ;;
    *) echo "unknown flavour '$1' (ros2 or ros1)" >&2; exit 2 ;;
  esac
}

need_device() {
  [ -x "$ADB" ] || { echo "adb not found (set ADB=...)" >&2; exit 1; }
  local n
  n="$("$ADB" devices | awk 'NR>1 && $2=="device"' | wc -l | tr -d ' ')"
  if [ "$n" = 0 ]; then
    echo "No Quest found. Plug it in, put it on, and allow USB debugging in the headset." >&2
    "$ADB" devices >&2
    exit 1
  fi
}

settings_path() { echo "/sdcard/Android/data/$(app_id "$1")/files/puppet_settings.json"; }

pull_settings() { # flavour local_file -> 0 if it existed
  "$ADB" pull "$(settings_path "$1")" "$2" >/dev/null 2>&1
}

push_settings() {
  "$ADB" shell mkdir -p "$(dirname "$(settings_path "$1")")"
  "$ADB" push "$2" "$(settings_path "$1")" >/dev/null
}

restart_if_running() {
  local id; id="$(app_id "$1")"
  if "$ADB" shell pidof "$id" >/dev/null 2>&1; then
    "$ADB" shell am force-stop "$id"
    "$ADB" shell monkey -p "$id" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
    echo "Restarted $id so it reads the new settings."
  else
    echo "The app reads the settings when it starts."
  fi
}

cmd="${1:-}"; shift || true
case "$cmd" in
  install)
    flavour="${1:-ros2}"; apk="$BUILDS/PUPPET-$flavour.apk"
    [ -f "$apk" ] || { echo "Missing $apk. Build it with unity/build_quest.sh $flavour" >&2; exit 1; }
    need_device
    "$ADB" install -r "$apk"
    echo "Installed. In the headset: App Library > Unknown Sources > PUPPET $(echo "$flavour" | tr a-z A-Z)."
    ;;
  set-ip)
    ip="${1:?usage: set-ip <ip> [ros2|ros1] [port]}"; flavour="${2:-ros2}"; port="${3:-}"
    need_device
    tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
    pull_settings "$flavour" "$tmp" || echo '{}' > "$tmp"
    python3 - "$tmp" "$ip" "$port" <<'PY'
import json, sys
path, ip, port = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    s = json.load(open(path))
except Exception:
    s = {}
s.setdefault("ipPresets", ["10.205.3.26", "10.68.0.1"])
s.setdefault("topicRemaps", [])
s.setdefault("showStatus", True)
s["robotIp"] = ip
if port:
    s["robotPort"] = int(port)
s.setdefault("robotPort", 10000)
if ip not in s["ipPresets"]:
    s["ipPresets"].insert(0, ip)
json.dump(s, open(path, "w"), indent=4)
PY
    push_settings "$flavour" "$tmp"
    echo "$(app_id "$flavour"): robot endpoint set to $ip:$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["robotPort"])' "$tmp")"
    restart_if_running "$flavour"
    ;;
  show)
    need_device
    "$ADB" shell cat "$(settings_path "${1:-ros2}")" 2>/dev/null || echo "No settings file yet; start the app once."
    ;;
  edit)
    flavour="${1:-ros2}"; need_device
    tmp="$(mktemp).json"; trap 'rm -f "$tmp"' EXIT
    pull_settings "$flavour" "$tmp" || { echo "No settings file yet; start the app once." >&2; exit 1; }
    "${EDITOR:-nano}" "$tmp"
    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$tmp" || { echo "Not valid JSON; nothing pushed." >&2; exit 1; }
    push_settings "$flavour" "$tmp"
    restart_if_running "$flavour"
    ;;
  start)
    need_device; "$ADB" shell monkey -p "$(app_id "${1:-ros2}")" -c android.intent.category.LAUNCHER 1 >/dev/null ;;
  stop)
    need_device; "$ADB" shell am force-stop "$(app_id "${1:-ros2}")" ;;
  logs)
    need_device
    "$ADB" logcat -v time -s Unity:V | grep --line-buffered -E "PUPPET|ROS|Incompatible|Arm motion|Exception|Error"
    ;;
  *)
    sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
