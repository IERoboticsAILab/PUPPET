# Table corner marker clip

A 3D-printed clip that slides onto a corner of the PUPPET table and carries two OptiTrack markers. Two clips go on **diagonally opposite corners**: one of variant A, one of variant B. Their four markers form one rigid body, `umh_table`, so Motive reports where the table is. The goal is to stop relying on tape marks on the floor to place the table.

This is the **rigid version** (2026-10-27). The first print was a spring clip. Rodrigo asked for a stiffer reprint, so the markers can't shift relative to the table and OptiTrack always detects the rigid body. In his words: bigger lips that hang onto the table, connected by a thick column. He then explained that the "column" means a thick member tying the left jaw directly to the right jaw across the corner, so that's the diagonal brace below.

The clip slides on with **no screws and no springy parts**. It has two jaws, one on each straight edge. They're joined in two ways:
- a thick L-shaped wall that goes around the outside of the corner;
- a thick diagonal brace straight across the corner above the table top.

Together these make a rigid triangle, and none of it touches the corner:

- **Jaws** (85–135 mm from the corner along each edge). Each one is a solid C-channel:
  - **Upper jaw (roof):** 6 mm thick, reaching 15 mm in over the top surface.
  - **Lower jaw (lip):** 6 mm thick, reaching 15 mm in under the table.
  - **Column:** a solid wall 14 mm thick joining the roof and lip. Its inner face rests on the bare wood above and below the rubber band.
- **No play.**
  - The lip's flat top sits 0.3 mm below the underside. Four small **crush ribs** per jaw stand 0.15 mm past the underside.
  - As the clip is pushed on, the table edge rides up a ramp on each rib and squashes the rib slightly. That takes out the play without anything having to flex, and holds the roof down on the top surface.
- **Band.**
  - The band has a rounded cross-section: 9.8 mm tall where it meets the wood and 3.5 mm out at the crown, so its radius is about 5.2 mm.
  - It sits in a rounded groove in the column with **1 mm clearance** all round, so it never takes load. Squeezing a round band would push the column away from the wood, and the column resting on the wood is what fixes the clip's x and y position.
- **Corner.**
  - Nearer than 85 mm to the corner, the clip stands at least 1.5 mm clear of the band and 5 mm clear of the wood, whatever the corner radius really is. So the rounded corner never sets the pose.
  - The wall there is 9 mm thick and runs full height, so the two jaws are held rigidly at 90°.
- **Diagonal brace.**
  - A 16 mm wide, 9 mm tall bar runs from the middle of one jaw's roof (110 mm along that edge) to the middle of the other's.
  - Its underside is 1 mm above the table top, so it touches nothing. It clears the top surface, the rounded corner and the rubber band, which is lower down.
  - It ties the two jaws together so they can't flex relative to each other. Nothing goes under the table, because what's under there is still unknown.
- **Posts:** 12 mm in diameter, sunk 3 mm into the column, with M3 screw holes.

![preview](preview.png)

Top row: both variants seen from outside the corner, and the top view with the edge contact in green and the diagonal brace across the corner. The two arcs are the possible corner radii. Bottom row: a section through a crush rib, and a side view of a jaw cut through the lip, showing the four ribs.

**Status:** generated, not printed yet. Print the fit test first.

## Files

| File | What |
|---|---|
| `table_corner_marker.py` | Parametric FreeCAD script; all dimensions are at the top |
| `table_corner_marker.FCStd` | FreeCAD document with `clip_A`, `clip_B` and `fit_test`, for looking at in the FreeCAD GUI |
| `table_corner_marker_A.3mf` / `.stl` / `.step` | Variant A (posts 35 mm and 60 mm above the table top) |
| `table_corner_marker_B.3mf` / `.stl` / `.step` | Variant B (posts 50 mm and 25 mm) |
| `table_corner_marker_fit_test.3mf` / `.stl` / `.step` | One whole jaw with its crush ribs, for testing the fit before printing a whole clip |
| `preview.png` | Render of both variants, the top view and the jaw sections |
| `measurements.md` | The real table measurements, the requirements and the feedback from the first print |

