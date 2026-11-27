# Lab furniture measurements

Measured by Rodrigo on the real lab furniture (2026-10-26 and 2026-10-27). These measurements are the reference for the Unity scene models and the OptiTrack marker clips. The Unity scene used generic models that don't match the real furniture (see the end of this page).

## Table (flip-top folding table on castors)

| What | Value |
|---|---|
| Top, length × width | 1370 × 680 mm, between the sharp corners |
| Height, floor to top surface | 750 mm |
| Edge thickness (top surface to underside, at the edge) | 25.3 mm |
| Rubber edge band | 9.8 mm tall, 3.5 mm proud, centred on the edge face, rounded profile |
| Corner | Arc ≈ 102 mm long, so radius ≈ 65 mm (over the band) |

The detailed corner measurements for the marker clip are in `hardware/table_corner_marker/measurements.md`.

## Shelf (wire-ladder frame, three sheet-metal shelves)

| What | Value |
|---|---|
| Each shelf | 900 × 365 mm |
| Shelf top surfaces above the floor | 130 mm (1st), 620 mm (2nd), 990 mm (3rd) |
| Highest point of the frame | 1350 mm |
| Shelf edge | Folded sheet: front face 25.8 mm tall, returning 17.1 mm underneath, 0.9 mm thick. The same fold runs along the front, sides and back |
| Side ladder columns | 8 mm diameter |
| Ladder rungs | Pairs of 5 mm rods with a 6.2 mm gap between them, one rod either side of the columns |
| Column centres (from OptiTrack) | 917.5 mm apart along the boards, 322.2 mm apart across them |

The OptiTrack markers are balls screwed onto the tops of the four corner columns. The planned shelf clips were dropped.

## OptiTrack rigid bodies (2026-10-27)

Motive 3.5.0.2 on gaia (10.205.3.3) streams NatNet 4.5. The rigid bodies are named `table` (ID 22) and `shelf` (ID 21), so their ROS topics are `/natnet_ros/table/pose` and `/natnet_ros/shelf/pose`.

`hardware/lab_models/natnet_modeldef.py` asks Motive for the marker layouts. The offsets below are in each rigid body's local frame (Motive, Y up, mm), relative to the pivot, which is the centroid of the markers.

| Marker | Table x, y, z | Shelf x, y, z |
|---|---|---|
| 1 | −664.9, 12.0, 159.1 | 120.3, 1.6, 471.5 |
| 2 | 653.2, −13.0, −155.5 | −120.7, 9.4, −470.6 |
| 3 | 762.8, 12.9, −67.8 | 200.8, −6.4, −442.4 |
| 4 | −751.1, −11.9, 64.1 | −200.4, −4.6, 441.5 |

### Shelf

- **Markers:** the four balls are on the tops of the four corner columns. They form a 917.5 × 322.2 mm rectangle, so:
  - the column centres are 8.75 mm beyond each end of the 900 mm boards;
  - the columns are inset 21.4 mm from the 365 mm depth.
- **Long axis** in the rigid-body frame: (0.087, 0, −0.996), about 5° off local −Z.
- **Height:** the pivot is 1365.7 mm above the floor (live reading). So the model's origin, on the floor under the centre, is at (0, −1365.7, 0) in the rigid-body frame.

### Table

- **Markers:** two balls on each of two printed corner clips, variants A and B from `hardware/table_corner_marker`, on diagonally opposite corners.
- **Fit:** fitting the clip CAD's ball positions to the measured markers leaves 3.2 mm mean and 4.8 mm max residual, and only one assignment fits.
- **Model origin** (floor, under the centre of the top) in the rigid-body frame: (7.2, −799.5, 3.0) mm.
- **Long axis:** (−0.950, 0, −0.311).
- **Top:** level with the rigid body to within 0.5°.

### In Unity

`TrackedFurniture` moves an empty object to the rigid body's pivot. The furniture model is a child of that empty.

**How the axes line up:**
- natnet_ros passes Motive's stream through unchanged, and the stream is Z-up. That's why `pose_to_odom.py` uses `z` as height.
- Assuming Motive's Z-up conversion is (x, −z, y), Unity local (x, y, z) = Motive local (x, y, −z). The marker offsets above come from Motive's asset descriptions, which stay Y-up.

**The children need:**

| | Local position (m) | Local yaw (°) |
|---|---|---|
| Table | (0.0072, −0.7995, −0.0030) | −161.9 |
| Shelf | (0, −1.3657, 0) | −85.0 |

Both pieces look the same turned 180°, so a yaw that is off by exactly 180° doesn't matter. **Check the yaw on the headset in the lab:** if Motive's Z-up conversion is different, it will be off by a fixed amount.

**In `MAIN PUPPET SCENE`:**
- `Table (tracked)` and `Shelf (tracked)` replace the old desk and shelf. The old pieces are still in the scene, switched off.
- Until the first pose arrives, they stand where the old pieces stood.
- They take the horizontal mocap offset from TIAGo's enabled `TiagoMocapFollower`, on `base_link`, so they line up with the robot.
- Their height comes from Motive (floor at z = 0) plus `floorHeight`, which is 0 because the scene floor is at y = 0. TIAGo's own offset isn't used for height because `base_link` sits 9.9 cm above the floor.

`Assets/Editor/LabFurnitureSetup.cs` sets this up again (`Apply`, safe to re-run). It also builds a Quest APK under a separate app id, `com.ProjectX.pxspatialversion.dev` ("PUPPET dev"), so it installs next to the lab's APK. Run `hardware/lab_models/build_quest_dev.sh`; the APK goes to `unity/PUPPET_Unity/Builds/PUPPET-dev.apk`. The script moves URDF-Importer's desktop `assimp` libraries out of the package cache for the build, because Android otherwise finds two `assimp.dll` and fails.

The repo has no images: 184 PNG, 105 JPG and 61 EXR files are present only as `.meta` files, probably left behind when the project moved into `unity/PUPPET_Unity`. A build from a fresh clone is missing those textures and icons. Unity also deletes the orphaned `.meta` files on import; `git checkout` brings them back.

## Unity scene vs the real furniture

| | Unity (`MAIN PUPPET SCENE`) | Real |
|---|---|---|
| Table top | ≈ 1546 × 853 mm, top at ≈ 776 mm (`escritorio2_0.fbx`) | 1370 × 680 mm, 750 mm |
| Shelf | Generic bookcase (`shelf-scp/Shelf.obj` at scale 0.3): 4 levels at ≈ 0.24, 0.77, 1.24, 1.75 m, boards ≈ 1173 × 432 mm, 1.94 m tall | 3 shelves at 0.13, 0.62, 0.99 m, 900 × 365 mm, 1.35 m tall |

The replacement models built from these numbers are in `unity/PUPPET_Unity/Assets/LabModels/` (`lab_table.fbx`, `lab_shelf.fbx`, in metres, origin on the floor under the centre). `hardware/lab_models/build_lab_models.py` generates them with Blender; change a number there and re-run it. The legs, castors and ladder rods are approximate. The table top and the shelf boards are as measured.
