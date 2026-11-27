# PUPPET demo runbook (TIAGo on Gallium, ROS 1)

Two people: the **operator** (archimedes keyboard, then the headset) and the **safety person**
(beside TIAGo, hand near the red e-stop, the whole time the motors are on). Any unexpected
motion: **press the e-stop**. Never try to catch the arm.

## Before the demo (15 min)

1. **TIAGo**: area around the arm and base clear. Power on, wait 2 minutes. Red e-stop released,
   then press the **blinking green button** so the motors get power.
2. **Motive on gaia**: running, streaming on, both rigid bodies tracked: `umh_tiago_base` (robot)
   and `umh_object_mahika` (puck).
3. **Quest**: charged, on the lab WiFi. Don't open the app yet.
4. **archimedes**: open a terminal in the PUPPET checkout (branch `ros1-demo`).

## Start

```
./puppet up
```

It checks everything first (network, SSH, e-stop, ROS master). Then it asks three questions,
answered by looking at the robot: physical preflight done? arm may move to its start pose now?
arm reached it cleanly? After that it starts telepresence and ends in the **status view**: one
line per part, refreshed every 2 s. Every line should say `ok`. Only `Quest: wait` is expected.

Now on the Quest: **Library > Unknown Sources > pxspatial**. The status view switches to
`Quest connected from ...`. In Unity, check that the robot and the puck sit where they really are.

Ctrl+C closes the status view; the demo keeps running. `./puppet status` opens it again.

## In the headset

| Control | Does |
|---|---|
| Right **A** | head and arm following on/off (the background goes black while on) |
| Right **B** | arm to `offer` (about 10 s). **The arm follows your right hand only after this.** B again: arm `home` (about 16 s) |
| Triggers, grip buttons | gripper open/close on one hand, torso up/down on the other |
| Thumbsticks | **drive the base**: only with the floor around TIAGo clear |
| Left X / Y | speaker / microphone |

Sequence: A, wait for the head to follow, B, wait until the arm stops at `offer`, then move the
right hand slowly. A again stops following: arm and head hold where they are.

> **Known limitation: the arm's directions depend on its pose when following starts.**
> The controller applies your hand motion in the gripper's frame at that moment, not in the
> robot's. From `offer` (where it starts after B), forward/back is right, but **up/down and
> left/right are mirrored**: move your hand down to raise the gripper, left to move it right.
> (Seen on the robot on 2026-10-26, and measured offline with the real controller code: 5 cm
> forward gives 4.6 cm forward and 1.5 cm up; 5 cm left gives 4.9 cm right; 5 cm up gives
> 4.8 cm down.) Wrist rotations are mixed up too: keep the controller's orientation steady.
> - Only turn following on (A) with the arm at `offer`. If you stop and restart following
>   elsewhere, the directions change again.
> - The command also restarts from the current pose after any pause longer than 0.25 s (WiFi
>   hiccup, B press). The arm can then jump by the offset your hand has built up since following
>   started (offline: a 0.6 s pause halfway through a 5 cm move gave 2.5 cm extra). Keep hand
>   movements small and slow, and close to where you started.
> - If the arm ends up somewhere awkward: A off, then `./puppet reset-arm` on archimedes.
>
> The real fix (in `arm_tp_controller` and the app) waits until after the demo:
> `docs/SETUP_IMPROVEMENTS.md`, "Open: arm mapping depends on the start pose".

## Stop

1. In the headset: B to `home` if the arm is out, then A to stop following. Take the headset off.
2. `./puppet down`: stops telepresence first (PAL's controllers take the arm back), then mocap.
3. Power down (ReadMe Section 15): arm in `home`, long-press the green button, press the red e-stop.

## When something fails

The status view names the broken part and the fix. The common ones:

| Status line | Fix |
|---|---|
| `TIAGo ... does not answer` | TIAGo on? archimedes and TIAGo on the lab network? |
| `ROS master ... not answering` | TIAGo still booting: wait 2 min after power-on. Never start a `roscore` on archimedes. |
| `E-stop PRESSED` | Twist the red button to release it, then press the blinking green button. |
| `Joint states silent` | Motors off: press the blinking green button. |
| `Controllers: ...` | `./puppet reset-arm` (arm back to its start pose, telepresence again). |
| `Controllers: PlayMotion has the arm` | Normal for up to 30 s after B. Longer: `./puppet reset-arm`. |
| `OptiTrack ... silent` | Motive streaming? Rigid body visible and named as above? The line lists the names that *are* published. |
| `Quest not connected` | Quest on the lab WiFi? Quit and reopen pxspatial. Only one client can connect at a time. |
| `B button ... missing` | `./puppet logs arm_motion`, then `./puppet reset-arm`. |
| `Process NAME exited` | Shows its last log line. `./puppet logs NAME` for more. Then `./puppet down` and `./puppet up`. |

Not in the status view:
- **B does nothing**: following must be on (A) first. A motion that fails or takes over 30 s is
  reported as failed, and the arm stays where it is. Press B again.
- **The arm doesn't follow**: was B's `offer` finished? The app only sends arm commands after it.
- **The arm moves in odd directions**: see the known limitation above.

Logs: `./puppet logs` (last lines of every process), `./puppet attach` (all of them in tmux,
leave with Ctrl+B then D).

## Check on the real robot before the demo

Tested offline only (`scripts/ros1/mock_test.sh`: mock TIAGo with the real telepresence
controllers, ROS-TCP-Endpoint and `./puppet`). On TIAGo, with the safety person at the e-stop:

- [ ] `./puppet doctor` reads the e-stop state (`E-stop released`, not `unknown`).
- [ ] `./puppet up` reaches the status view with every line `ok`, `Quest: wait`.
- [ ] Opening pxspatial turns the Quest line to `connected from <Quest IP>`.
- [ ] B: `offer` finishes and the status line `B button` shows it. B again: `home` finishes
      (about 16 s) instead of stopping halfway as before.
- [ ] From `offer`, small hand moves (5 cm): forward, up, left. Note what the gripper does, and
      update the known-limitation box if it differs.
- [ ] Which hand's trigger moves the torso, which the gripper (fix the controls table).
- [ ] Stop Motive streaming for a moment: the status view shows `OptiTrack ... silent`.
- [ ] `./puppet down` hands the arm back to PAL's controllers (the arm holds, no drop).
