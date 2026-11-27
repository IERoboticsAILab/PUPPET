# Parametric OptiTrack marker clip for the corners of the PUPPET table.
#
# Run headless with FreeCAD (writes STEP, STL and 3MF for variants A and B and a one-jaw
# fit test, a FreeCAD document with all three, and preview.png next to this file):
#   /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd table_corner_marker.py
#
# Frame used throughout (and in README.md): the origin is the Motive pivot, i.e. the table's
# sharp top corner (where the two straight wooden edge faces would meet if the corner were
# not rounded), at the top surface.
#   +x runs along one table edge, +y along the other, +z points up; the wood occupies
#   x >= 0, y >= 0, -table_top_thickness <= z <= 0. The rubber edge band sticks out past
#   x = 0 / y = 0 by band_protrusion.
# The clip is a rigid slide-on clip with no screws and no springy parts: each jaw is a
# C-channel (upper roof and lower lip joined by a thick solid column). It touches the table
# only on:
#   - the top surface (roof),
#   - the bare wood of each straight edge face above and below the band (the band sits,
#     with clearance, in a rounded groove in the column),
#   - the underside, with small crush ribs on top of the lower lip. The ribs are a little
#     taller than the gap, so they deform slightly as the clip is pushed on and take out
#     the play without anything having to flex,
# and only from contact_start along each edge. A thick diagonal brace runs from one jaw's
# roof to the other's across the corner, just above the table top, so the two jaws and the
# corner wall form a rigid triangle and can't flex relative to each other. Nearer the corner the clip stands clear of
# the wood and band by corner_clearance whatever the corner radius is, so the rounded
# corner never sets the pose.
# Exported geometry is already in print orientation: lower lips on the bed, posts up.

import os

import FreeCAD as App
import Mesh
import Part

# ---- Table (measured by Rodrigo 2026-10-26, see measurements.md) --------------------
table_top_thickness = 25.3   # mm, top surface to underside at the edge
# The rubber edge band has a rounded (circular-segment) cross-section: band_height is its
# height where it meets the wood, band_protrusion how far its crown sticks out.
band_height = 9.8            # mm, rubber edge band, vertical, at the wood
band_top_below_surface = (table_top_thickness - band_height) / 2  # mm, ASSUMED centred
band_protrusion = 3.5        # mm, how far the crown sticks out past the wooden edge face
no_contact_from_corner = 80.0  # mm, worst case for where the straight edge starts (the
                               #     unclear 80 mm "square part"); nothing touches nearer

# ---- Clip -------------------------------------------------------------------------
contact_start = no_contact_from_corner + 5.0  # mm, jaws start this far along each edge
jaw_length = 50.0            # mm, length of each jaw along its edge
roof_thickness = 6.0         # mm, upper jaw (roof) resting on the table top
roof_reach = 15.0            # mm, how far the roof reaches in over the table top
lip_thickness = 6.0          # mm, lower jaw (lip) under the table top
lip_width = 15.0             # mm, how far the lip reaches in under the table top
lead_in = 1.5                # mm, chamfer on the roof and lip edges so the jaw slides on
jaw_clearance = 0.3          # mm, gap between the lip's flat top and the table underside
rib_crush = 0.15             # mm, how far the crush ribs reach past the underside (squashed
                             #     when the clip goes on). More = tighter
rib_count = 4                # crush ribs per jaw, spread along it, running across the lip
rib_width = 1.5              # mm, rib width along the edge
rib_ramp = 2.0               # mm, ramp on the inner end of each rib so it rides on
groove_clearance = 1.0       # mm, the groove is the band's arc grown by this much. Keep it
                             #     positive: squeezing a round band pushes the wall off the
                             #     wood, and the wall on the wood is what sets x and y
wall_out = 14.0              # mm, outer face of the solid column joining roof and lip,
                             #     measured out from the wooden edge face
corner_clearance = 1.5       # mm, gap to the band (and so the wood) before contact_start
brace_width = 16.0           # mm, width of the diagonal brace seen from above
brace_thickness = 9.0        # mm, height of the brace
brace_clearance = 1.0        # mm, brace underside above the table top (it touches nothing)
brace_inward = roof_reach / 2  # mm, where the brace centreline meets each jaw roof, measured
                               #     in from the wooden edge face

