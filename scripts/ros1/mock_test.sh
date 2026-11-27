#!/usr/bin/env bash
# Offline rehearsal of the ROS 1 demo: three containers on a private network play the lab.
#
#   tiago       (.26)  Noetic, sshd, user pal, the ROS master, PAL's controller names on fake
#                      hardware, a mock PlayMotion with offer/home, the e-stop topic. The real
#                      telepresence controllers, tiago_real.launch and ROS-TCP-Endpoint run on it.
#   archimedes  (.122) runs ./puppet from this checkout (read-only), with a mock NatNet bridge.
#   quest       (.57)  scripts/ros1/fake_unity.py, speaking ROS-TCP like the pxspatial app.
#
#   scripts/ros1/mock_test.sh          the whole scenario; exit 0 = all checks passed
#   KEEP=1 scripts/ros1/mock_test.sh   leave the containers running afterwards
#
# Needs Docker only. Nothing here talks to the real robot.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMG=puppet-ros1-mock NET=puppet-ros1-mock SUB=172.31.38 VOL=puppet-ros1-mock-ws
T=puppet-mock-tiago A=puppet-mock-archimedes Q=puppet-mock-quest
KEYS=$(mktemp -d)
FAILS=0

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
pass() { echo "  ok    $*"; }
bad()  { echo "  FAIL  $*"; FAILS=$((FAILS + 1)); }
cleanup() {
  if [[ "${KEEP:-}" != 1 ]]; then docker rm -f $T $A $Q >/dev/null 2>&1 || true; docker network rm $NET >/dev/null 2>&1 || true; fi
  rm -rf "$KEYS"
}
trap cleanup EXIT

on_tiago() { docker exec $T su pal -c "source /opt/pal/gallium/setup.bash && source /ws/devel/setup.bash && $1"; }
on_arch()  { docker exec -e TERM=dumb $A bash -c "source /opt/ros/noetic/setup.bash && source /ws/devel/setup.bash && export ROS_MASTER_URI=http://$SUB.26:11311 ROS_IP=$SUB.122 PUPPET_CONFIG=/root/puppet.env && cd /puppet && $1"; }
puppet()   { on_arch "./puppet $*"; }
quest()    { docker exec $Q bash -c "source /opt/ros/noetic/setup.bash && source /ws/devel/setup.bash && python3 /puppet/scripts/ros1/fake_unity.py $SUB.26:10000 $*"; }
check()    { on_arch "python3 /puppet/scripts/ros1/mock/check.py $*"; }
DUMPED=""
expect()   { # expect <description> <pattern> <output>; a failing output is printed once
  if grep -qE -- "$2" <<<"$3"; then pass "$1"; return; fi
  bad "$1 (no '$2' in output)"
  if [[ "$DUMPED" != "$3" ]]; then echo "$3" | sed 's/^/        | /'; DUMPED=$3; fi; }

step "Image and network"
docker build -q -t $IMG "$ROOT/scripts/ros1/mock" >/dev/null
docker rm -f $T $A $Q >/dev/null 2>&1 || true
docker network rm $NET >/dev/null 2>&1 || true
docker network create --subnet $SUB.0/24 $NET >/dev/null
docker volume create $VOL >/dev/null
ssh-keygen -q -t ed25519 -N '' -f "$KEYS/id"
pass "image $IMG, network $SUB.0/24"

step "TIAGo boots (build of the workspace the first time: a few minutes)"
docker run -d --name $T --hostname tiago-38c --network $NET --ip $SUB.26 \
  -v "$ROOT:/puppet:ro" -v $VOL:/ws -v "$KEYS:/keys:ro" $IMG bash -c '
