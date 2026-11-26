# shellcheck shell=bash
# ROS 2 (PAL OS 25.01) versions of ./puppet's commands. Sourced by ./puppet when TIAGo runs
# ROS 2; the ROS 1 functions in ./puppet are left as they are and overridden here.
#
# On ROS 2 everything robot-side runs ON TIAGo: ROS-TCP-Endpoint, the tp controllers, and the
# OptiTrack bridge (NatNet streams from Motive straight to TIAGo). DDS traffic never leaves the
# robot, so PAL's DDS settings (CycloneDDS, unicast, localhost peers) need no change and
# archimedes needs no ROS 2. This machine only orchestrates over SSH.

TIAGO_SETUP="$TIAGO_SETUP_ROS2"

ros_env() { :; }  # nothing ROS-related runs on this machine in ROS 2 mode

probe() {  # probe <args>: run scripts/ros2/probe.py on TIAGo, print its lines; status 1 on any FAIL
  local out rc=0 level msg fix
  out=$(timeout 40 ssh "${SSH_OPTS[@]}" -o BatchMode=yes -o ConnectTimeout=5 "$TIAGO_SSH" \
        "$TIAGO_SETUP && python3 - $*" < "$PUPPET_ROOT/scripts/ros2/probe.py" 2>&1) || rc=$?
  while IFS=$'\t' read -r level msg fix; do
    case "$level" in
      ok)   ok "$msg" ;;
      warn) warn "$msg${fix:+  -> $fix}" ;;
      FAIL) fail "$msg${fix:+  -> $fix}" ;;
      *)    [[ -n "$level" ]] && echo "        $level $msg" ;;
    esac
  done <<< "$out"
  if (( rc != 0 )) && ! grep -q $'^FAIL\t' <<< "$out"; then
    fail "health probe on TIAGo did not run (exit $rc). Is the PUPPET workspace deployed? ./puppet deploy"
  fi
  return $rc
}

topic_live() {  # topic_live <topic> [seconds]
  tiago_batch "timeout ${2:-5} ros2 topic echo --once $1 >/dev/null 2>&1" 2>/dev/null
}

controller_state() {  # prints active / inactive / unconfigured / missing / unknown
  local out
  out=$(tiago_batch "ros2 control list_controllers 2>/dev/null" 2>/dev/null) || { echo unknown; return; }
  # The CLI colours its output even without a terminal: strip the escape codes before parsing.
  sed $'s/\x1b\\[[0-9;]*m//g' <<< "$out" | awk -v n="$1" '$1 == n { print $NF; found=1 } END { if (!found) print "missing" }'
}
running() { [[ "$(controller_state "$1")" == active ]]; }

deployed_version() { tiago_batch "cat ~/puppet_ws/PUPPET_VERSION 2>/dev/null" 2>/dev/null || true; }
local_version() { git -C "$PUPPET_ROOT" describe --always --dirty 2>/dev/null || echo unknown; }

# ---------------------------------------------------------------- processes (tmux windows)
proc() {
  case "$1" in
    mocap)
      tiago -t "exec ros2 launch puppet_bringup mocap.launch.py server_ip:=$MOTIVE_IP client_ip:=$TIAGO_IP \
                base_topic:=$BASE_TOPIC puck_topic:=$PUCK_TOPIC" ;;
    telepresence)
      tiago -t "exec ros2 launch tiago_telepresence_controllers telepresence.launch.py tcp_port:=$TCP_PORT \
                camera:=${CAMERA_TOPIC_ROS2%/compressed} compress_camera:=${COMPRESS_CAMERA:-false} \
                skip_planning:=$([[ "${PLAN_MOTIONS:-true}" == true ]] && echo false || echo true)" ;;
    *) die "unknown process $1" ;;
  esac
}

# ---------------------------------------------------------------- commands
doctor() {
  local bad=0
  step "Preflight (ROS 2, PAL OS 25.01)"
  if command -v tmux >/dev/null; then ok "tmux installed"; else fail "tmux missing: sudo apt install tmux"; bad=1; fi
  if ping -c 1 -W 2 "$TIAGO_IP" >/dev/null 2>&1; then ok "TIAGo $TIAGO_IP reachable"
  else fail "cannot ping TIAGo $TIAGO_IP (robot on? same WiFi?)"; return 1; fi

  drop_stale_ssh
  if tiago_batch true 2>/dev/null; then ok "SSH to $TIAGO_SSH"
  else fail "SSH to $TIAGO_SSH needs a password or fails: ssh-copy-id $TIAGO_SSH"; return 1; fi

  local dv lv; dv=$(deployed_version); lv=$(local_version)
  if [[ -z "$dv" ]]; then fail "PUPPET not deployed on TIAGo: ./puppet deploy"; return 1
  elif [[ "$dv" != "$lv" ]]; then warn "TIAGo runs PUPPET $dv, this checkout is $lv: ./puppet deploy to update"
  else ok "PUPPET $dv deployed on TIAGo"; fi

  if tiago_batch "ping -c 1 -W 2 $MOTIVE_IP >/dev/null" 2>/dev/null; then ok "TIAGo reaches Motive $MOTIVE_IP"
  else fail "TIAGo cannot ping Motive $MOTIVE_IP (gaia on? same network?)"; bad=1; fi

  probe --mode doctor --tcp-port "$TCP_PORT" --camera "$CAMERA_TOPIC_ROS2" --plan-motions "${PLAN_MOTIONS:-true}" || bad=1
  return $bad
}