# ---- Marker posts -----------------------------------------------------------------
# A screw goes into the top of each post and the OptiTrack marker screws onto the part of
# the screw that sticks out.
marker_screw = "M3"          # key into SCREWS (Rodrigo, 2026-10-27)
marker_mount = "tap"         # "tap" (screw threads into a pilot hole) or "heatset" (insert)
SCREWS = {                   # pilot hole, heat-set insert hole (mm)
    "M3": {"tap": 2.5, "heatset": 4.0},
    "M4": {"tap": 3.3, "heatset": 5.6},
}
post_diameter = 12.0         # mm
post_overlap = 3.0           # mm, how far the post cylinder sinks into the column
mount_hole_depth = 10.0      # mm
marker_center_above_post = 7.0  # mm, marker centre above the post top. PLACEHOLDER: depends
                                #     on the marker size and how far the screw sticks out

# Posts sit OUTSIDE the clip's outer wall as full-height pillars (no overhangs when
# printed). Each post: (edge, distance along that edge from the pivot, height of the post
# top above the table top surface).
# edge "x" = post on the y = 0 edge (runs along +x); edge "y" = post on the x = 0 edge.
# Heights are all different (A: 35/60, B: 50/25) and the along-edge distances differ, so
# two clips on diagonally opposite corners form one 4-marker rigid body with no
# symmetric ambiguity.
VARIANTS = {
    "A": [("y", 50.0, 35.0), ("x", 100.0, 60.0)],
    "B": [("y", 30.0, 50.0), ("x", 115.0, 25.0)],
}

# -----------------------------------------------------------------------------------
gap = table_top_thickness + jaw_clearance           # roof underside to the lip's flat top
z_bottom = -gap - lip_thickness
rib_top = -table_top_thickness + rib_crush
band_radius = (band_height ** 2 / 4 + band_protrusion ** 2) / (2 * band_protrusion)
band_center = (band_protrusion - band_radius, -band_top_below_surface - band_height / 2)  # (n, z)
groove_radius = band_radius + groove_clearance
groove_depth = band_protrusion + groove_clearance
groove_half = (groove_radius ** 2 - band_center[0] ** 2) ** 0.5  # half the groove mouth height
skirt_in = band_protrusion + corner_clearance     # inner face of the wall before contact_start
assert wall_out - groove_depth >= 3.0 and wall_out - skirt_in >= 3.0, "wall_out too thin"
arm_end = contact_start + jaw_length


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, App.Vector(x0, y0, z0))


def both_edges(make):
    # make(a0, a1, n0, n1, z0, z1) is a box along the y = 0 edge: a = along x, n = outward
    # distance from the wooden face (so y = -n). Returns it fused with its mirror on x = 0.
    def on_x(a0, a1, n0, n1, z0, z1):
        return box(a0, a1, -n1, -n0, z0, z1)

    def on_y(a0, a1, n0, n1, z0, z1):
        return box(-n1, -n0, a0, a1, z0, z1)

    return make(on_x).fuse(make(on_y))


def profile_edges(prof, to3d):
    # prof is a closed list of (n, z) points; an entry ("arc", (n, z)) means a circular arc
    # through that point from the previous point to the next one.
    edges, i = [], 0
    while i < len(prof):
        p0 = prof[i]
        if prof[(i + 1) % len(prof)][0] == "arc":
            mid, p1 = prof[i + 1][1], prof[(i + 2) % len(prof)]
            edges.append(Part.Arc(to3d(*p0), to3d(*mid), to3d(*p1)).toShape())
            i += 2
        else:
            edges.append(Part.LineSegment(to3d(*p0), to3d(*prof[(i + 1) % len(prof)])).toShape())
            i += 1
    return edges


def profile_points(prof, steps=24):
    # The same profile as a plain polygon (arcs split into segments), for plotting.
    out = []
    for e in profile_edges(prof, lambda n, z: App.Vector(n, z, 0)):
        out += [(v.x, v.y) for v in e.discretize(steps if e.Curve.TypeId == "Part::GeomCircle" else 2)[:-1]]
    return out


def section_prism(prof, a0, a1, edge):
    # Extrude a closed (n, z) profile along an edge from a0 to a1.
    def p(n, z):
        return App.Vector(a0, -n, z) if edge == "x" else App.Vector(-n, a0, z)

    face = Part.Face(Part.Wire(profile_edges(prof, p)))
    d = App.Vector(a1 - a0, 0, 0) if edge == "x" else App.Vector(0, a1 - a0, 0)
    return face.extrude(d)


