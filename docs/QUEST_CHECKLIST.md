# Quest app: what was tested, and what to check with the robot

For the APKs built on 2026-11-26 from branch `unity-ros2`. Install and status messages: [QUEST_INSTALL.md](QUEST_INSTALL.md).

## Tested without the robot (2026-11-26)

- **Both APKs build** with `unity/build_quest.sh` from a clean checkout of this branch. The script checked that `PUPPET-ros2.apk` was compiled for ROS 2 and `PUPPET-ros1.apk` for ROS 1, and `aapt` shows separate app ids (`com.ProjectX.pxspatialversion.ros2` / `.ros1`) and labels (PUPPET ROS2 / PUPPET ROS1).
- **The ROS 2 names are built in only where they should be:** `/key_vel` and `/head_front_camera/rgb/image_raw` are in the ROS 2 APK and not in the ROS 1 APK.
- **The ROS 2 code compiles:** the Header/Time differences in `ArmCommander` and `HeadCommander` failed to compile before this branch (`seq` doesn't exist on ROS 2).
- **The status text, in Play mode** with the main scene, against `unity/tools/fake_endpoint.py` (a stand-in for ROS-TCP-Endpoint), recording the text and screenshots at 1 to 12 s:
  - No endpoint: red `cannot reach robot endpoint 127.0.0.1:10000 (retrying)`.
  - Endpoint speaks ROS 2, app is ROS 1: red `WRONG APP: the robot endpoint runs ROS 2, this app is ROS 1. Install PUPPET-ros2.apk`.
  - Endpoint speaks ROS 1 and publishes `/joint_states`: green `connected`, no joints line, yellow `Camera ... never received` after the grace period, grey `mocap: no data`.
  - Endpoint sends an error (`Service ... is not available`): shown as a yellow `Error:` line.
  - Endpoint stops: red `connection ... LOST (retrying)`.
  - Address list (menu button) and the arm-motion timeout message render and are readable over the bright lab scene.
- **What Unity registers with the endpoint:** every topic, type and service the ROS 1 Play-mode run registered (fake endpoint log) is in the contract `docs/ROS2_INTERFACE.md` (branch `ros2-port`).

To repeat a test: close the Editor, run `python3 unity/tools/fake_endpoint.py --protocol ROS1 --joint-states`, then from `unity/PUPPET_Unity` run
`Unity -batchmode -projectPath . -executeMethod PuppetStatusPlayTest.Run -puppetTestOut /tmp/puppet_test -puppetTestIp 127.0.0.1`.
It writes `status.txt` and screenshots there. Unity sometimes crashes on exit after writing them; the results are still valid. Like any time Unity opens this checkout, it deletes `.meta` files whose image isn't in the repo; put them back with `git checkout -- '*.meta'`.

## Not tested (needs the robot or the headset)

- Anything on the Quest itself: no headset was connected. The menu-button binding (`<XRController>{LeftHand}/start` on the Oculus XR plugin) and the status text's size and position were checked only in the Editor. The address list was opened by a test hook, not by the button.
- The arm-motion timeout path in `ArmCommander` (it needs the B button); only its message was rendered.
- Real ROS 2 message traffic: serialization of every type against `ROS-TCP-Endpoint main-ros2`.
- The camera, odometry, mocap and audio topics on 25.01.

## Checklist for the robot session

Do these in order. Stop at the first one that fails and note what the headset says.

**Before you start**
- [ ] `adb devices` lists the Quest. Install with `unity/quest.sh install ros2` (and `install ros1` for the rollback).
- [ ] In the headset, App Library > Unknown Sources shows **PUPPET ROS2** (and **PUPPET ROS1**).

**Connection, robot not running PUPPET yet**
- [ ] Start PUPPET ROS2 with the endpoint not running. The headset shows red `ROS 2: cannot reach robot endpoint 10.205.3.26:10000 (retrying)`. If TIAGo's IP isn't 10.205.3.26, change it with the left menu button, or `unity/quest.sh set-ip <ip>`.
- [ ] Start the robot side (`./puppet up`). Within a few seconds the status turns green: `ROS 2: connected to ...`, and no restart is needed.
- [ ] Only if TIAGo is still on Gallium: PUPPET ROS2 shows `WRONG APP: the robot endpoint runs ROS 1 ...`. PUPPET ROS1 connects.

**Data from the robot (nothing moves yet)**
- [ ] No red `Robot joints` line. The VR robot model matches the real robot's pose (arm, head, torso, gripper).
- [ ] No yellow `Camera` line, and the camera image shows in VR. The ROS 2 app reads `/head_front_camera/rgb/image_raw/compressed`. If it says `never received`, check that topic on the robot (`ros2 topic hz`). If PAL named it differently, add a `topicRemaps` entry from `/head_front_camera/rgb/image_raw` with `unity/quest.sh edit`.
- [ ] No yellow `Base odometry` line.
- [ ] With NatNet running on archimedes: the grey `mocap: no data` note goes away, and the table and shelf models follow their markers.
- [ ] Pull the WiFi or stop the endpoint for a moment: red `connection ... LOST (retrying)`, then green again when it's back.

**Motion (robot clear, e-stop in hand)**
- [ ] Head: head tracking moves the robot head as on ROS 1.
- [ ] Torso and gripper commands work.
- [ ] Base: a small thumbstick push moves the base. The ROS 2 app publishes `geometry_msgs/Twist` on `/key_vel`, which goes into twist_mux. If the base doesn't move, check `ros2 topic echo /key_vel` on the robot, and that nothing with higher priority is active in twist_mux (the joystick wins at 100).
- [ ] Arm: enable arm motion. The yellow `arm enabled (arm at home)` appears. Press B: `Arm: 'offer' sent, waiting for the robot ...`, the arm moves to offer, then `Arm: 'offer' done` and `ARM TELEOP ON`.
- [ ] Arm teleop follows the controller as on ROS 1. Press B again: the arm goes home.
- [ ] If B gives `got NO ANSWER` or `FAILED`, note the message: the problem is `/tp_arm_motion/command` on the robot. Teleop is off after a timeout until you enable it again; that is intended.

**Rollback (only if 25.01 is abandoned)**
- [ ] With TIAGo back on Gallium, PUPPET ROS1 connects and the same checks pass.
