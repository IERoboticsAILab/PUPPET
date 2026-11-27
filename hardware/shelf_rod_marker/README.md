# Shelf rod marker clip

A 3D-printed clip that snaps onto a rung of the lab shelf, next to a front column, and carries one OptiTrack marker. There are two clips, **A** and **B**, with different post heights. Together with the two marker balls already on the column-top X-brace studs, they make up the shelf's rigid body.

A rung is a pair of 5 mm rods with a 6.2 mm gap. The rods sit either side of the 8 mm column and are sunk into it, so the column axis lies on the pair's centre plane (Rodrigo, 2026-10-27).

How the clip goes on:
1. Press it down onto the two rods a little away from the column, until it clicks.
2. Slide it along the rods towards the front column, until the column snaps into the C at its front end.

The clip has three working parts:

- **Wedge rib.** It drops into the gap between the rods. Its two 45° faces rest on the inner-upper side of each rod, so the clip sits on the pair like a roof on two logs. That sets the clip's sideways position and height with no clearance. A ±0.2 mm error in the gap only moves the clip ±0.1 mm in height.
- **Hooks.** There is one springy arm outside each rod. Its hook catches the rod's outer-lower side on a face parallel to the wedge face, so each rod is clamped across its diameter.
  - The hook face sits 0.15 mm past the rod (`hook_preload`), so the clip has no play once it's on.
  - Slots free each arm up to 4 mm below the top. That makes the arm long enough to flex 0.9 mm at about 1 % strain.
- **Column cradle.** This is a C around the column, above the rods: the rods are welded to the column on both sides, so it can't wrap the column at rod level.
  - Each jaw tip reaches 0.3 mm past the column's widest point (`cradle_snap`), so the C snaps on.
  - It stops the slide and locks the clip against sliding back or twisting.
  - It grips the column from about 2 mm (at the back) and 7 mm (at the jaw tips) up to 14 mm above the rod tops.
  - Within 2 mm of the column (`front_relief`) the clip doesn't touch the rods. From there its underside rises 1 mm for every mm towards the column, so it clears the weld beads.
- **Post.** It is 10 mm in diameter, 12 mm back from the column axis, on the centre line. It has a 2.5 mm × 10 mm pilot hole for the M3 screw.

![preview](preview.png)

Top row: both clips on a rung, with the rods and column in grey. Bottom row, left to right:
- a section across the rods, with the four contact points in green;
- a plan section through the cradle;
- a side section on the centre plane, showing the sloped underside next to the column.

**Status:** generated, not printed yet. Print the fit test first.

## Files

| File | What |
|---|---|
| `shelf_rod_marker.py` | Parametric FreeCAD script; all dimensions are at the top |
| `shelf_rod_marker.FCStd` | FreeCAD document with `clip_A`, `clip_B` and `fit_test`, for looking at in the FreeCAD GUI |
| `shelf_rod_marker_A.3mf` / `.stl` / `.step` | Clip A: post top 20 mm above the rod tops |
| `shelf_rod_marker_B.3mf` / `.stl` / `.step` | Clip B: post top 40 mm above the rod tops |
| `shelf_rod_marker_fit_test.3mf` / `.stl` / `.step` | The whole cross-section and the cradle, 10 mm long, no post: tests both snaps |
| `preview.png` | Render of both clips on the rung, and the three sections |
| `measurements.md` | The shelf measurements, the requirements and Rodrigo's answers |