set -e
mkdir -p /ws/src && cd /ws/src && rm -f /ws/.built
for p in tiago_telepresence_controllers puppet_bringup optitrack_ros_communication; do ln -sfn /puppet/ros_ws/src/$p .; done
for p in puppet_mock play_motion natnet_ros_cpp; do ln -sfn /puppet/scripts/ros1/mock/$p .; done
ln -sfn /deps/ROS-TCP-Endpoint .; ln -sfn /deps/play_motion/play_motion_msgs .
source /opt/ros/noetic/setup.bash && cd /ws
catkin_make -DCATKIN_ENABLE_TESTING=OFF > /ws/build.log 2>&1 || { echo BUILD FAILED; tail -40 /ws/build.log; exit 1; }
chmod -R a+rwX /ws && touch /ws/.built
install -d -o pal -m 700 /home/pal/.ssh && install -o pal -m 600 /keys/id.pub /home/pal/.ssh/authorized_keys
echo "export ROS_IP=$(hostname -I | cut -d" " -f1)" >> /opt/pal/gallium/setup.bash
/usr/sbin/sshd
su pal -c "export PYTHONUNBUFFERED=1 && source /opt/pal/gallium/setup.bash && source /ws/devel/setup.bash && (roscore > /tmp/roscore.log 2>&1 &) && sleep 4 && (roslaunch puppet_mock tiago.launch > /tmp/tiago.log 2>&1 &)"
sleep infinity' >/dev/null
for _ in $(seq 600); do
  docker exec $T test -e /ws/.built 2>/dev/null && break
  if [[ "$(docker inspect -f '{{.State.Running}}' $T)" != true ]]; then docker logs $T | tail -40; exit 1; fi
  sleep 1
done
for c in $A $Q; do
  ip=$SUB.122; [[ $c == "$Q" ]] && ip=$SUB.57
  docker run -d --name $c --hostname "${c#puppet-mock-}" --network $NET --ip $ip \
    -v "$ROOT:/puppet:ro" -v $VOL:/ws -v "$KEYS:/keys:ro" $IMG sleep infinity >/dev/null
done
docker exec $A bash -c "install -d -m 700 /root/.ssh && install -m 600 /keys/id /root/.ssh/id_ed25519 &&
  printf 'Host *\n  StrictHostKeyChecking accept-new\n' > /root/.ssh/config &&
  printf '%s\n' 'source /puppet/config/puppet.env' 'ROS_MASTER_URI=http://$SUB.26:11311' 'ROS_IP=$SUB.122' \
    'MOTIVE_IP=$SUB.26' 'TIAGO_SSH=pal@$SUB.26' 'TCP_IP=$SUB.26' 'TIAGO_WS_SETUP=/ws/devel/setup.bash' > /root/puppet.env"
end=$((SECONDS + 180))
until on_tiago "grep -q 'fake play_motion ready' /tmp/tiago.log" 2>/dev/null && check owner pal >/dev/null 2>&1; do
  if (( SECONDS > end )); then bad "mock TIAGo did not come up"; on_tiago "tail -30 /tmp/tiago.log"; exit 1; fi
  sleep 2
done
pass "TIAGo up: PAL controllers running, /play_motion ready"

step "./puppet doctor"
out=$(puppet doctor 2>&1) && pass "doctor exit 0" || bad "doctor exit $?"
expect "e-stop read from TIAGo" "ok .*E-stop released" "$out"

step "./puppet up --yes --detach"
out=$(puppet up --yes --detach 2>&1) && pass "up exit 0" || { bad "up failed"; echo "$out" | tail -30 | sed 's/^/        | /'; }
expect "extend played" "Moving to 'extend'" "$out"
expect "tp controllers running" "ok .*arm_tp_controller running" "$out"
expect "B-button node restarted from this checkout" "ok .*/tp_arm_motion/command" "$out"
check owner tp || FAILS=$((FAILS + 1))
check at extend || FAILS=$((FAILS + 1))

step "./puppet status before the headset connects"
out=$(puppet status --once 2>&1) && pass "status: nothing FAILs" || bad "status reports a FAIL"
for row in "ok .*TIAGo .*SSH ok" "ok .*E-stop .*released" "ok .*Joint states" "ok .*Controllers .*headset drives" \
           "ok .*ROS-TCP endpoint .*listening" "wait.*Quest .*not connected" "ok .*OptiTrack base .*Hz" \
           "ok .*OptiTrack puck .*Hz" "ok .*/odom_mocap" "ok .*B button .*ready" "ok .*Processes .*mocap"; do
  expect "status row: $row" "$row" "$out"
