# PUPPET interface contract: Unity ↔ ROS (ROS 1 Gallium and ROS 2 25.01)

This is the single list of every topic and service the Quest app (Unity) uses, and what serves it
on each robot OS. Owners: `puppet_ros2` (robot side), `puppet_unity` (Unity side). Change it here
first, then tell the other side.

**Rule:** names and types stay the same on ROS 1 and ROS 2. When PAL renamed something on 25.01,
the robot side adds a relay or remap. Unity does not change.

## Connection

| | ROS 1 (Gallium) | ROS 2 (PAL OS 25.01, Humble) |
|---|---|---|
| Endpoint | ROS-TCP-Endpoint (ROS 1, pinned in `dependencies/tiago_public_ws.rosinstall`) | ROS-TCP-Endpoint `main-ros2` v0.7.0 |
| Runs on | TIAGo | TIAGo |
| Address | `10.205.3.26:10000` | `10.205.3.26:10000` |
| Endpoint parameters | `tcp_ip`, `tcp_port` launch args | `ROS_IP` (default `0.0.0.0`), `ROS_TCP_PORT` (`10000`) |
| Unity build | `PUPPET-ros1.apk` (connector protocol ROS1) | `PUPPET-ros2.apk` (connector protocol ROS2) |

The connector protocol is chosen at compile time, so there are two APKs. A ROS 1 APK does not work
against a ROS 2 endpoint, and the reverse. The headset shows that mismatch at handshake. Robot IP
and port are runtime settings in the headset.

Type names on the wire are `package/Name` on both protocols. The ROS 2 endpoint splits on `/` and
imports `package.msg` or `package.srv` (`server.py`, `resolve_message_name`), so **don't** send
`package/srv/Name`.

## Unity publishes

| Topic | Type | Unity script | Served by (ROS 1) | Served by (ROS 2) |
|---|---|---|---|---|
| `/arm_tp_controller/command` | `geometry_msgs/PoseStamped` (frame `base_footprint`) | `ArmCommander.cs` | `arm_tp_controller` | `arm_tp_controller` (ros2_control) |
| `/head_tp_controller/command` | `geometry_msgs/QuaternionStamped` | `HeadCommander.cs` | `head_tp_controller` | `head_tp_controller` |
| `/torso_tp_controller/command` | `std_msgs/Int32` (−1, 0, +1 steps) | `TorsoCommander.cs` | `torso_tp_controller` | `torso_tp_controller` |
| `/gripper_tp_controller/command` | `std_msgs/Int32` (−1, 0, +1 steps) | `GripperCommander.cs` | `gripper_tp_controller` | `gripper_tp_controller` |
| `/mobile_base_controller/cmd_vel` | `geometry_msgs/Twist` | `BaseCommander.cs` | PAL base controller | **TBD**: checking 25.01 (diff_drive 4.x may take only `TwistStamped`; `twist_mux` sits in front) |
| `/audio_out/audio` | `audio_common_msgs/AudioData` | `AudioRecorder.cs` | `audio_play` (only with `TELEPRESENCE_AUDIO=true`) | `audio_play` (PAL `audio_common` 2.0.1) |

The tp controllers drop out (hold position) when no command arrives for 0.25 s. They are
inactive until the session switches them in (see "Controller switching").

## Unity subscribes

| Topic | Type | Unity script | Published by (ROS 1) | Published by (ROS 2) |
|---|---|---|---|---|
| `/joint_states` | `sensor_msgs/JointState` | `TiagoJointStateReader.cs` | PAL | PAL `joint_state_broadcaster` |
| `/xtion/rgb/image_raw/compressed` | `sensor_msgs/CompressedImage` | `ImageSubscriber.cs` | PAL camera + image_transport | **TBD**: checking the 25.01 camera topic; relay on TIAGo if renamed |
| `/mobile_base_controller/odom` | `nav_msgs/Odometry` | `TiagoBaseOdomSubscriber.cs` | PAL | PAL `mobile_base_controller` |
| `/odom_mocap` | `nav_msgs/Odometry` | `TiagoMocapFollower.cs` | `pose_to_odom.py` (archimedes) | same node on ROS 2 (archimedes, Humble in Docker) |
| `/puck_mocap` | `nav_msgs/Odometry` | `PuckMocapFollower.cs` | `puck_pose_to_odom.py` (archimedes) | same, ROS 2 |
| `/natnet_ros/table/pose` | `geometry_msgs/PoseStamped` | `TrackedFurniture.cs` | `natnet_ros_cpp` (archimedes) | ROS 2 NatNet driver, same topic names |
| `/natnet_ros/shelf/pose` | `geometry_msgs/PoseStamped` | `TrackedFurniture.cs` | `natnet_ros_cpp` | same |
| `/audio_in/audio` | `audio_common_msgs/AudioData` | `AudioPlayer.cs` | `audio_capture` (only with audio on) | `audio_capture` |
| `/head_controller/state` | `std_msgs/Float32MultiArray` | `HeadSubscriber.cs` | **type mismatch**: PAL publishes `control_msgs/JointTrajectoryControllerState`, so Unity never received data | same mismatch on ROS 2, plus a type-conflict warning. Disable in the ROS 2 build. |

Mocap topics come from archimedes, not TIAGo. On ROS 2 they reach TIAGo's endpoint through DDS,
so archimedes must use the same `ROS_DOMAIN_ID` and RMW as TIAGo (see `config/puppet.env`). Unity
shows "mocap: no data" when they are absent.

## Services (Unity is the client)

| Service | Type | Unity script | Served by |
|---|---|---|---|
| `/tp_arm_motion/command` | `tiago_telepresence_controllers/ArmMotion` | `ArmCommander.cs` (extend-arm button: `offer`, `home`) | `arm_motion.py` (ROS 1: PlayMotion; ROS 2: PlayMotion2) |

Unity sends one request at a time, with a 10 s or 15 s timeout.

## Custom types

Both live in the package **`tiago_telepresence_controllers`** on ROS 1 and ROS 2. The name is kept
on purpose: the type string goes over the wire, so one C# class serves both APKs.

`ArmMotion.srv` (used by Unity):
```
string command
---
bool success
string message
```

`JointPositions.msg` (robot-internal, `/<controller>/state`; Unity does not use it):
```
float64[] positions
int32 CMD_OK=0
int32 CMD_OUT_OF_LIMITS=1
int32 CMD_SINGULARITY=2
int32 CMD_CONVERGENCE=3
int32 CMD_UNKNOWN_ERROR=3
int32 status
```

## Controller switching (robot side, for reference)

The four `*_tp_controller`s claim the same joints as PAL's `arm_controller`, `head_controller`,
`torso_controller` and `gripper_controller`. When telepresence starts, PAL's controllers are
deactivated and ours activated, and the reverse when it stops or while an `ArmMotion` plays. On
ROS 2 this uses `/controller_manager/switch_controller` (`activate_controllers` /
`deactivate_controllers`).

## Changelog

- 2026-11-26: first version, from `puppet_unity`'s inventory of `MAIN PUPPET SCENE.unity`.
