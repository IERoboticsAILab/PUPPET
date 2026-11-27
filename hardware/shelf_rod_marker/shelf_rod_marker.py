# Parametric OptiTrack marker clip for the rungs of the lab shelf (wire-ladder frame).
#
# Run headless with FreeCAD (writes STEP, STL and 3MF for clips A and B and a short fit
# test, a FreeCAD document with all three, and preview.png next to this file):
#   /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd shelf_rod_marker.py
#
# A rung is a pair of 5 mm rods, one either side of the 8 mm front column and sunk into it
# (Rodrigo, 2026-10-27), so the column axis lies on the pair's centre plane.
# Frame used throughout (and in README.md): the origin is on the column axis, at the height
# of the rod axes.
#   +x runs along the rods away from the column (towards the back column), +y across them,
#   +z up. The rod axes are at y = +-rod_pitch / 2, z = 0; the rod tops are at z = +2.5.
# The clip snaps onto the rods from above, slides in -x until the column snaps into the
# C-shaped cradle at its front end, and grips the column above the rung.
#   - Wedge rib: two 45 degree faces drop into the gap and rest on the inner-upper side of
#     each rod. Together they set y and z with no clearance.
#   - Hooks: one springy arm outside each rod. Its hook catches the rod's outer-lower side
#     on a face parallel to the wedge face, so each rod is clamped across its diameter.
#     The hooks sit hook_preload past the rod, so the clip has no play.
#   - Cradle: a C around the column above the rods. It stops the slide and locks the
#     clip against sliding back and twisting.
# Every downward-facing surface is a 45 degree (or steeper) slope or a short bridge, so it
# prints upright with no supports. Exported geometry is in print orientation: hooks and
# rib on the bed, post up.

import math
import os

import FreeCAD as App
import Mesh
import Part

# ---- Shelf (measured by Rodrigo 2026-10-27, see measurements.md) --------------------
column_d = 8.0               # mm, vertical ladder column
rod_d = 5.0                  # mm, each rung rod
rod_gap = 6.2                # mm, gap between the two rods of a rung
column_free_above = 15.0     # mm, column clear above the rod tops at the chosen rung (min)

# ---- Clip -------------------------------------------------------------------------
body_length = 24.0           # mm, length along the rods of the part that clamps them
front_relief = 2.0           # mm, gap from the back of the column to where the wedge and
                             #     hooks start, clear of the weld beads at the column
deck_height = 14.0           # mm, top of the clip above the rod tops (must stay below
                             #     column_free_above, the cradle grips up to here)
rib_half = 2.0               # mm, half-width of the flat-bottomed rib under the wedge. It
                             #     only carries the wedge's tip down to the bed for printing
arm_thickness = 1.6          # mm, springy arm outside each rod. Thicker = harder to snap on
arm_gap = 0.2                # mm, clearance between an arm's inner face and the rod
slot_width = 0.8             # mm, slot that frees each arm from the deck
arm_root_below_top = 4.0     # mm, solid deck above the slots; the arms hang from here
hook_preload = 0.15          # mm, how far the hook face sits past the rod (squeezed when on).
                             #     More = tighter. 0 = just touching
hook_overreach = 0.15        # mm, how far the hook tip reaches past the contact point
hook_lead_in = 60.0          # degrees from horizontal, the hook's lower (lead-in) face

# ---- Column cradle ------------------------------------------------------------------
cradle_clearance = 0.05      # mm, radial gap between the column and the cradle bore
cradle_wall = 1.8            # mm, wall of the C. Thinner = easier to snap on
cradle_snap = 0.3            # mm, how far each jaw tip reaches past the column's widest
                             #     point. More = snaps on harder and holds harder
mouth_lead = 1.5             # mm, 45 degree lead-in on each jaw tip