done

step "Headset connects"
quest --hold 25 &
sleep 5
out=$(puppet status --once 2>&1) || true
expect "status shows the Quest" "ok .*Quest .*connected from $SUB.57" "$out"
out=$(puppet check 2>&1) || true
expect "check shows the Quest" "ok .*Quest connected from $SUB.57" "$out"
wait

step "B button: offer (arm follows only after this, in the app)"
out=$(quest --arm-motion offer 2>&1) || true; echo "$out"
expect "offer succeeded" "ok .*ArmMotion 'offer': success=True" "$out"
check at offer || FAILS=$((FAILS + 1))
check owner tp || FAILS=$((FAILS + 1))

step "Arm follows the hand from offer: how each headset direction maps"
for d in "0.05 0 0" "0 0.05 0" "0 0 0.05"; do
  check ee-save /tmp/ee.json
  quest --arm-move $d --seconds 2 >/dev/null
  sleep 1
  check ee-moved /tmp/ee.json $d || FAILS=$((FAILS + 1))
done

step "WiFi hiccup while following: a 0.6 s pause in the stream (informational)"
check ee-save /tmp/ee.json
quest --arm-move 0.05 0 0 --seconds 2 --gap 0.6
sleep 1
check ee-moved /tmp/ee.json 0.05 0 0 --expect-jump

step "B button: home (about 13 s, longer than the old 10 s wait)"
out=$(quest --arm-motion home 2>&1) || true; echo "$out"
expect "home succeeded" "ok .*ArmMotion 'home': success=True" "$out"
check at home || FAILS=$((FAILS + 1))
check owner tp || FAILS=$((FAILS + 1))

step "A motion longer than 30 s is reported as failed, not as done"
on_tiago "rosparam set /play_motion/slowdown 5"
out=$(quest --arm-motion offer 2>&1) || true; echo "$out"
expect "cut-off motion reported as failed" "FAIL .*success=False .*did not finish within 30 s" "$out"
check owner tp || FAILS=$((FAILS + 1))
on_tiago "rosparam set /play_motion/slowdown 1"

step "Failures show up in the status view with a fix"
on_arch "rosnode kill /natnet_ros >/dev/null"
sleep 3
out=$(puppet status --once 2>&1) && bad "status should FAIL with OptiTrack silent" || pass "status exit 1"
expect "OptiTrack silent, with a hint" "FAIL.*OptiTrack base .*silent" "$out"
on_tiago "rosnode kill /estop >/dev/null; (rostopic pub -r 1 /power_status/is_emergency std_msgs/Bool True __name:=estop_pressed >/dev/null 2>&1 &)"
sleep 4
out=$(puppet status --once 2>&1) || true
expect "e-stop pressed, with the recovery steps" "FAIL.*E-stop .*PRESSED" "$out"
expect "e-stop hint" "blinking green button" "$out"
on_tiago "rosnode kill /estop_pressed >/dev/null; (rostopic pub -r 1 /power_status/is_emergency std_msgs/Bool False __name:=estop >/dev/null 2>&1 &)"
on_arch "tmux -L puppet send-keys -t puppet:mocap C-c"
sleep 4
out=$(puppet status --once 2>&1) || true
expect "exited process named, with its last log line" "FAIL.*Process mocap .*exited" "$out"
out=$(puppet logs mocap 2>&1) || true
expect "./puppet logs shows the window" "mocap .*exited" "$out"

step "./puppet reset-arm --yes"
out=$(puppet reset-arm --yes 2>&1) && pass "reset-arm exit 0" || pass "reset-arm ran (check FAILs expected: mocap stopped)"
expect "back to extend, telepresence again" "ok .*arm_tp_controller running" "$out"
check at extend || FAILS=$((FAILS + 1))

step "./puppet down"
out=$(puppet down 2>&1) && pass "down exit 0" || bad "down exit $?"
sleep 2
check owner pal || FAILS=$((FAILS + 1))

echo
if (( FAILS == 0 )); then echo "ALL ROS 1 MOCK CHECKS PASSED"; else echo "$FAILS CHECK(S) FAILED"; exit 1; fi
