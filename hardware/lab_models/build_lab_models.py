"""Builds the lab table and shelf as FBX models for the Unity scene, from docs/LAB_MEASUREMENTS.md.

  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python hardware/lab_models/build_lab_models.py

Writes unity/PUPPET_Unity/Assets/LabModels/{lab_table,lab_shelf}.fbx and preview PNGs next to this
script. Units are metres. Each model's origin is on the floor, under the centre of the top/shelves.
In Blender the front (the edge the marker clips go on) faces -Y; after export it faces -Z in Unity.

Measured values are marked "measured". The rest (legs, ladder rods) is approximate and only affects
how the furniture looks, not where the tracked surfaces are.
"""
import math
import os

import bpy
import bmesh
import mathutils

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT_DIR = os.path.join(REPO, "unity", "PUPPET_Unity", "Assets", "LabModels")
mm = 0.001

# ---- Table (measured) ------------------------------------------------------------------
TABLE_L = 1370 * mm
TABLE_W = 680 * mm
TABLE_TOP_Z = 750 * mm
TABLE_EDGE = 25.3 * mm
TABLE_CORNER_R = 62 * mm  # wood radius; ~65 mm over the rubber band
BAND_H = 9.8 * mm
BAND_OUT = 3.5 * mm
# approximate: T-legs on castors
LEG_INSET = 150 * mm
LEG_SIZE = 60 * mm
FOOT_LEN = 600 * mm
FOOT_H = 40 * mm
CASTOR_D = 60 * mm

# ---- Shelf (measured) ------------------------------------------------------------------
SHELF_L = 900 * mm
SHELF_D = 365 * mm
SHELF_TOPS = [130 * mm, 620 * mm, 990 * mm]
FRAME_TOP = 1350 * mm
FACE_H = 25.8 * mm
RETURN = 17.1 * mm
SHEET = 0.9 * mm
LADDER_GAP = 8.75 * mm  # shelf end face to upright centre (OptiTrack: column tops 917.5 mm apart)
UPRIGHT_D = 8 * mm  # measured
RUNG_D = 5 * mm  # measured; each rung is a pair of rods, one either side of the columns
RUNG_PITCH = 11.2 * mm  # measured: 6.2 mm gap between the two rods
UPRIGHT_INSET = 21.4 * mm  # upright centre in from the shelf's front/back face (OptiTrack: 322.2 mm apart)
FOOT_PAD_D = 40 * mm
FOOT_PAD_H = 15 * mm


def material(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    return m


def box(name, size, center, mat, parent):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    o.parent = parent
    return o


def rod(name, a, b, d, mat, parent):
    a, b = mathutils.Vector(a), mathutils.Vector(b)
    v = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=d / 2, depth=v.length, location=(a + b) / 2)
    o = bpy.context.object
    o.name = name
    o.rotation_euler = v.to_track_quat("Z", "Y").to_euler()
    bpy.ops.object.transform_apply(rotation=True)
    o.data.materials.append(mat)
    o.parent = parent
    return o


def rounded_slab(name, length, width, radius, z0, z1, mat, parent, segments=12):
    """Rectangle with rounded corners, extruded from z0 to z1."""
    bm = bmesh.new()
    pts = []
    for cx, cy, a0 in [(1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)]:
        c = (cx * (length / 2 - radius), cy * (width / 2 - radius))
        for i in range(segments + 1):
            a = math.radians(a0 + 90 * i / segments)
            pts.append((c[0] + radius * math.cos(a), c[1] + radius * math.sin(a)))
    bottom = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(list(reversed(bottom)))
    bm.faces.new(top)
    n = len(pts)
    for i in range(n):
        bm.faces.new([bottom[i], bottom[(i + 1) % n], top[(i + 1) % n], top[i]])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(mat)
    o.parent = parent
    return o


def root(name):
    o = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(o)
    return o


def build_table():
    white = material("table_white", (0.92, 0.92, 0.9))
    grey = material("table_band", (0.35, 0.35, 0.35))
    dark = material("table_castor", (0.1, 0.1, 0.1))
    r = root("lab_table")
    z1 = TABLE_TOP_Z
    z0 = z1 - TABLE_EDGE
    rounded_slab("top", TABLE_L, TABLE_W, TABLE_CORNER_R, z0, z1, white, r)
    zm = (z0 + z1) / 2
    rounded_slab("edge_band", TABLE_L + 2 * BAND_OUT, TABLE_W + 2 * BAND_OUT, TABLE_CORNER_R + BAND_OUT,
                 zm - BAND_H / 2, zm + BAND_H / 2, grey, r)
    for sx in (-1, 1):
        x = sx * (TABLE_L / 2 - LEG_INSET)
        box(f"leg_{sx}", (LEG_SIZE, LEG_SIZE, z0 - FOOT_H - CASTOR_D), (x, 0, (z0 + FOOT_H + CASTOR_D) / 2), white, r)
        box(f"foot_{sx}", (LEG_SIZE, FOOT_LEN, FOOT_H), (x, 0, CASTOR_D + FOOT_H / 2), white, r)
        for sy in (-1, 1):
            y = sy * (FOOT_LEN / 2 - CASTOR_D / 2)
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=CASTOR_D / 2, depth=CASTOR_D / 2,
                                                location=(x, y, CASTOR_D / 2), rotation=(0, math.pi / 2, 0))
            c = bpy.context.object
            c.name = f"castor_{sx}_{sy}"
            c.data.materials.append(dark)
            c.parent = r
    return r