# ---- Marker post ------------------------------------------------------------------
# A screw goes into the top of the post and the OptiTrack marker screws onto the part of
# the screw that sticks out.
marker_screw = "M3"          # key into SCREWS (Rodrigo, 2026-10-27)
marker_mount = "tap"         # "tap" (screw threads into a pilot hole) or "heatset" (insert)
SCREWS = {                   # pilot hole, heat-set insert hole (mm)
    "M3": {"tap": 2.5, "heatset": 4.0},
    "M4": {"tap": 3.3, "heatset": 5.6},
}
post_diameter = 10.0         # mm
post_x = 12.0                # mm, post axis distance from the column axis, along the rods
mount_hole_depth = 10.0      # mm
marker_center_above_post = 7.0  # mm, marker centre above the post top. PLACEHOLDER: depends
                                #     on the marker size and how far the screw sticks out

# Post top height above the rod tops for each clip (Rodrigo, 2026-10-27: 20 and 40 mm).
VARIANTS = {"A": 20.0, "B": 40.0}

# -----------------------------------------------------------------------------------
r = rod_d / 2
rod_c = (rod_gap + rod_d) / 2        # rod axis distance from the centre plane (5.6)
rod_top = r
deck_top = rod_top + deck_height
assert deck_height < column_free_above, "cradle would run past the free column"
# Wedge face (+y side): the plane z = y - seat_c, tangent to the rod at its inner-upper
# 45 degree point. Hook face: the parallel plane z = y - hook_c, tangent at the
# outer-lower point and moved hook_preload towards the rod axis.
seat_c = rod_c - r * math.sqrt(2)
hook_c = rod_c + r * math.sqrt(2) - hook_preload * math.sqrt(2)
arm_in = rod_c + r + arm_gap
arm_out = arm_in + arm_thickness
slot_in = arm_in - slot_width
slot_top = deck_top - arm_root_below_top
tip_y = rod_c + r / math.sqrt(2) - hook_overreach
tip_z = tip_y - hook_c
z_bottom = tip_z - (arm_in - tip_y) * math.tan(math.radians(hook_lead_in))
x_start = column_d / 2 + front_relief   # where the wedge and hooks start
x_end = x_start + body_length
bore_r = column_d / 2 + cradle_clearance
cradle_r = bore_r + cradle_wall
mouth_half = column_d / 2 - cradle_snap
mouth_x = -math.sqrt(bore_r ** 2 - mouth_half ** 2)  # x of the jaw tips (inner edge)
assert slot_in - seat_c > rod_top + 1.0, "slot opens below the rod top"
assert tip_y < rod_c + r / math.sqrt(2), "hook tip must reach past the contact point"


def poly_face_yz(pts, x):
    # Closed polygon of (y, z) points as a face in the plane at x.
    vs = [App.Vector(x, y, z) for y, z in pts]
    return Part.Face(Part.makePolygon(vs + [vs[0]]))


def mirrored(half):
    # half: (y, z) points of the +y half, from the centre plane outwards and back.
    # Returns the whole closed outline, symmetric about y = 0.
    return half + [(-y, z) for y, z in reversed(half)]


def body_profile():
    # Cross-section of the rod-clamping part in (y, z), walked from the rib bottom on the
    # +y side, out over the wedge face, down the arm with its hook, and back mirrored.
    return mirrored([
        (rib_half, z_bottom),
        (rib_half, rib_half - seat_c),          # rib side up to the wedge face
        (slot_in, slot_in - seat_c),            # wedge face (rod rests here)
        (slot_in, slot_top),                    # inner wall of the slot
        (arm_in, slot_top),                     # slot top: the arm's root
        (arm_in, arm_in - hook_c),              # arm inner face down to the hook
        (tip_y, tip_z),                         # hook face (rod rests here)
        (arm_in, z_bottom),                     # lead-in face
        (arm_out, z_bottom),
        (arm_out, deck_top),
    ])


def body(x0, x1):
    return poly_face_yz(body_profile(), x0).extrude(App.Vector(x1 - x0, 0, 0))


