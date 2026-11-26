# Shelf rod marker clip: measurements and requirements (Rodrigo, 2026-10-27)

The shelf is a wire-ladder unit. Each side is a ladder made of two vertical columns (front and back), joined by horizontal rungs. Each rung is a **pair** of parallel rods: one on each side of the column, welded to it. The photos in `reference/` show this, especially `column_rod_pair.png` and `column_top_with_ball.png`.

Overall shelf numbers are in `docs/LAB_MEASUREMENTS.md`: shelves 900 × 365 mm at 130, 620 and 990 mm; frame 1350 mm tall.

| What | Value |
|---|---|
| Vertical columns | 8 mm diameter |
| Horizontal rung rods | 5 mm diameter each, two per rung |
| Gap between the two rods of a rung | 6.2 mm (so the rod centres are 11.2 mm apart and the pair is 16.2 mm wide overall) |

## Markers already on the shelf

Rodrigo screwed two marker balls onto the columns, at different heights. They're on the threaded studs of the white plastic X-brace connectors at the tops of the columns. The two clips below add the other markers to the same rigid body.

## What the clip needs to do

- **Two clips**, each hanging on a rung (the rod pair) next to a **front** column.
- **Snap on from above:** it clips onto the two 5 mm rods and stays on by itself. A rib that drops into the 6.2 mm gap between the rods locates it sideways.
- **Slide to the column:** once on, it slides along the rods until it meets the front column.
  - Ideally it then also snaps around the 8 mm column (a C-shaped cradle at that end). That locks it against sliding and twisting, so it's rigid.
- **Marker post:** an M3 screw goes into the printed part and the ball screws onto it. Each clip's post should be a different height, and different from the two column balls, so Motive can't confuse the markers.
- **Print:** PETG on the Bambu, no supports if possible. Keep the snap features parametric so the fit can be tuned after a test print.

## Not measured yet

- **Which rung each clip goes on**, and where the column sits relative to the rod pair. From the photo, the column sits between the two rods with its axis on their centre plane; check this on the fit test.

## Answers (Rodrigo, 2026-10-27, before the first design)

- **Rods at the column:** the rods are sunk into the column (notched or flattened at the weld), so the gap stays 6.2 mm right up to it, and the column axis is on the pair's centre plane.
- **Cradle:** it grips the column **above** the rung. The clips go on a mid-height rung where the column continues at least ~15 mm above the rods.
- **Post heights:** post tops 20 mm (clip A) and 40 mm (clip B) above the rod tops.
- **M3 mount:** self-tapping pilot hole, as on the table clip.
