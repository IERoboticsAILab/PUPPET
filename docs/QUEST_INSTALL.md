# Installing PUPPET on the Quest

There are two apps, one per robot software version. Install the one that matches TIAGo, or both side by side:

| Robot runs | Install | Shows in the Quest as |
|---|---|---|
| PAL OS 25.01 (ROS 2 Humble) | `Builds/PUPPET-ros2.apk` | PUPPET ROS2 |
| Gallium (ROS 1 Noetic), the rollback | `Builds/PUPPET-ros1.apk` | PUPPET ROS1 |

ROS-TCP-Connector chooses ROS 1 or ROS 2 when the app is compiled, so one APK can't do both. If you start the wrong one, the headset says so (see "Status messages" below). [UNITY_ROS1_ROS2.md](UNITY_ROS1_ROS2.md) explains the decision.

## Install

Plug the Quest into the Mac with USB, put it on, and allow USB debugging. Then, from the repo root:

```bash
unity/quest.sh install ros2      # = adb install -r unity/PUPPET_Unity/Builds/PUPPET-ros2.apk
unity/quest.sh install ros1      # the ROS 1 fallback, same thing
```

Plain adb works too, if `adb` is on your PATH (it's at `~/Library/Android/sdk/platform-tools/adb`):

```bash
adb install -r unity/PUPPET_Unity/Builds/PUPPET-ros2.apk
```

In the headset, open **App Library > Unknown Sources > PUPPET ROS2**.

## Set the robot address

The default is `10.205.3.26:10000`: TIAGo on the lab WiFi, with ROS-TCP-Endpoint on port 10000. There are two ways to change it, and neither needs a rebuild:

- **In the headset:** press the **menu button on the left controller** (≡). A list of addresses appears under the status text. Press ≡ again to move to the next address. **Hold ≡ for 1 second** to connect to the selected one. The choice is saved. If you do nothing for 12 seconds, the list closes and nothing changes.
- **From the Mac:**
  ```bash
  unity/quest.sh set-ip 10.205.3.26          # ROS 2 app; add "ros1" for the other app
  unity/quest.sh set-ip 10.68.0.1 ros1 10000 # address, app, port
  unity/quest.sh show                        # print the current settings
  unity/quest.sh edit                        # edit every setting in $EDITOR
  ```
  This also adds the address to the headset list, and restarts the app if it's running.

The settings live in `puppet_settings.json` in the app's folder on the Quest (`/sdcard/Android/data/com.ProjectX.pxspatialversion.ros2/files/`, or `.ros1`). The app creates the file on first start:

```json
{
    "robotIp": "10.205.3.26",
    "robotPort": 10000,
    "ipPresets": ["10.205.3.26", "10.68.0.1"],
    "topicRemaps": [],
    "showStatus": true
}
```

`topicRemaps` renames a topic or service in the scene without a rebuild. The ROS 2 app already uses the 25.01 names where they differ from ROS 1:

| What | ROS 1 app | ROS 2 app (built in) |
|---|---|---|
| Base velocity (`geometry_msgs/Twist`) | `/mobile_base_controller/cmd_vel` | `/key_vel` (a twist_mux input; PAL's joystick still overrides it) |
| Camera (Unity adds `/compressed`) | `/xtion/rgb/image_raw` | `/head_front_camera/rgb/image_raw` |

Every other name is the same in both apps. If the robot turns out to differ tomorrow, add an entry. `from` can be the ROS 1 name or the built-in ROS 2 name:

```json
"topicRemaps": [ { "from": "/key_vel", "to": "/cmd_vel" } ]
```

## Status messages

A short text line sits at the bottom of your view, drawn over everything. When everything is fine it's one green line, `ROS 2: connected to 10.205.3.26:10000`. Problems appear under that line, most serious first.

| Message | Colour | What it means / what to do |
|---|---|---|
| `connecting to <ip>:<port> ...` | grey | Just started. Takes a second. |
| `cannot reach robot endpoint <ip>:<port> (retrying)` | red | Nothing answers at that address. Check that the Quest and TIAGo are on the same WiFi, that the address is right (menu button), and that the endpoint is running (`./puppet up`, `./puppet doctor`). The app keeps retrying, so it reconnects once the endpoint is up. |
| `connection to <ip>:<port> LOST (retrying)` | red | It was connected and dropped: the endpoint stopped, or the WiFi dropped. Robot commands aren't arriving. |
| `WRONG APP: the robot endpoint runs ROS 1, this app is ROS 2. Install PUPPET-ros1.apk` | red | The app doesn't match the robot's software. Start the other app. |
| `Endpoint version mismatch` | yellow | The robot's ROS-TCP-Endpoint isn't v0.7.x. Update it on the robot. |
| `Robot joints: /joint_states never received` or `none for N s` | red | Connected, but the robot isn't publishing joint states: robot bringup down, or the endpoint isn't bridging. The robot model in VR won't move. |
| `Camera: /head_front_camera/rgb/image_raw/compressed ...` (ROS 1: `/xtion/...`) | yellow | No camera images. The camera driver is off, or the topic has a different name on this robot (use `topicRemaps`). |
| `Base odometry: ...` | yellow | No `/mobile_base_controller/odom`. |
| `mocap: no data`, `mocap (robot): no data` | grey | No OptiTrack data (`/odom_mocap`, `/puck_mocap`, `/natnet_ros/*`). Normal when NatNet on archimedes or Motive isn't running. The tracked table, shelf and robot base don't move. |
| `audio: no data` | grey | Normal: audio is off unless `TELEPRESENCE_AUDIO=true`. |
| `Arm: 'offer' sent, waiting for the robot ...` | grey | The B-button motion request has been sent to `/tp_arm_motion/command`. |
| `Arm motion 'offer' FAILED: <reason>` | red | The robot refused the motion. The reason comes from the robot. |
| `Arm motion 'offer' got NO ANSWER ... Arm teleop turned off` | red | No reply after 10 s (15 s for 'home'). The arm_motion node is probably down. Arm teleop is turned off on purpose; enable it again to retry. |
| `ARM TELEOP ON` / `arm enabled (arm at home)` | yellow | Arm teleoperation is on. This line is a reminder, not an error. |
| `Error: ...` | yellow | The last errors the app or the endpoint logged (for example a service that doesn't exist on the robot). Each one shows for 20 s. |

From the Mac, `unity/quest.sh logs` follows the same information in the Quest log.

## Build the APKs

Close the project in the Unity Editor, then run this from the repo root:

```bash
unity/build_quest.sh           # both APKs, about 10-20 min each
unity/build_quest.sh ros2      # or just one
```

The script builds `unity/PUPPET_Unity/Builds/PUPPET-ros2.apk` and `PUPPET-ros1.apk` from `MAIN PUPPET SCENE`, then checks that each APK was compiled for the protocol its name says. The log is in `unity/PUPPET_Unity/Logs/build_quest_<which>.log`. The app version shown in the Quest is `ros2-<git commit>`, with `+` if there were uncommitted Unity changes.