def front(x_front):
    # Everything nearer the column than x_start: the deck in front of the wedge and the
    # cradle. Its underside is the wedge's V raised by 1 mm for every 1 mm towards the
    # column, so it clears the welds and prints without supports.
    tall = deck_top + 40.0
    v = [(-slot_in, slot_in - seat_c), (0.0, -seat_c), (slot_in, slot_in - seat_c),
         (slot_in, tall), (-slot_in, tall)]
    rise = x_start - x_front
    w0 = poly_face_yz(v, x_start).OuterWire
    w1 = poly_face_yz([(y, z + rise) for y, z in v], x_front).OuterWire
    sheared = Part.makeLoft([w0, w1], True, True)
    lo = -seat_c - 1.0
    keep = Part.makeBox(x_start - (bore_r - 0.5), 2 * slot_in, deck_top - lo,
                        App.Vector(bore_r - 0.5, -slot_in, lo))
    keep = keep.fuse(Part.makeCylinder(cradle_r, deck_top - lo, App.Vector(0, 0, lo)))
    clip_box = Part.makeBox(x_start - x_front, 2 * slot_in, deck_top - lo,
                            App.Vector(x_front, -slot_in, lo))
    return sheared.common(clip_box).common(keep)


def cradle_cut():
    # The bore for the column, and the mouth of the C with a 45 degree lead-in.
    lo, hi = z_bottom - 1, deck_top + 1
    cut = Part.makeCylinder(bore_r, hi - lo, App.Vector(0, 0, lo))
    out = cradle_r + 2.0
    m = [(0.0, mouth_half), (mouth_x, mouth_half), (mouth_x - mouth_lead, mouth_half + mouth_lead),
         (-out, mouth_half + mouth_lead), (-out, -mouth_half - mouth_lead),
         (mouth_x - mouth_lead, -mouth_half - mouth_lead), (mouth_x, -mouth_half), (0.0, -mouth_half)]
    vs = [App.Vector(x, y, lo) for x, y in m]
    mouth = Part.Face(Part.makePolygon(vs + [vs[0]])).extrude(App.Vector(0, 0, hi - lo))
    return cut.fuse(mouth)


def build(post_top_above_rod=None, length=body_length):
    shape = body(x_start, x_start + length).fuse(front(-cradle_r - 1.0))
    shape = shape.cut(cradle_cut())
    if post_top_above_rod is not None:
        top = rod_top + post_top_above_rod
        assert top - mount_hole_depth > slot_top - 1.0, "post too short for the screw hole"
        shape = shape.fuse(Part.makeCylinder(post_diameter / 2, top - deck_top + 1.0,
                                             App.Vector(post_x, 0, deck_top - 1.0)))
        d = SCREWS[marker_screw][marker_mount]
        shape = shape.cut(Part.makeCylinder(d / 2, mount_hole_depth + 1,
                                            App.Vector(post_x, 0, top - mount_hole_depth)))
    return shape.removeSplitter()


def build_fit_test():
    # The whole cross-section and the cradle, with a short body and no post: print it
    # first to check both snaps before printing the clips.
    return build(None, 10.0)


def marker_center(variant):
    return (post_x, 0.0, rod_top + VARIANTS[variant] + marker_center_above_post)


def snap_strains():
    # Rough peak bending strain while snapping on (cantilever: 1.5 t d / L^2). PETG
    # yields at about 4 %; keep these under about 2 % so the arms survive repeated use.
    arm_len = slot_top - tip_z
    arm_defl = rod_c + r - tip_y
    arm = 1.5 * arm_thickness * arm_defl / arm_len ** 2
    jaw_len = (cradle_r + bore_r) / 2 * (math.pi - math.acos(bore_r / cradle_r) - math.asin(mouth_half / bore_r))
    jaw = 1.5 * cradle_wall * cradle_snap / jaw_len ** 2
    return arm, arm_defl, jaw


def rods_and_column(x0, x1, z_top):
    # Reference geometry for the preview only.
    rods = [Part.makeCylinder(r, x1 - x0, App.Vector(x0, s * rod_c, 0), App.Vector(1, 0, 0)) for s in (1, -1)]
    col = Part.makeCylinder(column_d / 2, z_top + 15, App.Vector(0, 0, -15))
    return rods + [col]


def slice_polys(shape, normal, offset, to2d):
    return [[to2d(v) for v in w.discretize(200)] for w in shape.slice(normal, offset)]


