# Real table measurements (Rodrigo, 2026-10-26)

Measured on the lab table. These replace the guesses in `table_corner_marker.py`.

| What | Value | Notes |
|---|---|---|
| Edge thickness (top surface to underside, at the edge) | 25.3 mm | |
| Rubber edge band, height | 9.8 mm | Centred on the edge face, so about 7.75 mm of bare edge above it and below it |
| Rubber edge band, protrusion | 3.5 mm | Sticks out from the edge face, visible from above |
| Rubber edge band, shape | rounded | Circular cross-section; 9.8 mm and 3.5 mm are its maximum height (at the wood) and maximum protrusion (at the crown). That makes it a circular segment of radius about 5.2 mm. Clarified by Rodrigo, 2026-10-26 |
| Corner arc length | ≈ 102 mm | Measured with a cable around the curve. For a quarter circle that's a radius of about 65 mm (102 / (π/2)). It was probably measured over the band, so the wood radius is about 61.5 mm |
| "Square part" of the corner | ≈ 80 mm | Unclear what this is. If it's the distance from the virtual sharp corner to where each edge turns straight, it doesn't agree with the arc (r = 80 would give a 126 mm arc). Treat 80 mm as the worst case: nothing should touch the edge closer than 80 mm to the virtual corner |
| Under the top near the corner | unknown | It's a flip-top folding table, so the frame and hinges are not like the Unity model. Keep the lower lip short and parametric |
| Length × width | 1370 × 680 mm | Rodrigo, 2026-10-27. Not yet clear whether this was measured over the rubber band or on the wood; over the band would make the wood 1363 × 673 mm |
| Floor to top | 750 mm | Rodrigo, 2026-10-27 |

## What the clip needs to do

- **Slide on and stay on by itself.** No thumbscrews needed for it to hold. It should be a friction or snap fit: push it onto the corner and it's secure.
  - Options to weigh: jaws slightly tighter than 25.3 mm that flex open (PETG); a groove in the inner wall that the rubber band seats into, which locks it in place.
  - The band is rubber, so it can take a little squeeze.
- **Sit the same way every time.**
  - It should rest against the table top and the two straight edges (or the band on those edges).
  - It should not rest on the rounded corner, because the radius is uncertain.
- **Marker mounts:** screw-in posts. A screw goes into the printed part and the OptiTrack ball screws onto the screw.
  - The screws are **M3** (Rodrigo, 2026-10-27).

## After the first print (Rodrigo, 2026-10-27)

- The spring-clip version was printed. Rodrigo wants a stiffer reprint so the markers can't shift relative to the table and OptiTrack always detects the rigid body.
- In his words: the lips that hang onto the table should be bigger and connected by a thick column, so the whole piece is rigid.
- So: bigger upper and lower jaws, joined by a thick solid column instead of the springy section.
- Clarified later the same day: the "thick column" means a thick member directly connecting the left jaw to the right jaw across the corner, so the two sides can't flex relative to each other. It must stay clear of the rounded corner and the band, and must not go under the table (under-table clearance still unknown). So it's a diagonal brace at roof level, just above the table top.
