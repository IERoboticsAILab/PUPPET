#!/usr/bin/env bash
# Rehearse a PUPPET session on a simulated TIAGo 38, inside PAL's 25.01 image. No robot needed.
#
#   scripts/ros2/mock_test.sh        (runs scripts/ros2/build.sh first)
#
# The mock robot is PAL's own TIAGo 38 URDF with mock hardware (commands are followed exactly),
# a controller_manager with PAL's controller names, and PAL's play_motion2. On top of it, the
# real PUPPET launch file (endpoint, tp controllers, switcher, arm_motion), then a fake headset
# (scripts/ros2/fake_unity.py) that talks to the endpoint over TCP like the Quest app does.
# It checks, in order:
#   1. PAL-like controllers own the joints; ours are loaded inactive
#   2. the switcher hands the joints to the tp controllers
#   3. Unity's view: /joint_states arrives through the endpoint
#   4. torso, gripper, head and arm commands from the headset move the joints
#   5. ArmMotion 'extend' through the endpoint: PlayMotion2 plays it, joints come back to us
#   6. the keyboard condition (keyboard_teleop) moves the hand by the keyed steps
#   7. Ctrl+C on the launch file gives the joints back to PAL's controllers

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
"$ROOT/scripts/ros2/build.sh"

docker run --rm --platform linux/amd64 --entrypoint bash \
  -v "$ROOT/ros2_ws:/home/pal/puppet_ws" -v "$ROOT/scripts:/puppet_scripts:ro" -w /home/pal/puppet_ws \
  -e ROS_LOCALHOST_ONLY=1 -e ROS_DOMAIN_ID=77 \
  development-tiago-38:alum-25.01 -c '
set -eo pipefail
source /opt/pal/alum/setup.bash && source install/setup.bash
T=src/tiago_telepresence_controllers/test/mock_robot
LOG=/tmp/mock; mkdir -p $LOG
step() { echo; echo "==> $*"; }
cleanup() { kill $(jobs -p) 2>/dev/null || true; }
trap cleanup EXIT
fail_logs() { echo "--- last log lines:"; tail -n 15 $LOG/*.log; exit 1; }

step "Mock TIAGo 38 (PAL URDF, mock hardware, PAL controller names, play_motion2)"
python3 $T/make_mock_urdf.py /tmp/tiago.urdf
ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(cat /tmp/tiago.urdf)" > $LOG/rsp.log 2>&1 &
ros2 run controller_manager ros2_control_node --ros-args --params-file $T/mock_controllers.yaml \
  -r ~/robot_description:=/robot_description > $LOG/cm.log 2>&1 &
ros2 run controller_manager spawner joint_state_broadcaster arm_controller head_controller torso_controller gripper_controller \
  --controller-manager-timeout 60 > $LOG/spawn_pal.log 2>&1 || fail_logs
ros2 run play_motion2 play_motion2_node --ros-args --params-file $T/mock_motions.yaml \
  --params-file $T/mock_motion_planner.yaml \
  -r /play_motion2_executor/robot_description:=/robot_description > $LOG/pm2.log 2>&1 &
python3 $T/check.py owner pal 30 || fail_logs
python3 /puppet_scripts/ros2/probe.py --mode doctor --seconds 2 --plan-motions false || fail_logs

step "PUPPET telepresence launch (the real one)"
# Job control on, so the background launch gets Ctrl+C (SIGINT) like in a terminal.
set -m
ros2 launch tiago_telepresence_controllers telepresence.launch.py skip_planning:=true > $LOG/puppet.log 2>&1 &
LAUNCH=$!
set +m
python3 $T/check.py owner tp 90 || fail_logs

step "Fake headset over TCP: Unity view"
sleep 3
python3 /puppet_scripts/ros2/fake_unity.py 127.0.0.1:10000 --listen 3 || fail_logs

step "./puppet check probe (read-only) during the session"
python3 /puppet_scripts/ros2/probe.py --mode check --seconds 2 --plan-motions false || fail_logs

step "Fake headset: torso, gripper, head and arm commands"
python3 $T/check.py snapshot /tmp/before.json
python3 /puppet_scripts/ros2/fake_unity.py 127.0.0.1:10000 --drive-test || fail_logs
python3 $T/check.py snapshot /tmp/after.json
python3 $T/check.py moved /tmp/before.json /tmp/after.json || fail_logs

step "Fake headset: extend-arm button (ArmMotion extend via PlayMotion2)"
python3 /puppet_scripts/ros2/fake_unity.py 127.0.0.1:10000 --arm-motion extend || fail_logs
python3 $T/check.py at-motion extend || fail_logs
python3 $T/check.py owner tp 20 || fail_logs

step "Keyboard condition (keyboard_teleop, ROS 2): i i i w = 9 mm forward, 3 mm up"
# From a pose inside every joint limit (extend has arm_3 past its limit, which bends some directions).
python3 /puppet_scripts/ros2/fake_unity.py 127.0.0.1:10000 --arm-motion mid || fail_logs
python3 $T/check.py ee-snapshot /tmp/ee0.json
ros2 run keyboard_teleop keyboard_arm_teleop.py --keys iiiw --yes > $LOG/keyboard.log 2>&1 || fail_logs
python3 $T/check.py ee-snapshot /tmp/ee1.json
python3 $T/check.py ee-moved /tmp/ee0.json /tmp/ee1.json 0.009 0 0.003 || fail_logs
ros2 run keyboard_teleop keyboard_arm_teleop.py --keys jjl --yes >> $LOG/keyboard.log 2>&1 || fail_logs
python3 $T/check.py ee-snapshot /tmp/ee2.json
python3 $T/check.py ee-moved /tmp/ee1.json /tmp/ee2.json 0 0.003 0 || fail_logs

step "Ctrl+C on the launch file gives the joints back"
kill -INT $LAUNCH
for i in $(seq 30); do kill -0 $LAUNCH 2>/dev/null || break; sleep 1; done
python3 $T/check.py owner pal 30 || fail_logs

echo; echo "ALL MOCK CHECKS PASSED"
'