def write_preview(shapes, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon, Rectangle
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    blue, steel = (0.6, 0.7, 0.85), (0.8, 0.8, 0.8)
    fig = plt.figure(figsize=(18, 12))
    grid = fig.add_gridspec(2, 6)
    light = App.Vector(-0.4, -0.6, 0.7).normalize()

    def shaded(ax, shape, color, alpha=1.0):
        pts, tris = shape.tessellate(0.1)
        verts = [[(pts[a].x, pts[a].y, pts[a].z) for a in t] for t in tris]
        cols = []
        for p0, p1, p2 in verts:
            n = (App.Vector(*p1) - App.Vector(*p0)).cross(App.Vector(*p2) - App.Vector(*p0))
            k = 0.35 + 0.65 * abs(n.normalize().dot(light)) if n.Length > 0 else 0.35
            cols.append((color[0] * k, color[1] * k, color[2] * k, alpha))
        ax.add_collection3d(Poly3DCollection(verts, facecolors=cols, edgecolor="none"))

    for i, (v, shape) in enumerate(shapes.items()):
        ax = fig.add_subplot(grid[0, 3 * i:3 * i + 3], projection="3d")
        for ref in rods_and_column(-12, x_end + 8, deck_top):
            shaded(ax, ref, steel, 0.35)
        shaded(ax, shape, blue)
        x, y, z = marker_center(v)
        ax.scatter([x], [y], [z], color="orange", s=120)
        ax.scatter([0], [0], [0], color="red", s=30)
        ax.text(x, y, z + 6, "%s marker" % v, fontsize=9)
        lo, hi = -14, x_end + 10
        ax.set_xlim(lo, hi), ax.set_ylim(-(hi - lo) / 2, (hi - lo) / 2), ax.set_zlim(z_bottom - 4, z_bottom - 4 + hi - lo)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=24, azim=-60)
        ax.set_xlabel("x along rods (mm)"), ax.set_ylabel("y (mm)"), ax.set_zlabel("z (mm)")
        ax.set_title("Clip %s on the rung (grey: rods and column; red: origin)" % v)

    fit = build_fit_test()

    def rods_yz(ax):
        for s in (1, -1):
            ax.add_patch(Circle((s * rod_c, 0), r, facecolor=steel, edgecolor="0.3", alpha=0.8))

    # Cross-section across the rods, through the clamping part.
    ax = fig.add_subplot(grid[1, 0:2])
    for poly in slice_polys(fit, App.Vector(1, 0, 0), x_start + 5.0, lambda p: (p.y, p.z)):
        ax.add_patch(Polygon(poly, closed=True, facecolor=blue, edgecolor="k"))
    rods_yz(ax)
    for s in (1, -1):
        for a in (135, -45):
            ax.plot([s * (rod_c + r * math.cos(math.radians(a)))], [r * math.sin(math.radians(a))], "o", color="green")
    ax.set_xlim(-arm_out - 3, arm_out + 3), ax.set_ylim(z_bottom - 2, deck_top + 2)
    ax.set_aspect("equal")
    ax.set_xlabel("y (mm)"), ax.set_ylabel("z (mm)")
    ax.set_title("Section across the rods (green: contact points;\n"
                 "the hooks overlap the rods by the %.2f mm preload)" % hook_preload)

    # Plan section through the cradle, above the rods.
    ax = fig.add_subplot(grid[1, 2:4])
    zc = deck_top - 2.0
    for poly in slice_polys(fit, App.Vector(0, 0, 1), zc, lambda p: (p.x, p.y)):
        ax.add_patch(Polygon(poly, closed=True, facecolor=blue, edgecolor="k"))
    ax.add_patch(Circle((0, 0), column_d / 2, facecolor=steel, edgecolor="0.3", alpha=0.8, label="column"))
    for s in (1, -1):
        ax.add_patch(Rectangle((-10, s * rod_c - r), x_start + 14, rod_d, facecolor=steel,
                               edgecolor="0.6", alpha=0.3, ls="--"))
    ax.annotate("slide this way", (-9, rod_c + 5), (0, rod_c + 5), fontsize=8,
                arrowprops=dict(arrowstyle="->"))
    ax.set_xlim(-12, x_start + 12), ax.set_ylim(-arm_out - 3, arm_out + 6)
    ax.set_aspect("equal")
    ax.set_xlabel("x (mm)"), ax.set_ylabel("y (mm)")
    ax.set_title("Plan section %.1f mm above the rod tops: the cradle\n"
                 "(rods below, dashed)" % (zc - rod_top))

    # Side section on the centre plane.
    ax = fig.add_subplot(grid[1, 4:6])
    for poly in slice_polys(fit, App.Vector(0, 1, 0), 0.0, lambda p: (p.x, p.z)):
        ax.add_patch(Polygon(poly, closed=True, facecolor=blue, edgecolor="k"))
    ax.add_patch(Rectangle((-column_d / 2, z_bottom - 2), column_d, deck_top + 6 - z_bottom,
                           facecolor=steel, edgecolor="0.3", alpha=0.8))
    ax.add_patch(Rectangle((-10, -r), x_start + 24, rod_d, facecolor=steel, edgecolor="0.6",
                           alpha=0.3, ls="--"))
    ax.set_xlim(-10, x_start + 12), ax.set_ylim(z_bottom - 2, deck_top + 4)
    ax.set_aspect("equal")
    ax.set_xlabel("x (mm)"), ax.set_ylabel("z (mm)")
    ax.set_title("Side section on the centre plane: wedge, sloped\nunderside and column "
                 "(rods behind, dashed)")

    fig.tight_layout()
    fig.savefig(path, dpi=80)