def jaw_profile():
    # Cross-section of a jaw in (n, z): roof, solid column with the rounded groove for the
    # band, and lip, with lead-in chamfers. Walk it starting at the bottom. The crush ribs
    # are added in jaw().
    nc, zc = band_center
    return [
        (wall_out, z_bottom),
        (wall_out, roof_thickness),
        (-roof_reach, roof_thickness),
        (-roof_reach, lead_in),                    # roof lead-in
        (-roof_reach + lead_in, 0.0),
        (0.0, 0.0),                                # roof rests on the top surface
        (0.0, zc + groove_half),                   # wall on the bare wood above the band
        ("arc", (groove_depth, zc)),               # groove following the band's arc
        (0.0, zc - groove_half),                   # wall on the bare wood below the band
        (0.0, -gap),
        (-lip_width + lead_in, -gap),              # lip under the top
        (-lip_width, -gap - lead_in),
        (-lip_width, z_bottom),
    ]


def rib_profile():
    # Cross-section of a crush rib on top of the lip, running from the lip's inner edge to
    # the column. The table edge rides up the ramp at the inner end as the clip goes on.
    start = -lip_width + lead_in
    return [(start, -gap), (0.0, -gap), (0.0, rib_top), (start + rib_ramp, rib_top)]


def rib_positions(a0, a1):
    pitch = (a1 - a0) / rib_count
    return [a0 + (i + 0.5) * pitch for i in range(rib_count)]


def jaw(edge, a0, a1):
    body = section_prism(jaw_profile(), a0, a1, edge)
    for a in rib_positions(a0, a1):
        body = body.fuse(section_prism(rib_profile(), a - rib_width / 2, a + rib_width / 2, edge))
    return body


def corner_skirt():
    # Everything nearer the corner than contact_start: a full-height L wall that ties the two
    # jaws together and touches nothing. The table and band (any corner radius) lie inside
    # the sharp quadrant x, y >= -band_protrusion, so a wall outside that clears them. It has
    # no roof over the table, so it prints with no overhang.
    return both_edges(lambda b: b(-wall_out, contact_start, skirt_in, wall_out, z_bottom, roof_thickness))


def brace():
    # A straight bar across the corner from the middle of one jaw's roof to the middle of
    # the other's, sitting brace_clearance above the table top. Each end runs on into its
    # roof so it is fused over its full width.
    a = contact_start + jaw_length / 2
    p1, p2 = App.Vector(a, brace_inward, 0), App.Vector(brace_inward, a, 0)
    d = p2 - p1
    d.normalize()
    side = App.Vector(-d.y, d.x, 0) * (brace_width / 2)
    run_on = d * (brace_width / 2)
    q1, q2 = p1 - run_on, p2 + run_on
    z0 = brace_clearance
    pts = [q1 - side, q2 - side, q2 + side, q1 + side]
    face = Part.Face(Part.makePolygon([p + App.Vector(0, 0, z0) for p in pts + pts[:1]]))
    return face.extrude(App.Vector(0, 0, brace_thickness))


def post_center(edge, along):
    off = -wall_out - post_diameter / 2 + post_overlap
    return (along, off) if edge == "x" else (off, along)


def build(variant):
    body = corner_skirt().fuse(brace())
    for edge in ("x", "y"):
        body = body.fuse(jaw(edge, contact_start, arm_end))
    holes = []
    d = SCREWS[marker_screw][marker_mount]
    for edge, along, height in VARIANTS[variant]:
        cx, cy = post_center(edge, along)
        body = body.fuse(Part.makeCylinder(post_diameter / 2, height - z_bottom, App.Vector(cx, cy, z_bottom)))
        holes.append(Part.makeCylinder(d / 2, mount_hole_depth + 1, App.Vector(cx, cy, height - mount_hole_depth)))
    for h in holes:
        body = body.cut(h)
    return body.removeSplitter()


def build_fit_test():
    # One whole jaw (crush ribs included): print it first and push it onto a straight edge
    # to check the grip and the groove before printing a whole clip.
    return jaw("x", 0.0, jaw_length).removeSplitter()


def marker_centers(variant):
    out = []
    for i, (edge, along, height) in enumerate(VARIANTS[variant], 1):
        cx, cy = post_center(edge, along)
        out.append(("%s%d" % (variant, i), cx, cy, height + marker_center_above_post))
    return out


def slice_polys(shape, normal, offset, to2d):
    # Cut shape with the plane normal . p = offset; returns each section outline as 2D points.
    return [[to2d(v) for v in w.discretize(200)] for w in shape.slice(normal, offset)]


