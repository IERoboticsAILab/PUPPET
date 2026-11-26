#!/usr/bin/env bash
# A simulated TIAGo 38 on PAL OS 25.01, with PUPPET's ROS 2 session running on it, and
# ROS-TCP-Endpoint published on THIS machine's port 10000. Connect the Unity editor (ROS 2 build)
# or a Quest on the same WiFi to <this machine's IP>:10000 to test without the robot.
#
#   scripts/ros2/mock_robot.sh [PORT]     Ctrl+C stops everything
#
# What it runs: PAL's TIAGo 38 URDF with mock hardware (joints follow commands exactly),
# joint_state_broadcaster (/joint_states), PAL-named trajectory controllers, PAL's play_motion2
# with PAL's general motions (offer, home, ...), then PUPPET's telepresence launch: the endpoint,
# the four tp controllers (active), the switcher and /tp_arm_motion/command.
# Not simulated: camera, base, OptiTrack, audio, e-stop. The headset shows them as "no data".

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORT=${1:-10000}
"$ROOT/scripts/ros2/build.sh" >/dev/null || { echo "build failed: scripts/ros2/build.sh"; exit 1; }

echo "Mock TIAGo starting (about a minute under emulation). Connect Unity / the Quest to one of:"
if command -v ipconfig >/dev/null 2>&1; then  # macOS
  for i in en0 en1; do ip=$(ipconfig getifaddr "$i" 2>/dev/null || true); [[ -n "$ip" ]] && echo "    $ip:$PORT  ($i)"; done
else
  hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | sed "s/\$/:$PORT/; s/^/    /"
fi
echo "    127.0.0.1:$PORT  (Unity editor on this machine)"
echo "Wait for 'MOCK TIAGO READY'. Ctrl+C to stop."

tty=(-i); [[ -t 0 ]] && tty=(-it)  # -t only from a terminal (so it also runs from scripts)
exec docker run --rm "${tty[@]}" --platform linux/amd64 --entrypoint bash -p "$PORT:10000" \
  -v "$ROOT/ros2_ws:/home/pal/puppet_ws" -w /home/pal/puppet_ws -e ROS_LOCALHOST_ONLY=1 \
  development-tiago-38:alum-25.01 -c '
source /opt/pal/alum/setup.bash && source install/setup.bash
T=src/tiago_telepresence_controllers/test/mock_robot; L=/tmp/mock; mkdir -p $L
trap "kill \$(jobs -p) 2>/dev/null; exit 0" INT TERM
python3 $T/make_mock_urdf.py /tmp/tiago.urdf
ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(cat /tmp/tiago.urdf)" > $L/rsp.log 2>&1 &
ros2 run controller_manager ros2_control_node --ros-args --params-file $T/mock_controllers.yaml \
  -r ~/robot_description:=/robot_description > $L/cm.log 2>&1 &
ros2 run controller_manager spawner joint_state_broadcaster arm_controller head_controller torso_controller gripper_controller \
  --controller-manager-timeout 60 > $L/spawn.log 2>&1
ros2 run play_motion2 play_motion2_node --ros-args \
  --params-file /opt/pal/alum/share/tiago_bringup/config/motions/tiago_motions_general.yaml \
  --params-file $T/mock_motions.yaml --params-file $T/mock_motion_planner.yaml \
  -r /play_motion2_executor/robot_description:=/robot_description > $L/pm2.log 2>&1 &
ros2 launch tiago_telepresence_controllers telepresence.launch.py skip_planning:=true 2>&1 | \
  sed -u "/telepresence controllers active/ s/\$/\n\n========== MOCK TIAGO READY (endpoint on port 10000) ==========\n/"
'
