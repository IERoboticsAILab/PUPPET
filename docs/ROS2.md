# PUPPET on ROS 2 (TIAGo with PAL OS 25.01)

PUPPET runs on both TIAGo operating systems with the same commands:

| TIAGo runs | ROS | Robot-side code | Started by |
|---|---|---|---|
| PAL OS 25.01 (alum) | ROS 2 Humble | `ros2_ws/` | `./puppet up` |
| Gallium (rollback) | ROS 1 Noetic | `ros_ws/` | `./puppet up` |

`./puppet` asks TIAGo which one it runs (`PUPPET_ROS=auto` in `config/puppet.env`). `./puppet version`
prints the answer.

## What runs where on ROS 2

```
Quest (PUPPET-ros2.apk) --TCP 10000--> TIAGo: ROS-TCP-Endpoint, tp controllers, arm_motion,
                                              OptiTrack bridge, pose-to-odom
Motive (gaia) --NatNet--------------> TIAGo
archimedes (or any Linux PC) --SSH--> TIAGo: ./puppet starts and checks everything
```

Everything robot-side runs on TIAGo. DDS traffic never leaves the robot, so PAL's DDS settings
need no change, and archimedes needs no ROS 2. On Gallium, the OptiTrack bridge still runs on
archimedes, as before.

## Setup (once per machine)

**Build machine** (any Linux amd64 or Mac with Docker; this builds exactly what TIAGo runs):

1. Install Docker, and keep PAL's delivery folder (`uni-ie-build-docker.sh` with its keys) at
   `~/Downloads/uni-ie/`, or set `PAL_DOCKER_SCRIPT`.
2. `./puppet deploy` builds `ros2_ws` in PAL's tiago-38 image and copies it to TIAGo's
   `~/puppet_ws`. The first build fetches PAL's image (10–30 min); later builds take about a minute.

**Operator machine** (archimedes): `tmux`, `python3`, and passwordless SSH to TIAGo
(`ssh-copy-id pal@tiago-38c`). Nothing ROS-related.

**Quest:** install `PUPPET-ros2.apk` (see `docs/QUEST_INSTALL.md`).

Run `./puppet deploy` again whenever `ros2_ws` changes. `./puppet doctor` warns when TIAGo runs an
older version than your checkout.

## A session

```
./puppet doctor     # preflight: network, SSH, deployed version, e-stop, controllers, DDS, PlayMotion2
./puppet up         # mocap, start pose (asks first), telepresence; then ./puppet check
./puppet status     # live health view
./puppet reset-arm  # back to the start pose, telepresence again
./puppet down       # stops everything; PAL's controllers get the joints back
```

**Keyboard condition** (study baseline, instead of the headset): with telepresence running and the
headset's arm control off, run `ros2 run keyboard_teleop keyboard_arm_teleop.py` in the control
window. The keys are the same as on Gallium (ReadMe 7.8). It drives the same `arm_tp_controller`
as the headset, with no MoveIt: 3 mm per key at 1 cm/s, and `x` makes the arm hold.

`./puppet attach` shows the logs (tmux windows `mocap`, `telepresence`, `control`). On ROS 2 the
`control` window is a shell on TIAGo with ROS 2 loaded.

## Settings (`config/puppet.env`, overrides in `config/puppet.local.env`)

| Setting | Default | Meaning |
|---|---|---|
| `PUPPET_ROS` | `auto` | `1` or `2` to skip detection |
| `TIAGO_IP` | `10.205.3.26` | TIAGo's address. Motive streams to it. |
| `START_MOTION` | `extend` | start pose, from `ros2_ws/.../config/telepresence_motions.yaml` |
| `PLAN_MOTIONS` | `true` | PlayMotion2 plans the approach with MoveIt. Set `false` if `doctor` reports no `move_group`. |
| `CAMERA_TOPIC_ROS2` | `/head_front_camera/rgb/image_raw/compressed` | what the headset shows |
| `COMPRESS_CAMERA` | `false` | `true` if `doctor` reports the compressed camera topic missing |
| `BASE_TOPIC`, `PUCK_TOPIC` | `/natnet_ros/<Motive name>/pose` | rigid bodies for `/odom_mocap` and `/puck_mocap` |

## When something fails

Every `FAIL` line says what to do. The common ones:

| Message | Cause and fix |
|---|---|
| `PUPPET not deployed on TIAGo` | `./puppet deploy` |
| `E-stop pressed` | Twist the red button up, then press the blinking green button. |
| `PAL controllers not active` | After boot or an e-stop. Wait, or reboot TIAGo. |
| `tp controllers: ... inactive` | PAL restarts its own controllers after an e-stop. Run `./puppet reset-arm`. |
| `MoveIt move_group not running, but PLAN_MOTIONS=true` | Start PAL's motion planner, or set `PLAN_MOTIONS=false`. |
| `/natnet_ros/... silent` | Motive streaming off, the rigid body not tracked, or a different name. `ros2 topic list \| grep natnet_ros` in the control window shows the real names. |
| `cannot reach TIAGo:10000 from here` | The Quest can't either: wrong WiFi, or the endpoint is down (telepresence window). |
| `ROS ..., from login environment` | PUPPET could not read PAL's DDS settings, so its nodes may not see the robot. Check that PAL's services run as user `pal`. |

`./puppet unity-test` (with the Quest **disconnected**) connects to the endpoint like the headset does
and lists what arrives per topic.

## Tests without the robot

```
scripts/ros2/build.sh --test     # build + unit tests in PAL's image
scripts/ros2/mock_test.sh        # a full session on a simulated TIAGo 38, with a fake headset over TCP
scripts/ros2/runner_test.sh      # ./puppet doctor/up/check/reset-arm/down against a fake TIAGo over SSH
```

The mock robot is PAL's own TIAGo 38 URDF with mock hardware, PAL's controller names and PAL's
PlayMotion2. It checks the controller switch both ways, Unity's view, torso, gripper, head and arm
commands from the headset, and the extend-arm button through PlayMotion2.

## Where things are

| Path | What |
|---|---|
| `ros2_ws/src/tiago_telepresence_controllers` | tp controllers (ros2_control), `arm_motion.py`, switcher, endpoint wrapper, launch file |
| `ros2_ws/src/natnet_bridge` | Motive → `/natnet_ros/<body>/pose` (same names and values as ROS 1) |
| `ros2_ws/src/keyboard_teleop` | keyboard condition (ROS 2 rewrite; the ROS 1 version stays in `ros_ws`) |
| `ros2_ws/src/puppet_bringup` | pose → `/odom_mocap`, `/puck_mocap` (same maths as ROS 1) |
| `scripts/ros2/` | build, deploy, probe, tests, the ROS 2 half of `./puppet` |
| `scripts/playmotion_to_playmotion2.py` | ROS 1 motions → PlayMotion2 YAML |
| `docs/ROS2_INTERFACE.md` | every topic and service the Quest app uses, ROS 1 next to ROS 2 |
| `docs/ROS2_FIRST_RUN.md` | checklist for the first session on the real robot |
