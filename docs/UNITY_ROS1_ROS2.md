# Unity: ROS 1 and ROS 2 from one project

Decided 2026-11-26, for the switch of TIAGo to PAL OS 25.01 (ROS 2 Humble), with Gallium (ROS 1) kept as the rollback.

## Decision: two APKs from one command

`unity/build_quest.sh` builds `PUPPET-ros2.apk` and `PUPPET-ros1.apk` from the same project and scene. They have separate app ids (`com.ProjectX.pxspatialversion.ros2` and `.ros1`), so both can be installed at once. Install and use: [QUEST_INSTALL.md](QUEST_INSTALL.md).

## Why not a runtime switch

ROS-TCP-Connector picks the protocol at compile time with the `ROS2` scripting define (Robotics > ROS Settings > Protocol). The define changes:

- message serialization (`MessageSerializer` / `MessageDeserializer`): ROS 2 adds a CDR header, aligns fields, and null-terminates strings;
- the handwritten `std_msgs/Header`, `builtin_interfaces/Time` and `Duration` (ROS 2 has no `seq`, and Time uses `sec`/`nanosec`);
- the handshake check against the endpoint's protocol.

A runtime switch would mean forking the connector and turning every `#if ROS2` into a branch. That's possible, but it's a risky change to make the day before the robot moves to 25.01, for little gain: you pick the app once per robot software version, not during a session. If we want one APK later, the fork is the way, and auto-detecting the protocol from the endpoint's handshake would be the nice version of it.

## How the build does it

`unity/build_quest.sh` starts Unity in batch mode once per flavour. For the ROS 2 build, it first writes `Assets/csc.rsp` containing `-define:ROS2`, so the editor and the player are both compiled for ROS 2. They must match: the serialized layout of types like `HeaderMsg` differs, and Unity refuses a player build whose layout differs from the editor's. The script deletes the file afterwards. The project's own setting (Robotics > ROS Settings) stays ROS 1, so the Editor and Play mode behave as before. `Assets/Editor/PuppetBuild.cs` refuses to build a flavour that doesn't match how the scripts were compiled. After each build, the script checks inside the APK that it was compiled for the protocol in its file name.

## What is the same in both

- Topic, service and type names, except the two below. The contract is `docs/ROS2_INTERFACE.md` on the `ros2-port` branch.
- `tiago_telepresence_controllers/ArmMotion` keeps its package name and fields on ROS 2, so one generated C# class serves both APKs. ROS-TCP-Endpoint `main-ros2` takes `pkg/Name` type names, as Unity sends them.
- Generated message classes in `Assets/RosMessages`: they follow the define through the connector's serializer, so no separate ROS 2 set is needed.
- Runtime settings (`puppet_settings.json`): robot address, address list, topic remaps, status text on or off.
- The in-headset status text (`Assets/Scripts/Puppet/PuppetStatus.cs`).

## Differences

- Topic names. The scene keeps the ROS 1 names, and the ROS 2 build renames two of them when the app starts (`BuiltInRemaps` in `PuppetStatus.cs`):
  - base velocity `/mobile_base_controller/cmd_vel` becomes `/key_vel`. 25.01's diff_drive controller only takes `TwistStamped`, and `/key_vel` is a twist_mux input with priority 90, below PAL's joystick (100). So the joystick still overrides the headset. twist_mux's `key_vel` timeout is 0.5 s and the controller's `cmd_vel_timeout` is 0.25 s, so the base stops within about 0.75 s if the headset or WiFi drops. `BaseCommander` publishes at a steady rate even with the sticks released (it ramps down to zero and keeps sending zero), so while PUPPET runs it holds `key_vel`. Lower-priority twist_mux inputs, such as navigation, are blocked during that time; the joystick is not.
  - camera `/xtion/rgb/image_raw` becomes `/head_front_camera/rgb/image_raw` (25.01's Astra driver).

  The settings file's `topicRemaps` are applied after these, so a wrong name can be fixed tomorrow without a rebuild.

- `HeadSubscriber` doesn't subscribe to `/head_controller/state` in the ROS 2 build. That topic is `control_msgs/JointTrajectoryControllerState` on the robot, not the `Float32MultiArray` Unity asks for, so it never received data on ROS 1 either. On ROS 2 the mismatch is a type conflict. Its value isn't used anywhere.
