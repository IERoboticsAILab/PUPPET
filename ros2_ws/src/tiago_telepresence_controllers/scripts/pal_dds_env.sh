# shellcheck shell=bash
# Source after /opt/pal/alum/setup.bash: use exactly the DDS settings of PAL's running ROS 2
# processes (RMW_IMPLEMENTATION, ROS_DOMAIN_ID, CYCLONEDDS_URI, ROS_LOCALHOST_ONLY), read from
# the controller_manager's environment. A login shell over SSH may not get the same values as
# PAL's services, and then PUPPET's nodes would not see the robot at all.
# Sets PUPPET_DDS_SOURCE to where the values came from (shown by ./puppet doctor).
# Match on the executable (argv[0]), never on arguments: a shell whose command line merely
# mentions these names must not count.
__puppet_pid=
for __pat in '^[^ ]*control_node( |$)' '^[^ ]*/robot_state_publisher( |$)' '^[^ ]*/play_motion2_node( |$)'; do
  for __p in $(pgrep -f "$__pat" 2>/dev/null); do
    if [ -r "/proc/$__p/environ" ]; then __puppet_pid=$__p; break 2; fi
  done
done
if [ -n "$__puppet_pid" ]; then
  __puppet_env=$(tr '\0' '\n' < "/proc/$__puppet_pid/environ")
  for __v in RMW_IMPLEMENTATION ROS_DOMAIN_ID CYCLONEDDS_URI ROS_LOCALHOST_ONLY FASTRTPS_DEFAULT_PROFILES_FILE; do
    __line=$(printf '%s\n' "$__puppet_env" | grep -m1 "^$__v=" || true)
    if [ -n "$__line" ]; then export "$__line"; else unset "$__v"; fi
  done
  export PUPPET_DDS_SOURCE="$(tr '\0' ' ' < "/proc/$__puppet_pid/cmdline" | cut -c1-60) (pid $__puppet_pid)"
else
  export PUPPET_DDS_SOURCE="login environment (no readable PAL ROS 2 process)"
fi
unset __puppet_pid __puppet_env __v __line __pat __p
