import bpy, sys, math, mathutils
FBX = "/Users/rorosaga/Documents/roros_lab/cyphy/PUPPET/unity/PUPPET_Unity/Assets/minimalist-desk-escritorio-minimalista/source/escritorio2_0.fbx"
OUT = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=FBX)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
# Unity instance scale (x, y-up, z) = (0.4267, 0.3889, 0.4267); Blender is Z-up.
root = bpy.data.objects.new("root", None); bpy.context.scene.collection.objects.link(root)
for o in bpy.context.scene.objects:
    if o.parent is None and o is not root: o.parent = root
root.scale = (0.42665848, 0.42665848, 0.38887143)
bpy.context.view_layer.update()
pts = [o.matrix_world @ mathutils.Vector(c) for o in meshes for c in o.bound_box]
mn = mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); mx = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
size = mx - mn
print("BBOX_M", [round(v, 3) for v in size], "min", [round(v,3) for v in mn], "max", [round(v,3) for v in mx])
# table-top slab: vertices in the top 10 cm
vz = sorted({round((o.matrix_world @ v.co).z, 4) for o in meshes for v in o.data.vertices})
top = mx.z; print("Z_LEVELS_NEAR_TOP", [round(top - z, 4) for z in vz if top - z < 0.12][:25])
for o in meshes: print("MESH", o.name, len(o.data.vertices))
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"; sc.display.shading.show_cavity = True; sc.display.shading.show_object_outline = True
sc.display.shading.color_type = "SINGLE"; sc.display.shading.single_color = (0.85, 0.85, 0.85)
sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
sc.world = bpy.data.worlds.new("w"); sc.world.color = (1, 1, 1)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
def shot(name, loc, target, lens):
    cam.location = loc; cam.data.lens = lens
    d = mathutils.Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = OUT + "/" + name + ".png"; bpy.ops.render.render(write_still=True)
c = (mn + mx) / 2
shot("table_overview", c + mathutils.Vector((size.x*1.1, -size.y*1.6, size.z*1.4)), c, 35)
corner = mathutils.Vector((mx.x, mn.y, mx.z))
shot("table_corner", corner + mathutils.Vector((0.35, -0.35, 0.18)), corner + mathutils.Vector((-0.05, 0.05, -0.04)), 50)
shot("table_corner_below", corner + mathutils.Vector((0.32, -0.32, -0.30)), corner + mathutils.Vector((-0.06, 0.06, -0.03)), 50)
shot("table_top_view", mathutils.Vector((c.x, c.y, mx.z + 3.0)), c, 35)