def export(shape, here, name):
    # STEP for CAD, STL and 3MF for the slicer (Bambu Studio opens either).
    assert shape.isValid() and shape.isClosed() and len(shape.Solids) == 1 and shape.Volume > 0, \
        "%s invalid" % name
    step = os.path.join(here, "%s.step" % name)
    stl = os.path.join(here, "%s.stl" % name)
    shape.exportStep(step)
    mesh = Mesh.Mesh(shape.tessellate(0.02))
    mesh.write(stl)
    mesh.write(os.path.join(here, "%s.3mf" % name))
    b = shape.BoundBox
    print("%s: volume %.2f cm3, %.1f x %.1f x %.1f mm, mesh solid=%s, wrote .step .stl .3mf"
          % (name, shape.Volume / 1000, b.XLength, b.YLength, b.ZLength, Mesh.Mesh(stl).isSolid()))


def save_document(parts, path):
    # One FreeCAD document holding every exported part, to open and inspect in the GUI.
    doc = App.newDocument("shelf_rod_marker")
    for name, shape in parts.items():
        doc.addObject("Part::Feature", name).Shape = shape
    doc.recompute()
    doc.saveAs(path)
    App.closeDocument(doc.Name)


if __name__ in ("__main__", "shelf_rod_marker"):
    here = os.path.dirname(os.path.abspath(__file__))
    arm, arm_defl, jaw = snap_strains()
    print("arm deflects %.2f mm snapping on, peak strain ~%.1f %%; cradle jaw strain ~%.1f %%"
          % (arm_defl, arm * 100, jaw * 100))
    print("bed at z=%.2f, rod tops at z=%.2f, deck top at z=%.2f" % (z_bottom, rod_top, deck_top))
    shapes = {}
    for v in VARIANTS:
        shapes[v] = build(VARIANTS[v])
        export(shapes[v], here, "shelf_rod_marker_%s" % v)
        x, y, z = marker_center(v)
        print("  marker %s centre (clip frame): x=%.1f y=%.1f z=%.1f mm" % (v, x, y, z))
    fit_test = build_fit_test()
    export(fit_test, here, "shelf_rod_marker_fit_test")
    parts = {"clip_%s" % v: shape for v, shape in shapes.items()}
    parts["fit_test"] = fit_test
    save_document(parts, os.path.join(here, "shelf_rod_marker.FCStd"))
    print("wrote shelf_rod_marker.FCStd")
    write_preview(shapes, os.path.join(here, "preview.png"))
    print("wrote preview.png")