The 3MF and STL files are the same meshes; Bambu Studio opens either. They carry only the geometry, no print settings, so set those as in [Printing](#printing-bambu-studio). Copies of the print files are in `~/Downloads/shelf_rod_marker_print/`.

## Open questions (for Rodrigo)

1. **Is there 15 mm of free column above the chosen rung?**
   - The cradle reaches 14 mm above the rod tops (`deck_height`). Any X-brace connector or shelf bracket in that range would get in the way.
   - If there's less room, lower `deck_height`. The arms get shorter and stiffer with it.
2. **Is anything right under the rods?**
   - The hooks and the rib reach 1.1 mm below the rod bottoms. They must not land on the shelf's folded sheet edge or a connector.
3. **Weld beads.**
   - Nothing touches the rods within 2 mm of the column. If the beads run further along the rods, raise `front_relief`.
4. **Marker size and screw stick-out.** These set `marker_center_above_post` (placeholder 7 mm, the same as the table clip), which goes into the marker centres below.
5. **Are the four markers distinguishable?**
   - The posts differ by 20 mm, which is what Motive needs from the clips themselves.
   - Once all four markers are on (two clips, two column balls), check in Motive that no two marker-to-marker distances are within a few mm of each other. If two are, change one entry in `VARIANTS`.

## Regenerate

```bash
cd hardware/shelf_rod_marker
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd shelf_rod_marker.py
```

The script does the following:
- prints the hook deflection and a rough peak strain for the arms and the cradle jaws;
- checks that each part is a single valid, closed solid;
- rewrites the STEP, STL and 3MF files for A, B and the fit test;
- rewrites `shelf_rod_marker.FCStd`;
- re-renders `preview.png`;
- prints the marker centres.

Copy the new `.3mf` or `.stl` files to `~/Downloads/shelf_rod_marker_print/` by hand if you print from there.

## Printing (Bambu Studio)

1. **Fit test first.** Print `shelf_rod_marker_fit_test.3mf` (3.7 cm³) with the same settings as the clips.
   - **Rods:** press it onto a rung away from the column. It should click on with a firm thumb push, then not rattle or rock.
     - Too loose: raise `hook_preload` (0.05 mm steps).
     - Too hard to push on, or an arm cracks: lower `hook_preload`, or make `arm_thickness` thinner (e.g. 1.4).
     - If it sits crooked or rocks side to side, the gap isn't 6.2 mm: measure it at the rung you're using and set `rod_gap`.
   - **Column:** slide it to the column. The column should snap into the C, and the C should then not turn on the column.
     - Won't snap in, or a jaw cracks: lower `cradle_snap` or `cradle_wall`.
     - Turns or rattles on the column: lower `cradle_clearance` (it can go to 0) or raise `cradle_snap`.
   - Then regenerate and print the clips.
2. **Import:** open the `.3mf` (or `.stl`) in Bambu Studio.
   - The part lands in print orientation: hooks and rib on the plate, post up. Don't use auto-orient.
   - Clip A is 33 × 20 × 26 mm and clip B is 33 × 20 × 46 mm (8.5 and 10.0 cm³).
3. **No supports.**
   - Every downward face is a 45° slope, a steeper one, or the 0.8 mm bridge at the top of each arm slot.
   - If Bambu Studio still adds supports (under the wedge faces or the sloped front), turn them off.
4. **Bed adhesion:** add a **brim** (5 mm, outer only). Only the rib and the two arm bottoms touch the plate, and clip B is 46 mm tall.
5. **Strength:**
   - Filament: PETG.
   - Walls: 4 or more, so the 1.6 mm arms and 1.8 mm jaws are solid perimeters. Infill: 40–60 %, or 100 % for the stiffest part.
   - Layer height 0.16–0.2 mm. The arms and jaws flex in the layer plane, which is the strong direction.
6. **Marker screw (M3) goes in after printing.** Nothing goes in mid-print, so don't add a pause.
   - The post has a 10 mm deep, 2.5 mm pilot hole in its top.
   - Once the part is cool, drive the M3 screw straight in so it cuts its own thread. Leave enough sticking out for the marker to screw onto.
   - A drop of CA glue or thread-locker keeps the screw from turning when you screw markers on and off.
   - If markers will be swapped often, set `marker_mount = "heatset"`. That makes a 4.0 mm hole for an M3 brass heat-set insert.
7. **Removing a clip:**
   1. Pull it straight back along the rods to unsnap the column.
   2. Spread one arm with a fingernail and lift that side off the rods.

## Marker positions

Clip frame:
- The origin is on the column axis, at the height of the rod axes.
- +x runs along the rods away from the column (towards the back column), +z points up.
- The rod tops are at z = +2.5 mm.

With the current parameters, the marker centres are:

| Marker | x (mm) | y (mm) | z (mm) | Post top above rod tops |
|---|---|---|---|---|
| A | 12.0 | 0.0 | 29.5 | 20 mm |
| B | 12.0 | 0.0 | 49.5 | 40 mm |

The z values include the placeholder `marker_center_above_post` of 7 mm (open question 4). The clip is symmetric across the rods, so either clip fits the left or the right front column. If you change any parameter, re-run the script and use the marker centres it prints.
