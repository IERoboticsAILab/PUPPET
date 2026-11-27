#!/usr/bin/env bash
# End-to-end test of ./puppet in ROS 2 mode, without a robot: one container plays TIAGo (sshd,
# user pal, the mock robot from mock_test.sh, PUPPET deployed in ~/puppet_ws) and runs ./puppet
# against it over SSH, exactly as archimedes would. Motive is absent, so the mocap checks are
# expected to FAIL visibly; everything else must pass.
#
#   scripts/ros2/runner_test.sh   (after scripts/ros2/build.sh)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ -f "$ROOT/ros2_ws/install/setup.bash" ]] || "$ROOT/scripts/ros2/build.sh"

docker run --rm --platform linux/amd64 --entrypoint bash -v "$ROOT:/puppet:ro" \
  development-tiago-38:alum-25.01 -c '
set -eo pipefail
trap '"'"'echo "runner_test: failed at line $LINENO: $BASH_COMMAND"'"'"' ERR
say() { echo; echo "######## $*"; }
apt-get install -y -qq tmux >/dev/null 2>&1 || { apt-get update -qq >/dev/null && apt-get install -y -qq tmux >/dev/null; }

# ---- "TIAGo": user pal, sshd, PUPPET deployed the way ./puppet deploy does it
useradd -m -s /bin/bash pal && usermod -p "*" pal  # unlocked, key-only (sshd refuses locked accounts)
mkdir -p /run/sshd /root/.ssh && ssh-keygen -q -t ed25519 -N "" -f /root/.ssh/id_ed25519
install -d -o pal -m 700 /home/pal/.ssh && install -o pal -m 600 /root/.ssh/id_ed25519.pub /home/pal/.ssh/authorized_keys
/usr/sbin/sshd
printf "Host localhost\n  StrictHostKeyChecking accept-new\n" > /root/.ssh/config
mkdir -p /home/pal/puppet_ws && cp -r /puppet/ros2_ws/install /home/pal/puppet_ws/
# The worktree'"'"'s .git is not visible in here, so ./puppet reports "unknown" for this checkout.
echo unknown > /home/pal/puppet_ws/PUPPET_VERSION
chown -R pal /home/pal/puppet_ws

# ---- the mock robot, as pal (PAL boots these on the real one)
cat > /tmp/robot.sh <<"EOF"
source /opt/pal/alum/setup.bash && source ~/puppet_ws/install/setup.bash
T=/puppet/ros2_ws/src/tiago_telepresence_controllers/test/mock_robot
python3 $T/make_mock_urdf.py /tmp/tiago.urdf
ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(cat /tmp/tiago.urdf)" > /tmp/rsp.log 2>&1 &
ros2 run controller_manager ros2_control_node --ros-args --params-file $T/mock_controllers.yaml -r ~/robot_description:=/robot_description > /tmp/cm.log 2>&1 &
ros2 run controller_manager spawner joint_state_broadcaster arm_controller head_controller torso_controller gripper_controller > /tmp/sp.log 2>&1
ros2 run play_motion2 play_motion2_node --ros-args --params-file /opt/pal/alum/share/tiago_bringup/config/motions/tiago_motions_general.yaml \
  --params-file $T/mock_motions.yaml --params-file $T/mock_motion_planner.yaml \
  -r /play_motion2_executor/robot_description:=/robot_description > /tmp/pm2.log 2>&1 &
ros2 topic pub -r 2 /power/is_emergency std_msgs/msg/Bool "{data: false}" > /dev/null 2>&1 &
sleep 5; touch /tmp/robot_ready
sleep infinity
EOF
su pal -c "bash /tmp/robot.sh" &
for i in $(seq 180); do [ -f /tmp/robot_ready ] && break; sleep 1; done
[ -f /tmp/robot_ready ] || { echo "mock robot did not start"; tail -n 20 /tmp/*.log; exit 1; }

# ---- ./puppet against it, as archimedes would
sed -e "s/^TIAGO_SSH=.*/TIAGO_SSH=pal@localhost/" -e "s/^TIAGO_IP=.*/TIAGO_IP=127.0.0.1/" \
    -e "s/^TCP_IP=.*/TCP_IP=127.0.0.1/" -e "s/^MOTIVE_IP=.*/MOTIVE_IP=127.0.0.1/" \
    -e "s/^ROS_MASTER_URI=.*/ROS_MASTER_URI=http:\/\/127.0.0.1:11311/" \
    -e "s/^PLAN_MOTIONS=.*/PLAN_MOTIONS=false/" /puppet/config/puppet.env > /tmp/puppet.env  # mock has no MoveIt
export PUPPET_CONFIG=/tmp/puppet.env
P=/puppet/puppet
say "./puppet version";            $P version
say "./puppet doctor";             $P doctor; echo "doctor exit $?"
say "./puppet up --yes --detach";  $P up --yes --detach || echo "up exit $?"
say "./puppet check";              $P check || echo "check exit $? (mocap FAILs expected: no Motive)"
say "./puppet reset-arm --yes";    $P reset-arm --yes || echo "reset-arm exit $?"
say "./puppet down";               $P down
sleep 5
say "after down: PAL controllers must own the joints again"
su pal -c "source /opt/pal/alum/setup.bash && ros2 control list_controllers"
'