def build_shelf():
    metal = material("shelf_metal", (0.85, 0.86, 0.86))
    frame = material("shelf_frame", (0.95, 0.95, 0.95))
    dark = material("shelf_feet", (0.1, 0.1, 0.1))
    r = root("lab_shelf")
    L, D = SHELF_L, SHELF_D
    for i, top in enumerate(SHELF_TOPS, start=1):
        n = f"shelf_{i}"
        # Folded sheet: top skin, four faces, and the lip that returns underneath.
        box(n + "_top", (L, D, SHEET), (0, 0, top - SHEET / 2), metal, r)
        for sy in (-1, 1):
            box(f"{n}_face_y{sy}", (L, SHEET, FACE_H), (0, sy * (D / 2 - SHEET / 2), top - FACE_H / 2), metal, r)
            box(f"{n}_lip_y{sy}", (L, RETURN, SHEET), (0, sy * (D / 2 - RETURN / 2), top - FACE_H + SHEET / 2), metal, r)
        for sx in (-1, 1):
            box(f"{n}_face_x{sx}", (SHEET, D, FACE_H), (sx * (L / 2 - SHEET / 2), 0, top - FACE_H / 2), metal, r)
            box(f"{n}_lip_x{sx}", (RETURN, D, SHEET), (sx * (L / 2 - RETURN / 2), 0, top - FACE_H + SHEET / 2), metal, r)
    # Side ladders: two uprights per side, a rod-pair rung under each shelf end and one at the top.
    for sx in (-1, 1):
        x = sx * (L / 2 + LADDER_GAP)
        ys = [sy * (D / 2 - UPRIGHT_INSET) for sy in (-1, 1)]
        for y in ys:
            rod(f"upright_{sx}_{y > 0}", (x, y, FOOT_PAD_H), (x, y, FRAME_TOP), UPRIGHT_D, frame, r)
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=FOOT_PAD_D / 2, depth=FOOT_PAD_H,
                                                location=(x, y, FOOT_PAD_H / 2))
            f = bpy.context.object
            f.name = f"foot_{sx}_{y > 0}"
            f.data.materials.append(dark)
            f.parent = r
        for z in [t - FACE_H - RUNG_D / 2 for t in SHELF_TOPS] + [FRAME_TOP - RUNG_D / 2]:
            for side in (-1, 1):
                xr = x + side * RUNG_PITCH / 2
                rod(f"rung_{sx}_{side}_{round(z * 1000)}", (xr, ys[0], z), (xr, ys[1], z), RUNG_D, frame, r)
    return r


def export(r, name):
    bpy.ops.object.select_all(action="DESELECT")
    r.select_set(True)
    for c in r.children:
        c.select_set(True)
    os.makedirs(OUT_DIR, exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT_DIR, name + ".fbx"), use_selection=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                             bake_space_transform=True, object_types={"EMPTY", "MESH"})


def preview(r, name, size, target_z):
    sc = bpy.context.scene
    for o in sc.objects:
        o.hide_render = not (o is r or o.parent is r or o.type == "CAMERA")
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.show_cavity = True
    sc.display.shading.show_object_outline = True
    sc.display.shading.color_type = "MATERIAL"
    sc.render.resolution_x, sc.render.resolution_y = 1200, 900
    sc.world = sc.world or bpy.data.worlds.new("w")
    sc.world.color = (1, 1, 1)
    cam = sc.camera
    cam.location = (size * 1.1, -size * 1.6, target_z + size * 0.7)
    cam.data.lens = 35
    d = mathutils.Vector((0, 0, target_z)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(HERE, f"preview_{name}.png")
    bpy.ops.render.render(write_still=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam

table = build_table()
shelf = build_shelf()
shelf.location.x = 2.0  # side by side for the previews only; exported with origin at 0
bpy.context.view_layer.update()
preview(table, "table", 1.6, 0.4)
shelf.location.x = 0
table.location.x = -3.0
bpy.context.view_layer.update()
preview(shelf, "shelf", 1.4, 0.7)
table.location.x = 0
bpy.context.view_layer.update()
export(table, "lab_table")
export(shelf, "lab_shelf")
print("WROTE", OUT_DIR)