check() {
  local bad=0
  step "Session health (ROS 2)"
  probe --mode check --tcp-port "$TCP_PORT" --camera "$CAMERA_TOPIC_ROS2" --plan-motions "${PLAN_MOTIONS:-true}" \
    --topic "$BASE_TOPIC" --topic "$PUCK_TOPIC" --topic /odom_mocap --topic /puck_mocap || bad=1
  if port_open "$TCP_IP" "$TCP_PORT"; then ok "endpoint $TCP_IP:$TCP_PORT reachable from this machine (Quest's path)"
  else fail "cannot reach $TCP_IP:$TCP_PORT from here: the Quest will not connect either"; bad=1; fi
  return $bad
}

move_to_start_and_teleop() {
  step "Moving to '$START_MOTION' (PlayMotion2)"
  confirm "TIAGo moves to '$START_MOTION' now. Operator beside the robot, area clear, E-stop in reach?" \
    || die "aborted before any motion"
  local skip=(); [[ "${PLAN_MOTIONS:-true}" == true ]] || skip=(--skip-planning)
  tiago -t "ros2 run tiago_telepresence_controllers play_motion.py run $START_MOTION ${skip[*]+${skip[*]}}" \
    || die "start motion failed (above). Nothing else was started."
  confirm "Did the arm reach '$START_MOTION' cleanly, with no collision?" || die "stopped; telepresence not started"

  step "Starting telepresence (window: telepresence)"
  start_window telepresence
  wait_for 120 "tp controllers active" running arm_tp_controller || die "telepresence controllers not active; ./puppet attach"
  wait_for 30 "ROS-TCP endpoint $TCP_IP:$TCP_PORT" endpoint_up || true
}

up() {
  if have_session; then die "session '$SESSION' already exists: ./puppet attach, or ./puppet down first"; fi
  doctor || die "preflight failed; fix the FAIL lines above"
  echo
  confirm "Physical preflight done (ReadMe Section 5): E-stop in reach, TIAGo approved for motion, Motive running on gaia?" \
    || die "aborted"

  tm new-session -d -s "$SESSION" -n control "'$PUPPET_ROOT/puppet' shell"
  tm set-window-option -g remain-on-exit on >/dev/null

  step "Starting OptiTrack bridge + pose-to-odom on TIAGo (window: mocap)"
  start_window mocap
  wait_for 30 "$BASE_TOPIC" topic_live "$BASE_TOPIC" || warn "base rigid body not streaming yet; check Motive on gaia"
  wait_for 15 "/odom_mocap" topic_live /odom_mocap || true

  move_to_start_and_teleop

  echo
  check || warn "some checks failed (above); fix them before teleoperating"
  echo
  echo "${B}Ready.${N} Quest: open PUPPET (ROS 2 build). Check heading and puck in Unity before moving the arm."
  echo "Logs: ./puppet attach (windows: mocap, telepresence).  Live status: ./puppet status.  Stop: ./puppet down"
  if [[ "${DETACH:-false}" != true ]]; then tm attach -t "$SESSION"; fi
}

reset_arm() {
  have_session || die "no session running (./puppet up)"
  step "Stopping telepresence (PAL's controllers come back)"
  interrupt_window telepresence 20 || die "telepresence did not stop; ./puppet attach"
  move_to_start_and_teleop
  check || true
}

deploy() {
  if have_session; then die "a session is running: ./puppet down first (deploy replaces the running code)"; fi
  step "Building ros2_ws in PAL's 25.01 image"
  "$PUPPET_ROOT/scripts/ros2/build.sh" || die "build failed"
  local v; v=$(local_version)
  step "Copying the install space to $TIAGO_SSH:~/puppet_ws (PUPPET $v)"
  # tar over SSH: no rsync needed on the robot. The old install is replaced as a whole.
  tar -C "$PUPPET_ROOT/ros2_ws" -czf - install \
    | ssh "${SSH_OPTS[@]}" "$TIAGO_SSH" "set -e; mkdir -p ~/puppet_ws; rm -rf ~/puppet_ws/install.new; \
        mkdir ~/puppet_ws/install.new; tar -C ~/puppet_ws/install.new --strip-components=1 -xzf -; \
        rm -rf ~/puppet_ws/install; mv ~/puppet_ws/install.new ~/puppet_ws/install; echo '$v' > ~/puppet_ws/PUPPET_VERSION" \
    || die "copy to TIAGo failed"
  tiago_batch "ros2 pkg prefix tiago_telepresence_controllers >/dev/null" || die "deployed, but TIAGo cannot find the packages"
  ok "PUPPET $v deployed. Next: ./puppet doctor"
}

endpoint_up() { tiago_batch "ss -Hltn 'sport = :$TCP_PORT' | grep -q ." 2>/dev/null; }

shell_cmd() {  # ./puppet shell on ROS 2: a shell ON TIAGo with ROS 2 and PUPPET loaded
  ssh "${SSH_OPTS[@]}" -t "$TIAGO_SSH" \
    "exec bash --rcfile <(printf '%s\n' '[ -f ~/.bashrc ] && source ~/.bashrc' '$TIAGO_SETUP' 'echo \"PUPPET ROS 2 shell on TIAGo (ros2 topic list, ros2 control list_controllers)\"') -i"
}