The 3MF and STL files are the same meshes; Bambu Studio opens either. They carry only the geometry, no print settings, so set those as in [Printing](#printing-bambu-studio). Copies of the print files are in `~/Downloads/table_corner_marker_print/`.

## Open questions (for Rodrigo)

1. **What is the 80 mm "square part" of the corner?**
   - The 102 mm arc gives a radius of about 61.5–65 mm. A radius of 80 mm would give a 126 mm arc, so the two numbers don't agree.
   - For now, 80 mm is treated as the worst case for where the straight edge begins. The jaws start at 85 mm (`no_contact_from_corner`, `contact_start`).
   - If the straight edge really starts nearer, the jaws can move closer to the corner and the clip gets smaller.
2. **Is there room for the bigger lip?**
   - The lip now reaches 15 mm under the table (was 8 mm), from 85 to 135 mm along each edge (was 85–125).
   - If a frame rail or hinge on the flip-top table is in the way, give its distance in from the edge, and `lip_width` or `contact_start` can change.
3. **Was 1370 × 680 mm measured over the rubber band or on the wood?**
   - The pivot is on the wood. If you measured over the band, the wood is 1363 × 673 mm, and clip B's markers in the table frame shift by 7 mm.
   - The two clips can also measure it; see [below](#table-length-and-width-from-the-two-clips).
4. **Is the band really centred?**
   - Please measure from the top surface down to the top of the band, and from the underside up to the bottom of the band.
   - The groove assumes 7.75 mm for both (`band_top_below_surface`). With 1 mm of clearance, it tolerates being up to about 1 mm off.
5. **Marker size and screw stick-out.** These set `marker_center_above_post` (placeholder 7 mm), which goes into the marker offsets below.

## Regenerate

```bash
cd hardware/table_corner_marker
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd table_corner_marker.py
```
The script does the following:
- checks that each solid is valid and closed;
- rewrites the STEP, STL and 3MF files for A, B and the fit test;
- rewrites `table_corner_marker.FCStd`;
- re-renders `preview.png`;
- prints the footprint and the marker centres for the offset table below.

Copy the new `.3mf` or `.stl` files to `~/Downloads/table_corner_marker_print/` by hand if you print from there.

## Printing (Bambu Studio)

1. **Fit test first.**
   - Print `table_corner_marker_fit_test.3mf` (33 cm³, one 50 mm jaw) with the same settings as the clips, and push it onto a straight part of the edge.
   - It should take a firm push and then not rock or slide.
   - Too loose: raise `rib_crush` (0.05 mm steps). Too hard to push on: lower it.
   - If the band touches the groove, raise `groove_clearance`. Then regenerate and print the clips.
2. **Import:** open the `.3mf` (or `.stl`) in Bambu Studio.
   - The part lands in print orientation: lower lips flat on the plate, posts pointing up. Don't use auto-orient.
   - Each clip is 158 × 158 mm, 91.6 mm tall (A) and 81.6 mm tall (B). It fits one clip per plate on the X1/P1/A1 and the A1 mini.
3. **Supports are needed this time.**
   - The bigger roof is a 15 mm overhang above the pocket. The supports stand on the lip inside the pocket, so don't use "on build plate only".
   - The diagonal brace spans about 130 mm across the open corner at roof height. It needs supports too; those stand on the build plate inside the L. Its underside doesn't touch the table, so support marks there don't matter.
   - Use tree supports with interface layers and a 0.2 mm top Z distance, so the roof underside, which rests on the table, comes out clean.
   - Paint supports under the roof only if Bambu Studio adds them elsewhere.
   - When removing them, don't break the crush ribs on top of the lip.
   - The rounded groove is a shallow arch and prints without supports.
4. **Strength:**
   - Filament: PETG.
   - Walls (perimeters): 6, so the 14 mm column and the posts are close to solid. Infill: 40–60 %.
   - 100 % infill works too if you want the stiffest possible part. It's about 167 cm³ of plastic per clip.
5. **Marker screws (M3) go in after printing.** Nothing goes in mid-print, so don't add a pause.
   - Each post has a 10 mm deep, 2.5 mm pilot hole in its top.
   - Once the part is cool, drive the M3 screw straight in so it cuts its own thread. Leave enough sticking out for the marker to screw onto.
   - A drop of CA glue or thread-locker in the hole keeps the screw from turning when you screw markers on and off.
   - If markers will be swapped often, set `marker_mount = "heatset"`. That makes a 4.0 mm hole for an M3 brass heat-set insert, pressed in after printing with a soldering iron.
6. **Putting it on:** push the clip diagonally onto the corner until both columns are flat against the wood and the roof is flat on the top surface.

## Pivot and marker offsets

The pivot is the table's **sharp top corner**: where the two straight wooden edge faces would meet if the corner weren't rounded. The band is not part of this. The clip frame has its origin there:
- +x runs along one edge and +y along the other, both into the table.
- +z points up, with z = 0 on the top surface.

The columns rest on the wood, so the clip finds this corner directly.

With the current parameters, the marker centres in each clip's own frame are:

| Marker | x (mm) | y (mm) | z (mm) |
|---|---|---|---|
| A1 | -17.0 | 50.0 | 42.0 |
| A2 | 100.0 | -17.0 | 67.0 |
| B1 | -17.0 | 30.0 | 57.0 |
| B2 | 115.0 | -17.0 | 32.0 |

The z values include the placeholder `marker_center_above_post` of 7 mm (question 5), so they will change once the markers are measured.

Clip B on the opposite corner is turned 180°. In a table frame with its origin at clip A's corner (+x along the length L, +y along the width W), a B-marker at (x, y, z) in its own frame sits at **(L − x, W − y, z)**.

The table is 1370 × 680 mm (750 mm floor to top). If those are wood dimensions (question 3), the four markers in the table frame are:

| Marker | x (mm) | y (mm) | z (mm) |
|---|---|---|---|
| A1 | -17.0 | 50.0 | 42.0 |
| A2 | 100.0 | -17.0 | 67.0 |
| B1 | 1387.0 | 650.0 | 57.0 |
| B2 | 1255.0 | 697.0 | 32.0 |

All four heights are different, and the posts sit at different distances along the edges. That's what lets Motive tell the table's orientation apart without ambiguity.

### Table length and width from the two clips

Two diagonal clips can also measure L and W, as long as the table is rectangular. Use this to check the tape measurement.
1. Put both clips on and read the four marker positions in Motive.
2. Express them in clip A's frame:
   - origin: the sharp corner, i.e. A1 minus its offset;
   - +x: along the edge carrying A2;
   - +z: up.
3. Read L and W off clip B's markers:
   - **L = B1.x − 17.0**, which should equal **B2.x + 115.0**.
   - **W = B1.y + 30.0**, which should equal **B2.y − 17.0**.
4. Each dimension comes out twice. If the two values disagree by more than a millimetre or two, a clip isn't pushed fully home or the table isn't square.

The numbers come from B's offsets in the clip-frame table, using (L − x, W − y). Redo them if the posts move.

## Setting up the rigid body in Motive

1. Clip A on one corner and B on the diagonally opposite corner, both pushed fully home.
2. Select the 4 markers and create the rigid body. Name it **`umh_table`**, so natnet_ros publishes `/natnet_ros/umh_table/pose`.
3. Move the pivot to the sharp corner under clip A: pivot onto marker **A1**, then translate it by **(+17.0, −50.0, −42.0) mm**, which is minus A1's offset. Do this in the table frame, in the axes described above.
   - Set the rigid body's orientation so its axes match the table's edges. The simplest way is to align the table with Motive's ground-plane axes when creating it.
   - The menu names differ between Motive versions. Check the result by reading the pose while a tracked marker or the puck is held on the corner.
4. Once the pivot is the table corner, no extra offsets are needed in ROS.

If you change any parameter, re-run the script and use the marker centres it prints.