def write_preview(shapes, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Arc, Polygon, Rectangle
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    blue, wood = (0.6, 0.7, 0.85), (0.85, 0.75, 0.6)
    fig = plt.figure(figsize=(18, 12))
    grid = fig.add_gridspec(2, 6)

    for i, (v, shape) in enumerate(shapes.items()):
        ax = fig.add_subplot(grid[0, 2 * i:2 * i + 2], projection="3d")
        pts, tris = shape.tessellate(0.2)
        verts = [[(pts[a].x, pts[a].y, pts[a].z) for a in t] for t in tris]
        light = App.Vector(-0.4, -0.6, 0.7).normalize()
        colors = []
        for p0, p1, p2 in verts:
            n = (App.Vector(*p1) - App.Vector(*p0)).cross(App.Vector(*p2) - App.Vector(*p0))
            k = 0.35 + 0.65 * abs(n.normalize().dot(light)) if n.Length > 0 else 0.35
            colors.append((blue[0] * k, blue[1] * k, blue[2] * k))
        ax.add_collection3d(Poly3DCollection(verts, facecolors=colors, edgecolor="none"))
        # Table outline (wood top edge, straight parts only) for reference.
        for xs, ys in [((contact_start, arm_end + 10), (0, 0)), ((0, 0), (contact_start, arm_end + 10))]:
            ax.plot(xs, ys, [0, 0], color="0.4", lw=1, ls="--")
        ax.scatter([0], [0], [0], color="red", s=30)
        for name, x, y, z in marker_centers(v):
            ax.scatter([x], [y], [z], color="orange", s=60)
            ax.text(x, y, z + 6, name, fontsize=9)
        lo, hi = -wall_out - post_diameter - 5, arm_end + 5
        ax.set_xlim(lo, hi), ax.set_ylim(lo, hi), ax.set_zlim(z_bottom - 5, z_bottom - 5 + hi - lo)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=28, azim=-135)
        ax.set_xlabel("x (mm)"), ax.set_ylabel("y (mm)"), ax.set_zlabel("z (mm)")
        ax.set_title("Variant %s (seen from outside the corner; red = pivot)" % v)

    # Top view: where the clip touches the edges, and possible corner radii.
    ax = fig.add_subplot(grid[0, 4:6])
    shp = next(iter(shapes.values()))
    pts, tris = shp.tessellate(0.5)
    for t in tris:
        tri = [(pts[a].x, pts[a].y) for a in t]
        ax.add_patch(Polygon(tri, closed=True, facecolor=blue, edgecolor="none"))
    for r, style, lab in [(61.5, "-", "wood corner r = 61.5 (from the 102 mm arc)"),
                          (no_contact_from_corner, ":", "r = 80 (worst case)")]:
        ax.add_patch(Arc((r, r), 2 * r, 2 * r, theta1=180, theta2=270, color="0.3", ls=style, label=lab))
        ax.plot([r, arm_end + 15], [0, 0], color="0.3", ls=style)
        ax.plot([0, 0], [r, arm_end + 15], color="0.3", ls=style)
    for edge in ("x", "y"):
        a = (contact_start, arm_end)
        xs, ys = (a, (0, 0)) if edge == "x" else ((0, 0), a)
        ax.plot(xs, ys, color="green", lw=4, solid_capstyle="butt",
                label="edge contact (jaws)" if edge == "x" else None)
    ax.plot([0], [0], "o", color="red")
    lo = -wall_out - post_diameter - 3
    ax.set_xlim(lo, arm_end + 15), ax.set_ylim(lo, arm_end + 15)
    ax.set_aspect("equal")
    ax.set_xlabel("x (mm)"), ax.set_ylabel("y (mm)")
    ax.set_title("Top view: contact only on the straight edges")
    ax.legend(loc="upper right", fontsize=8)

    # Both sections are cut from one jaw (the fit-test part, which runs along x from 0).
    jaw_shape = build_fit_test()
    T = table_top_thickness

    # Cross-section through a crush rib, with the table edge and band.
    ax = fig.add_subplot(grid[1, 0:3])
    for poly in slice_polys(jaw_shape, App.Vector(1, 0, 0), rib_positions(0.0, jaw_length)[0], lambda v: (-v.y, v.z)):
        ax.add_patch(Polygon(poly, closed=True, facecolor=blue, edgecolor="k"))
    ax.add_patch(Rectangle((-20, -T), 20, T, facecolor=wood, edgecolor="0.3", alpha=0.6, label="table top (wood)"))
    band = [(0.0, -band_top_below_surface), ("arc", (band_protrusion, band_center[1])),
            (0.0, -band_top_below_surface - band_height)]
    ax.add_patch(Polygon(profile_points(band), closed=True, facecolor="0.15", alpha=0.7, label="rubber band"))
    ax.plot([0], [0], "o", color="red", label="pivot")
    ax.set_xlim(-20, wall_out + 4), ax.set_ylim(z_bottom - 3, roof_thickness + 3)
    ax.set_aspect("equal")
    ax.set_xlabel("distance out from the wooden edge face (mm)"), ax.set_ylabel("z (mm)")
    ax.set_title("Jaw section through a crush rib (the rib overlaps the wood by %.2f mm,\n"
                 "which is squashed when the clip goes on)" % rib_crush)
    ax.legend(loc="lower right", fontsize=8)

    # Side view of the jaw, cut through the lip.
    ax = fig.add_subplot(grid[1, 3:6])
    for poly in slice_polys(jaw_shape, App.Vector(0, 1, 0), lip_width / 2, lambda v: (v.x, v.z)):
        ax.add_patch(Polygon(poly, closed=True, facecolor=blue, edgecolor="k"))
    ax.add_patch(Rectangle((-5, -T), jaw_length + 10, T, facecolor=wood, edgecolor="0.3", alpha=0.6))
    ax.annotate("roof", (jaw_length / 2, roof_thickness / 2 - 1), ha="center", fontsize=9)
    ax.annotate("lip", (jaw_length / 2, z_bottom + 1.5), ha="center", fontsize=9)
    for a in rib_positions(0.0, jaw_length):
        ax.annotate("rib", (a, rib_top + 1), ha="center", fontsize=8)
    ax.set_xlim(-5, jaw_length + 5), ax.set_ylim(z_bottom - 3, roof_thickness + 3)
    ax.set_aspect("equal")
    ax.set_xlabel("along the edge, from the corner end of the jaw (mm)"), ax.set_ylabel("z (mm)")
    ax.set_title("Jaw side view, cut %.1f mm in under the table (corner end on the left)" % (lip_width / 2))

    fig.tight_layout()
    fig.savefig(path, dpi=80)


