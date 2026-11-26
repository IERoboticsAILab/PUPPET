# First PUPPET session on TIAGo with PAL OS 25.01: checklist

For the first run after the flash. Do the steps in order and stop at the first one that fails;
each step says what to look at. **A second person stays at the e-stop from step 5 on.** Steps 1–4
never move the robot, and most checks in step 5 run with the e-stop **pressed** (motors off).

Commands run on archimedes in the PUPPET checkout (`ros2` branch, or `ros2-port` until merged),
unless they say "control window" (`./puppet attach`, window `control`, a shell on TIAGo).

## 1. Reach the robot (no motion)

- [ ] `ping 10.205.3.26` and `ssh pal@tiago-38c` (password `pal`), then `ssh-copy-id pal@tiago-38c`.
      If the address changed after the flash, set `TIAGO_IP`, `TCP_IP` and `TIAGO_SSH` in
      `config/puppet.local.env`.
- [ ] `./puppet version` prints `runs ROS 2`.

## 2. Deploy (no motion)

- [ ] `./puppet deploy` (on a machine with Docker and PAL's `uni-ie` folder; archimedes, MSI or the Mac).
      It ends with `PUPPET <version> deployed`.

## 3. Doctor (no motion)

- [ ] `./puppet doctor`. Note these lines for the record:
  - `ROS 2 humble, RMW ..., ROS_DOMAIN_ID ..., from .../ros2_control_node ...`: PUPPET adopted
    PAL's DDS settings. If it says `from login environment`, stop and send the output.
  - `PAL arm/head/torso/gripper controllers active`. If one is missing, send `ros2 control
    list_controllers` (control window): PAL's 25.01 names may differ from `arm_controller` etc.
  - `play_motion2 running`.
  - `move_group`. If doctor reports it missing, set `PLAN_MOTIONS=false` for today.
  - camera. If it says the compressed topic is missing but raw exists, set `COMPRESS_CAMERA=true`.
- [ ] `TIAGo reaches Motive 10.205.3.3`.

## 4. Mocap on TIAGo (no motion)

- [ ] In Motive (gaia), Streaming pane: Broadcast Frame Data on, Transmission Type **Unicast**, so Motive
      streams to the client that connects, which is now TIAGo at **10.205.3.26** (on Gallium it was
      archimedes). The rigid bodies `umh_tiago_base`, `umh_object_mahika`, `table` and `shelf` are tracked.
- [ ] Control window: `ros2 launch puppet_bringup mocap.launch.py client_ip:=10.205.3.26` shows
      `Connected to Motive` and one `Rigid body ... -> ~/<name>/pose` line per body. Ctrl+C after.
  - No connection: TIAGo's firewall may block NatNet's UDP ports 1510/1511. Check with `sudo ufw status`.
- [ ] Compare one pose with Gallium-era values: the TIAGo tracker's z is about 0.099 m above the floor (ReadMe sections 8–9).
- [ ] **Pose lag and drops over WiFi.** NatNet now crosses WiFi to TIAGo, not the wired link to archimedes.
      While mocap runs, in the control window:
      `ros2 topic hz /natnet_ros/umh_tiago_base/pose` should be steady at Motive's frame rate (e.g. 120 Hz),
      with no gaps. `ros2 topic delay` doesn't apply (stamps are TIAGo's receive time). Instead, move a
      rigid body by hand and watch the headset for visible lag. If the rate drops or stutters, note the
      numbers. The fallback is running the bridge on archimedes with robot-side DDS peers (ROR-155).

## 5. Telepresence with the e-stop PRESSED (motors off)

- [ ] Press the e-stop. `./puppet doctor` now shows `E-stop pressed`. That proves the e-stop check works.
- [ ] Control window: `ros2 launch tiago_telepresence_controllers telepresence.launch.py`.
      Look for `Activated arm controller ...` for all four, and `telepresence controllers active`.
  - If the switch fails while the e-stop is pressed, that's expected on some PAL versions. Note the
    message and go to step 6, which runs with the motors on.
- [ ] Quest: install `PUPPET-ros2.apk` and connect (`docs/QUEST_INSTALL.md`). The headset shows the
      robot's joint states and camera, and `mocap` data if step 4 runs.
- [ ] Control window, second shell: `ros2 topic echo /torso_tp_controller/command` while pressing the
      torso buttons. Same for `/head_tp_controller/command` and `/arm_tp_controller/command`
      (arm motion enabled in the headset). These prove the commands arrive; nothing moves.
- [ ] `ros2 topic echo /key_vel` while using the thumbsticks: the base commands arrive at PAL's twist_mux.
- [ ] Ctrl+C the launch. `ros2 control list_controllers` shows PAL's controllers active again.

## 6. Head and torso only, motors on

- [ ] Release the e-stop (twist up, then the blinking green button). Clear area around the robot.
- [ ] `./puppet up` and answer the questions; the start pose (`extend`) plays through PlayMotion2.
      Check it is the same pose as on Gallium.
- [ ] Headset: small head motions. Then torso up/down one step at a time.
- [ ] `./puppet check` is all `ok` (mocap needs step 4).

## 7. Arm and gripper (README section 5 preflight)

- [ ] Workspace clear, e-stop in reach, the operator looks at the robot, not only the headset.
- [ ] Gripper open/close.
- [ ] Arm: enable arm motion in the headset and move slowly from the start pose.
- [ ] Extend-arm button (`offer` / `home`): the arm plays the motion and telepresence resumes.
- [ ] Press the e-stop during a small motion and release it. Then `./puppet check`: if the tp
      controllers are inactive (PAL restarts its own after an e-stop), `./puppet reset-arm` brings
      them back. Note what happened.

## 8. Keyboard condition (study baseline)

- [ ] Telepresence running (`./puppet up`), headset arm control **off**.
- [ ] Control window: `ros2 run keyboard_teleop keyboard_arm_teleop.py`. Same keys as Gallium:
      `i/k` forward/back, `j/l` left/right, `w/s` up/down, `+/-` step, `x` stop, `q` quit.
      Each key moves the hand 3 mm at 1 cm/s; `x` makes the arm hold.
- [ ] Compare the feel with the Gallium version (that one used MoveIt at 5 % speed). Adjust `--speed` if needed.

## 9. Base (optional, clear floor)

- [ ] Thumbsticks: slow base motion. The base stops within about 0.5 s of releasing the sticks.
- [ ] The joystick overrides the headset (twist_mux priority).

## 10. Full session and wrap-up

- [ ] A full session from the headset with mocap, then `./puppet down`.
- [ ] Send the `./puppet doctor` output and any step that failed, so docs and Linear (ROR-158) can be updated.

## Rollback

If 25.01 fails: restore Gallium from the disk image (`tiago-backup-tools/RESTORE.md`). The same
`./puppet` commands then run the ROS 1 session (`./puppet version` prints `runs ROS 1`), and the
Quest needs `PUPPET-ros1.apk`.
