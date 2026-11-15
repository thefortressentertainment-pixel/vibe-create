"""Build a deterministic low-poly fantasy scene in Blender from project metadata.

Run inside Blender with --background --python generate_blender_concept.py and
VIBE_GAME_TITLE, VIBE_GAME_IDEA, VIBE_GAME_OUTDIR set in the environment.
"""

import json
import math
import os

import bpy
from mathutils import Matrix, Vector


TITLE = os.environ.get("VIBE_GAME_TITLE", "Idea Game")
IDEA = os.environ.get("VIBE_GAME_IDEA", "A hero explores a magical world.")
THEME = os.environ.get("VIBE_GAME_THEME", "sky-dragon")
with open(os.environ["VIBE_GAME_CONTENT"], encoding="utf-8") as content_file:
    GAME = json.load(content_file)
OUTDIR = os.environ["VIBE_GAME_OUTDIR"]
os.makedirs(OUTDIR, exist_ok=True)
review_character_prefix = GAME.get("player", {}).get("name", "Wayfarer")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 760
scene.render.resolution_y = 640
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.render.filepath = os.path.join(OUTDIR, "concept.png")
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "AgX"


def material(name, color, metallic=0.0, roughness=0.65, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    if emission:
        shader.inputs["Emission Color"].default_value = (*color, 1.0)
        shader.inputs["Emission Strength"].default_value = emission
    return mat


def ico(name, location, scale, mat, subdivisions=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def cylinder(name, location, radius, depth, mat, vertices=8, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth,
                                       location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def cone(name, location, radius1, radius2, depth, mat, vertices=7, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius1, radius2=radius2,
                                    depth=depth, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def box(name, location, scale, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def beam(name, start, end, radius, mat, vertices=8):
    a, b = Vector(start), Vector(end)
    delta = b - a
    obj = cylinder(name, (a + b) * 0.5, radius, delta.length, mat, vertices)
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    return obj


def star_mesh(name, center, outer, inner, depth, mat):
    cx, cy, cz = center
    verts = []
    for i in range(10):
        radius = outer if i % 2 == 0 else inner
        angle = math.pi * 0.5 + i * math.pi / 5
        verts.append((cx + math.cos(angle) * radius, cy - depth / 2, cz + math.sin(angle) * radius))
    for i in range(10):
        radius = outer if i % 2 == 0 else inner
        angle = math.pi * 0.5 + i * math.pi / 5
        verts.append((cx + math.cos(angle) * radius, cy + depth / 2, cz + math.sin(angle) * radius))
    verts.extend([(cx, cy - depth / 2, cz), (cx, cy + depth / 2, cz)])
    faces = []
    for i in range(10):
        j = (i + 1) % 10
        faces.extend([(20, i, j), (21, 10 + j, 10 + i), (i, 10 + i, 10 + j, j)])
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return obj


sky = material("Night teal", (0.018, 0.055, 0.105), roughness=1)
rock = material("Floating island slate", (0.12, 0.19, 0.24))
grass = material("Island moss", (0.18, 0.39, 0.31))
grass_light = material("Moss highlights", (0.34, 0.56, 0.39))
dragon = material("Dragon jade", (0.12, 0.56, 0.43), roughness=0.42)
dragon_light = material("Dragon belly", (0.61, 0.78, 0.48))
wing_mat = material("Dragon wings", (0.075, 0.31, 0.32))
gold = material("Beacon brass", (0.83, 0.48, 0.16), metallic=0.48, roughness=0.35)
star_mat = material("Star glow", (1.0, 0.67, 0.18), emission=2.0)
eye_mat = material("Eyes", (0.045, 0.075, 0.1), metallic=0.1)

world = bpy.data.worlds.new("Deep blue evening")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.026, 0.07, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.45
scene.world = world

# Main floating island, faceted stone underside, green playable top.
ico("Main floating island", (0, 0, -0.45), (5.1, 4.0, 1.15), rock, 2)
ico("Island top", (0, 0, 0.08), (5.0, 3.9, 0.48), grass, 2)
for name, loc, scale in [
    ("Moss patch west", (-2.9, -0.45, 0.38), (1.4, 1.0, 0.10)),
    ("Moss patch east", (2.25, 0.55, 0.40), (1.65, 1.2, 0.10)),
    ("Moss patch front", (0.15, -2.15, 0.38), (1.55, 0.8, 0.08)),
]:
    ico(name, loc, scale, grass_light, 1)

# Little broken fragments make the floating silhouette legible.
ico("Floating shard left", (-5.4, 1.7, -1.0), (0.75, 0.7, 0.45), rock, 1)
ico("Floating shard right", (5.6, 2.6, -1.8), (0.8, 0.7, 0.45), rock, 1)

# Hero dragon: body/head, four legs, long tail, ears/horns, folded stylized wings.
ico("Sky Dragon", (-0.9, -0.1, 1.17), (1.12, 0.56, 0.62), dragon, 2)
ico("Dragon belly", (-0.45, -0.48, 0.98), (0.68, 0.22, 0.34), dragon_light, 1)
ico("Dragon head", (0.18, -0.03, 1.62), (0.59, 0.47, 0.47), dragon, 2)
ico("Dragon muzzle", (0.63, -0.12, 1.47), (0.4, 0.32, 0.26), dragon_light, 1)
for side_y in (-0.19, 0.19):
    # The dragon faces +X. The eyes sit just outside the head surface, paired
    # across its front rather than protruding as separate cheek-side knobs.
    ico("Dragon eye left" if side_y < 0 else "Dragon eye right",
        (0.66, side_y, 1.80), (0.045, 0.06, 0.065), eye_mat, 2)
    ico("Dragon eye glint",
        (0.696, side_y - 0.012, 1.818), (0.012, 0.018, 0.022), star_mat, 1)
for x in (-0.05, 0.42):
    cone("Dragon horn", (x, -0.03, 2.12), 0.16, 0.015, 0.48, gold, 6, (0, -0.35, 0))
for x in (-1.55, -0.15):
    for y in (-0.38, 0.28):
        beam("Dragon leg", (x, y, 1.0), (x + 0.08, y, 0.56), 0.13, dragon, 7)
        ico("Dragon foot", (x + 0.15, y - 0.015, 0.55), (0.23, 0.16, 0.12), dragon_light, 1)
beam("Dragon tail", (-1.8, 0.05, 1.29), (-2.95, 0.15, 1.7), 0.18, dragon, 7)
cone("Tail spade", (-3.0, 0.15, 1.73), 0.28, 0.015, 0.52, gold, 5, (0, -0.6, 0))

def wing(name, sign):
    points = [(-0.8, 0.28, 1.55), (-1.0, 0.42, 3.08), (0.13, 0.35, 2.52),
              (0.38, 0.33, 1.94), (-0.36, 0.35, 1.55)]
    points = [(x, y, z) for x, y, z in points]
    verts = [(x, y, z) for x, y, z in points]
    faces = [(0, 1, 2), (0, 2, 3), (0, 3, 4)]
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(wing_mat)
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    if sign < 0:
        obj.scale.x = -1
    for endpoint in (points[1], points[2], points[3]):
        beam(name + " rib", points[0], endpoint, 0.035, gold, 5)
    return obj

wing("Dragon near wing", 1)
wing("Dragon far wing", -1)

# Beacon on the right side of the island.
bx, by = 2.85, 0.72
cylinder("Beacon plinth", (bx, by, 0.65), 0.65, 0.42, gold, 8)
cylinder("Beacon tower", (bx, by, 1.55), 0.34, 1.5, rock, 7)
cylinder("Beacon gold bands", (bx, by, 1.0), 0.41, 0.12, gold, 8)
cylinder("Beacon crown", (bx, by, 2.32), 0.55, 0.18, gold, 8)
ico("Beacon crystal", (bx, by, 2.75), (0.34, 0.34, 0.56), star_mat, 1)
for i in range(8):
    angle = 2 * math.pi * i / 8
    ico("Beacon crown stud", (bx + math.cos(angle) * 0.52, by + math.sin(angle) * 0.52, 2.35),
        (0.09, 0.09, 0.13), star_mat, 1)

# Collectible stars around the path.
for i, (loc, scale) in enumerate([
    ((-3.25, -1.65, 1.2), 0.34), ((0.65, -2.25, 1.55), 0.30), ((2.0, 2.0, 2.25), 0.32)
]):
    star_mesh("Floating star %02d" % i, loc, scale, scale * 0.43, 0.11, star_mat)

# Two small pines along the rear edge.
for i, (x, y, h) in enumerate([(-3.6, 1.25, 1.55), (4.0, -0.15, 1.2)]):
    cylinder("Pine trunk %d" % i, (x, y, 0.63), 0.13, 0.7, gold, 6)
    cone("Pine crown %d" % i, (x, y, 0.95 + h * 0.35), 0.65, 0.03, h, grass_light, 6)

# Faint stepping-stone trail leads from the hero to the beacon.
for i, (x, y) in enumerate([(0.25, 0.35), (0.85, 0.4), (1.45, 0.5), (2.05, 0.6)]):
    ico("Path stone %02d" % i, (x, y, 0.52), (0.25, 0.20, 0.07), gold, 1)

review_character_target = Vector((0.25, -0.02, 1.76))
if THEME != "sky-dragon":
    # Keep the sky-dragon template out of other genres; build a matching
    # medieval encounter from primitives instead of shipping the wrong hero.
    for obj in scene.objects:
        if obj.type == "MESH":
            obj.hide_render = True
    traveler = GAME.get("player", {}).get("name", "Wayfarer")
    guide = GAME.get("npc", {}).get("name", "Trail Guide")
    foe = GAME.get("enemy", {}).get("name", "Guardian")
    item = GAME.get("collectible", {}).get("name", "Relic")

    earth = material("Moor earth", (0.13, 0.20, 0.19))
    stone = material("Crypt stone", (0.27, 0.31, 0.30))
    stone_light = material("Worn edges", (0.47, 0.46, 0.39))
    cloak = material("Traveler cloak", (0.20, 0.18, 0.26))
    skin = material("Traveler face", (0.68, 0.47, 0.32))
    wraith = material("Wraith shadow", (0.24, 0.12, 0.31), emission=0.15)
    wisp = material("Will-o-wisp", (0.37, 0.95, 0.76), emission=2.3)
    ember = material("Torch ember", (1.0, 0.36, 0.10), emission=1.4)

    if THEME == "dark-fantasy":
        box("Murkfen stone path", (0, 0, -0.42), (10.5, 8.0, 0.55), earth)
        box("Crypt dais", (2.2, 1.45, -0.04), (4.5, 2.7, 0.26), stone)
        # A broken crypt doorway and worn battlements frame the encounter.
        for x, z, sx, sz in [(0.85, 1.25, 0.46, 2.5), (3.55, 1.25, 0.46, 2.5),
                             (1.05, 2.62, 0.82, 0.42), (3.35, 2.62, 0.82, 0.42),
                             (2.2, 2.92, 3.1, 0.40)]:
            box("Wraithmoor crypt arch", (x, 1.25, z), (sx, 0.60, sz), stone_light)
        for i, x in enumerate((-4.0, -3.2, 4.4)):
            box("Broken grave marker %d" % i, (x, 0.7 + (i % 2), 0.10), (0.45, 0.18, 0.75), stone)
            ico("Grave crown %d" % i, (x, 0.7 + (i % 2), 0.48), (0.24, 0.11, 0.17), stone_light, 1)
        for i, (x, y) in enumerate(((-3.7, -2.2), (-2.6, 2.4), (4.3, 2.8))):
            beam("Dead tree trunk %d" % i, (x, y, 0.0), (x + 0.12, y, 2.5), 0.14, rock, 5)
            for dx, dz in ((-0.65, 0.25), (0.58, 0.55), (-0.4, 1.0)):
                beam("Dead tree limb", (x + 0.08, y, 1.1 + dz), (x + dx, y, 1.5 + dz), 0.075, rock, 5)
        # Traveler in a hooded cloak with a lantern and walking staff.
        tx, ty = -1.95, -0.45
        cone(traveler + " cloak", (tx, ty, 0.68), 0.47, 0.20, 1.05, cloak, 7)
        ico(traveler + " head", (tx, ty, 1.43), (0.24, 0.23, 0.30), skin, 2)
        ico(traveler + " visible face", (tx + 0.16, ty - 0.035, 1.44), (0.11, 0.17, 0.18), skin, 2)
        for side_y in (-0.085, 0.085):
            ico(traveler + " eye", (tx + 0.245, ty + side_y - 0.035, 1.49), (0.025, 0.022, 0.03), eye_mat, 1)
        cone(traveler + " hood", (tx, ty, 1.66), 0.30, 0.035, 0.24, cloak, 7)
        beam(traveler + " staff", (tx + 0.45, ty, 0.08), (tx + 0.50, ty, 1.75), 0.055, gold, 6)
        ico(traveler + " lantern", (tx + 0.50, ty, 1.87), (0.17, 0.17, 0.22), ember, 1)
        for dx in (-0.22, 0.22):
            beam(traveler + " boot", (tx + dx, ty, 0.4), (tx + dx + 0.08, ty - 0.12, 0.08), 0.10, rock, 6)
        # A friendly guide stands beside the path, away from the fight.
        gx, gy = -3.65, -1.45
        cone(guide + " robe", (gx, gy, 0.61), 0.38, 0.19, 0.95, grass, 7)
        ico(guide + " head", (gx, gy, 1.27), (0.22, 0.21, 0.26), skin, 2)
        # The crypt warden faces the traveler from the far side of the arch.
        ex, ey = 2.5, -0.38
        ico(foe + " wraith body", (ex, ey, 1.13), (0.58, 0.38, 0.76), wraith, 2)
        cone(foe + " shroud", (ex, ey, 1.74), 0.48, 0.02, 0.74, cloak, 7)
        for side in (-0.21, 0.21):
            ico(foe + " wisp eye", (ex + side, ey - 0.35, 1.48), (0.08, 0.045, 0.08), wisp, 1)
        for i, (x, y) in enumerate(((-0.4, -2.0), (0.4, -2.2), (3.4, -1.7))):
            ico("Collectible " + item + " %d" % (i + 1), (x, y, 0.9 + i * 0.12), (0.17, 0.17, 0.22), wisp, 1)
        review_character_target = Vector((tx, ty, 1.35))
    else:
        # A genre-neutral woodland trail for ideas outside the sky-dragon and
        # Valtherion dark-fantasy presets.
        green = material("Forest floor", (0.20, 0.37, 0.26))
        box("Forest clearing", (0, 0, -0.42), (10.5, 8.0, 0.55), green)
        box("Trail", (0, -0.55, -0.08), (8.4, 1.55, 0.16), stone_light)
        for i, (x, y, h) in enumerate(((-4.0, 1.0, 2.5), (-3.0, 3.2, 2.1), (4.2, 1.5, 2.7), (3.5, 3.5, 2.2))):
            cylinder("Forest tree trunk %d" % i, (x, y, 0.55), 0.18, 1.1, rock, 7)
            cone("Forest canopy %d" % i, (x, y, 1.0 + h * 0.42), 0.85, 0.04, h, grass_light, 7)
        tx, ty = -1.7, -0.45
        cone(traveler + " tunic", (tx, ty, 0.66), 0.43, 0.23, 1.0, dragon, 7)
        ico(traveler + " head", (tx, ty, 1.39), (0.24, 0.22, 0.28), skin, 2)
        beam(traveler + " walking staff", (tx + 0.48, ty, 0.08), (tx + 0.48, ty, 1.7), 0.06, gold, 6)
        gx, gy = -3.4, -1.55
        ico(guide + " guide", (gx, gy, 0.95), (0.35, 0.30, 0.85), gold, 1)
        ex, ey = 2.3, -0.25
        ico(foe + " guardian", (ex, ey, 0.9), (0.62, 0.48, 0.82), wraith, 2)
        for i, (x, y) in enumerate(((-0.1, -2.0), (0.7, -2.0), (3.5, -1.4))):
            ico("Collectible " + item + " %d" % (i + 1), (x, y, 0.85 + i * 0.12), (0.17, 0.17, 0.22), star_mat, 1)
        review_character_target = Vector((tx, ty, 1.35))

# Scale the dragon around its center so its face reads at the full-scene size.
if THEME == "sky-dragon":
    hero_anchor = Vector((-0.9, -0.1, 1.2))
    hero_scale = 1.25
    scale_around_anchor = (Matrix.Translation(hero_anchor)
                           @ Matrix.Diagonal((hero_scale, hero_scale, hero_scale, 1.0))
                           @ Matrix.Translation(-hero_anchor))
    for obj in scene.objects:
        if obj.name == "Sky Dragon" or obj.name.startswith("Dragon"):
            obj.matrix_world = scale_around_anchor @ obj.matrix_world

# Decorative title is baked into the Blender file but excluded from the render.
text_curve = bpy.data.curves.new("Scene title", type="FONT")
text_curve.body = TITLE.upper()
text_curve.align_x = "CENTER"
text_curve.size = 0.34
title_obj = bpy.data.objects.new("Scene title", text_curve)
scene.collection.objects.link(title_obj)
title_obj.location = (0, 3.65, 4.2)
title_obj.rotation_euler = (math.radians(63), 0, 0)
title_obj.data.materials.append(material("Title ink", (0.8, 0.9, 0.88), emission=0.2))
title_obj.hide_render = True

# Camera and lighting.
cam_data = bpy.data.cameras.new("Concept Camera")
cam = bpy.data.objects.new("Concept Camera", cam_data)
scene.collection.objects.link(cam)
cam.location = (16.5, -8.5, 11.8)
target = Vector((0.0, 0.0, 1.05))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
cam_data.type = "ORTHO"
cam_data.ortho_scale = 13.7
scene.camera = cam

sun_data = bpy.data.lights.new("Moon key", "SUN")
sun_data.energy = 2.0
sun_data.angle = math.radians(18)
sun = bpy.data.objects.new("Moon key", sun_data)
scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(28), math.radians(-32), math.radians(-28))

fill_data = bpy.data.lights.new("Warm fill", "AREA")
fill_data.energy = 950
fill_data.shape = "DISK"
fill_data.size = 8
fill_data.color = (0.55, 0.76, 1.0)
fill = bpy.data.objects.new("Warm fill", fill_data)
scene.collection.objects.link(fill)
fill.location = (-5, -5, 9)
fill.rotation_euler = (Vector((0, 0, 1)) - fill.location).to_track_quat("-Z", "Y").to_euler()

rim_data = bpy.data.lights.new("Beacon rim", "AREA")
rim_data.energy = 700
rim_data.shape = "DISK"
rim_data.size = 5
rim_data.color = (1.0, 0.43, 0.16)
rim = bpy.data.objects.new("Beacon rim", rim_data)
scene.collection.objects.link(rim)
rim.location = (5, 4, 7)
rim.rotation_euler = (Vector((0, 0, 1)) - rim.location).to_track_quat("-Z", "Y").to_euler()

scene.render.image_settings.file_format = "PNG"
scene.camera.data.lens = 50
scene.render.filepath = os.path.join(OUTDIR, "concept.png")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTDIR, "concept.blend"))
bpy.ops.render.render(write_still=True)

# A close-up makes face placement reviewable at the small-model scale.
main_camera = scene.camera
main_resolution = (scene.render.resolution_x, scene.render.resolution_y)
main_path = scene.render.filepath
close_data = bpy.data.cameras.new("Character Review Camera")
close_camera = bpy.data.objects.new("Character Review Camera", close_data)
scene.collection.objects.link(close_camera)
close_target = review_character_target
# Characters in these templates face +X. Review near that axis so a paired
# front face does not read as a side profile.
close_camera.location = close_target + Vector((4.8, -0.55, 0.55))
close_camera.rotation_euler = (close_target - close_camera.location).to_track_quat("-Z", "Y").to_euler()
close_data.type = "ORTHO"
close_data.ortho_scale = 2.7
scene.camera = close_camera
scene.render.resolution_x = 640
scene.render.resolution_y = 480
scene.render.resolution_percentage = 100
scene.render.filepath = os.path.join(OUTDIR, "character-closeup.png")
if THEME == "sky-dragon":
    # Nearby props can overlap the dragon in a straight-on review crop.
    hidden_for_closeup = [obj for obj in scene.objects
                          if obj.type == "MESH" and obj.name != "Sky Dragon"
                          and not obj.name.startswith("Dragon")]
else:
    face_parts = ("head", "face", "eye", "hood")
    hidden_for_closeup = [obj for obj in scene.objects
                          if obj.type == "MESH" and not (
                              obj.name.startswith(review_character_prefix)
                              and any(part in obj.name.lower() for part in face_parts)
                          )]
for obj in hidden_for_closeup:
    obj.hide_render = True
bpy.ops.render.render(write_still=True)
for obj in hidden_for_closeup:
    obj.hide_render = False
scene.camera = main_camera
scene.render.resolution_x, scene.render.resolution_y = main_resolution
scene.render.filepath = main_path
bpy.data.objects.remove(close_camera, do_unlink=True)
bpy.data.cameras.remove(close_data)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTDIR, "concept.blend"))

for obj in bpy.context.selected_objects:
    obj.select_set(False)
for obj in scene.objects:
    if obj.type == "MESH" and not obj.hide_render:
        obj.select_set(True)
bpy.context.view_layer.objects.active = next(obj for obj in scene.objects if obj.type == "MESH" and not obj.hide_render)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUTDIR, "concept.fbx"), use_selection=True,
                         object_types={"MESH"}, apply_scale_options="FBX_SCALE_UNITS",
                         axis_forward="-Z", axis_up="Y", bake_space_transform=False,
                         add_leaf_bones=False, use_mesh_modifiers=True, use_custom_props=False)
print(json.dumps({"ok": True, "title": TITLE, "idea": IDEA, "objects": len(scene.objects),
                  "blend": os.path.join(OUTDIR, "concept.blend"),
                  "render": os.path.join(OUTDIR, "concept.png"),
                  "fbx": os.path.join(OUTDIR, "concept.fbx")}))