def export(shape, here, name):
    # STEP for CAD, STL and 3MF for the slicer (Bambu Studio opens either).
    assert shape.isValid() and shape.isClosed() and shape.Volume > 0, "%s invalid" % name
    step = os.path.join(here, "%s.step" % name)
    stl = os.path.join(here, "%s.stl" % name)
    shape.exportStep(step)
    mesh = Mesh.Mesh(shape.tessellate(0.05))
    mesh.write(stl)
    mesh.write(os.path.join(here, "%s.3mf" % name))
    print("%s: volume %.1f cm3, mesh solid=%s, wrote .step .stl .3mf"
          % (name, shape.Volume / 1000, Mesh.Mesh(stl).isSolid()))


def save_document(parts, path):
    # One FreeCAD document holding every exported part, to open and inspect in the GUI.
    doc = App.newDocument("table_corner_marker")
    for name, shape in parts.items():
        doc.addObject("Part::Feature", name).Shape = shape
    doc.recompute()
    doc.saveAs(path)
    App.closeDocument(doc.Name)


if __name__ in ("__main__", "table_corner_marker"):
    here = os.path.dirname(os.path.abspath(__file__))
    shapes = {}
    for v in VARIANTS:
        shapes[v] = build(v)
        export(shapes[v], here, "table_corner_marker_%s" % v)
        b = shapes[v].BoundBox
        print("  footprint %.1f x %.1f mm, height %.1f mm" % (b.XLength, b.YLength, b.ZLength))
        for name, x, y, z in marker_centers(v):
            print("  marker %s centre (pivot frame): x=%.1f y=%.1f z=%.1f mm" % (name, x, y, z))
    fit_test = build_fit_test()
    export(fit_test, here, "table_corner_marker_fit_test")
    parts = {"clip_%s" % v: shape for v, shape in shapes.items()}
    parts["fit_test"] = fit_test
    save_document(parts, os.path.join(here, "table_corner_marker.FCStd"))
    print("wrote table_corner_marker.FCStd")
    write_preview(shapes, os.path.join(here, "preview.png"))
    print("wrote preview.png")
