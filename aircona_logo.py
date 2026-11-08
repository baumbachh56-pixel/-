"""
AIRCONA — анимация логотипа для Blender (проверено на Blender 4.2+ / 5.0).

Как использовать:
  1) В Blender: вкладка Scripting -> Open -> aircona_logo.py -> Run Script.
     Сцена соберётся сама, нажмите пробел для просмотра, Ctrl+F12 для рендера.
  2) Из терминала (собрать сцену, сохранить .blend и отрендерить видео):
       blender --background --python aircona_logo.py -- --render
     Доп. флаги:  --cycles   (рендер через Cycles вместо EEVEE)
                  --samples N
                  --out путь/к/файлу.mp4

Анимация (30 fps, 150 кадров = 5 сек):
  1-40    рисуется светло-серое кольцо
  15-60   зелёный треугольник вращается и «выпрыгивает» с пружинкой
  45-75   тёмный шеврон падает сверху внутрь треугольника
  65-115  буквы AIRCONA появляются по одной
  100-150 мягкий наезд камеры, финальная пауза
"""

import bpy
import math
import os
import sys

# ----------------------------------------------------------------------------
# Настройки
# ----------------------------------------------------------------------------
FPS = 30
FRAME_END = 150

GREEN = (0.30, 0.62, 0.45, 1.0)     # #6DBF9A-ish в линейном пространстве
DARK = (0.035, 0.035, 0.038, 1.0)   # тёмно-серый (шеврон и текст)
RING = (0.55, 0.57, 0.62, 1.0)      # светло-серое кольцо
BG = (1.0, 1.0, 1.0)                # белый фон

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ARG_RENDER = "--render" in argv
ARG_CYCLES = "--cycles" in argv


def arg_value(name, default):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


SAMPLES = int(arg_value("--samples", 64))
OUT_PATH = arg_value("--out", "//aircona_logo.mp4")


# ----------------------------------------------------------------------------
# Утилиты
# ----------------------------------------------------------------------------
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                 bpy.data.cameras, bpy.data.lights, bpy.data.actions):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def make_material(name, color, roughness=0.4, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    mat.diffuse_color = color
    return mat


def keyframe(datablock, path, frame, value, interp="BEZIER", index=-1):
    """Ставит ключ с нужной интерполяцией (работает и в Blender 5 без legacy fcurves)."""
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = interp
    try:
        prop = path
        if isinstance(value, (tuple, list)):
            setattr(datablock, prop, value)
        elif index >= 0:
            getattr(datablock, prop)[index] = value
        else:
            setattr(datablock, prop, value)
        datablock.keyframe_insert(data_path=prop, frame=frame, index=index)
    finally:
        prefs.keyframe_new_interpolation_type = old


def poly_curve(name, splines, extrude=0.0, bevel=0.0, fill="BOTH", dims="2D"):
    """splines: список (points, cyclic). points — [(x, y), ...]."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = dims
    if dims == "2D":
        cu.fill_mode = fill
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    for pts, cyclic in splines:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for p, (x, y) in zip(sp.points, pts):
            p.co = (x, y, 0.0, 1.0)
        sp.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def arc(cx, cy, r, a0, a1, steps=48):
    pts = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def scale_poly(pts, s, cx=0.0, cy=0.0):
    return [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in pts]


# ----------------------------------------------------------------------------
# Сцена
# ----------------------------------------------------------------------------
clear_scene()
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start = 1
scene.frame_end = FRAME_END
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

mat_green = make_material("AIRCONA_Green", GREEN, roughness=0.35)
mat_dark = make_material("AIRCONA_Dark", DARK, roughness=0.45)
mat_ring = make_material("AIRCONA_Ring", RING, roughness=0.6)

# Корневой объект: логотип строится в локальной плоскости XY,
# а root повёрнут так, чтобы смотреть в камеру (камера на -Y).
root = bpy.data.objects.new("AIRCONA_Logo", None)
scene.collection.objects.link(root)
root.rotation_euler = (math.radians(90), 0, 0)


def parent(obj):
    obj.parent = root
    return obj


# --- Кольцо --------------------------------------------------------------
RING_R = 1.75
ring_pts = arc(0, 0, RING_R, 90, 90 - 360, steps=160)
ring = parent(poly_curve("Ring", [(ring_pts, False)], bevel=0.038, dims="3D"))
ring.data.materials.append(mat_ring)
ring.data.use_fill_caps = True
keyframe(ring.data, "bevel_factor_end", 1, 0.0)
keyframe(ring.data, "bevel_factor_end", 40, 1.0)

# Тонкое внутреннее кольцо
ring2_pts = arc(0, 0, RING_R - 0.11, 90, 90 + 360, steps=160)
ring2 = parent(poly_curve("RingInner", [(ring2_pts, False)], bevel=0.012, dims="3D"))
ring2.data.materials.append(mat_ring)
keyframe(ring2.data, "bevel_factor_end", 8, 0.0)
keyframe(ring2.data, "bevel_factor_end", 46, 1.0)

# --- Зелёный треугольник (рамка) ----------------------------------------
TRI_CY = 0.38     # центр треугольника по вертикали
outer = [(0.0, 1.17), (0.62, 0.0), (-0.62, 0.0)]
outer = [(x, y - 0.38 + TRI_CY) for x, y in outer]
# Пивот вращения — центр тяжести треугольника
cx = sum(p[0] for p in outer) / 3
cy = sum(p[1] for p in outer) / 3
inner = scale_poly(outer, 0.60, cx, cy)
inner = [(x, y + 0.02) for x, y in inner]
tri_local_out = [(x - cx, y - cy) for x, y in outer]
tri_local_in = [(x - cx, y - cy) for x, y in inner]
tri = parent(poly_curve("Triangle", [(tri_local_out, True), (tri_local_in, True)],
                        extrude=0.06, bevel=0.006))
tri.data.materials.append(mat_green)
tri.location = (cx, cy, 0)

keyframe(tri, "scale", 15, (0.0, 0.0, 0.0), interp="BACK")
keyframe(tri, "scale", 52, (1.0, 1.0, 1.0))
keyframe(tri, "rotation_euler", 15, (0.0, math.radians(-180), math.radians(-30)), interp="CUBIC")
keyframe(tri, "rotation_euler", 55, (0.0, 0.0, 0.0))

# --- Тёмный шеврон -------------------------------------------------------
apex_y = cy + 0.30
w, h, t = 0.31, 0.44, 0.135   # полуширина, высота, толщина «рук»
chev = [
    (0.0, apex_y),
    (w, apex_y - h),
    (w - t * 1.15, apex_y - h),
    (0.0, apex_y - h * 0.52),
    (-(w - t * 1.15), apex_y - h),
    (-w, apex_y - h),
]
chev_cy = apex_y - h / 2
chev_local = [(x, y - chev_cy) for x, y in chev]
chevron = parent(poly_curve("Chevron", [(chev_local, True)], extrude=0.08, bevel=0.005))
chevron.data.materials.append(mat_dark)

FINAL_CHEV = (0.0, chev_cy, 0.04)
keyframe(chevron, "location", 45, (0.0, chev_cy + 2.6, 0.04), interp="BACK")
keyframe(chevron, "location", 72, FINAL_CHEV)
keyframe(chevron, "scale", 44, (0.0, 0.0, 0.0), interp="CONSTANT")
keyframe(chevron, "scale", 45, (1.0, 1.0, 1.0))

# --- Буквы AIRCONA (тонкий геометрический шрифт без перекладин у «A») --
LH = 0.30          # высота букв
STROKE = 0.016     # радиус штриха


def letter_A():
    return [([(-0.15, 0), (0.0, LH), (0.15, 0)], False)], 0.30


def letter_I():
    return [([(0.0, 0), (0.0, LH)], False)], 0.0


def letter_R():
    r = 0.078
    bowl = [(0.0, LH), (0.07, LH)] + arc(0.07, LH - r, r, 90, -90, 24) + [(0.0, LH - 2 * r)]
    return [([(0.0, 0), (0.0, LH)], False),
            (bowl, False),
            ([(0.07, LH - 2 * r), (0.17, 0)], False)], 0.17


def letter_C():
    r = LH / 2
    return [(arc(r, r, r, 45, 315, 48), False)], LH


def letter_O():
    r = LH / 2
    return [(arc(r, r, r, 0, 360, 64), True)], LH


def letter_N():
    return [([(0.0, 0), (0.0, LH), (0.23, 0), (0.23, LH)], False)], 0.23


glyphs = [("A", letter_A), ("I", letter_I), ("R", letter_R), ("C", letter_C),
          ("O", letter_O), ("N", letter_N), ("A", letter_A)]
GAP = 0.13
TEXT_Y = -0.72

built = []
for ch, fn in glyphs:
    splines, width = fn()
    # нормализуем, чтобы у каждой буквы x начинался с 0
    min_x = min(x for pts, _ in splines for x, _y in pts)
    splines = [([(x - min_x, y) for x, y in pts], c) for pts, c in splines]
    built.append((ch, splines, width))

total = sum(wd for _, _, wd in built) + GAP * (len(built) - 1)
x = -total / 2
letters = []
for i, (ch, splines, width) in enumerate(built):
    # центрируем каждую букву вокруг её собственного пивота
    local = [([(px - width / 2, py - LH / 2) for px, py in pts], c) for pts, c in splines]
    obj = parent(poly_curve(f"Letter_{i}_{ch}", local, bevel=STROKE, dims="3D"))
    obj.data.materials.append(mat_dark)
    obj.location = (x + width / 2, TEXT_Y + LH / 2, 0)
    letters.append(obj)
    x += width + GAP

for i, obj in enumerate(letters):
    f0 = 65 + i * 5
    final = tuple(obj.location)
    keyframe(obj, "location", f0, (final[0], final[1] - 0.25, final[2]), interp="BACK")
    keyframe(obj, "location", f0 + 18, final)
    keyframe(obj, "scale", f0, (0.0, 0.0, 0.0), interp="BACK")
    keyframe(obj, "scale", f0 + 14, (1.0, 1.0, 1.0))
    keyframe(obj, "rotation_euler", f0, (math.radians(-90), 0, 0), interp="CUBIC")
    keyframe(obj, "rotation_euler", f0 + 16, (0.0, 0.0, 0.0))

# Лёгкое «дыхание» всего логотипа в конце
keyframe(root, "rotation_euler", 100, (math.radians(90), 0, math.radians(-6)))
keyframe(root, "rotation_euler", 150, (math.radians(90), 0, 0))
keyframe(root, "rotation_euler", 1, (math.radians(90), 0, math.radians(-6)))

# ----------------------------------------------------------------------------
# Камера, свет, мир
# ----------------------------------------------------------------------------
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 50
cam = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam)
cam.rotation_euler = (math.radians(90), 0, 0)
scene.camera = cam
keyframe(cam, "location", 1, (0.0, -11.0, 0.0))
keyframe(cam, "location", FRAME_END, (0.0, -10.0, 0.0))

key_data = bpy.data.lights.new("Key", "AREA")
key_data.energy = 250
key_data.size = 5
key = bpy.data.objects.new("Key", key_data)
scene.collection.objects.link(key)
key.location = (-3.5, -5.0, 4.0)
key.rotation_euler = (math.radians(50), 0, math.radians(-35))

rim_data = bpy.data.lights.new("Rim", "AREA")
rim_data.energy = 120
rim_data.size = 4
rim = bpy.data.objects.new("Rim", rim_data)
scene.collection.objects.link(rim)
rim.location = (4.0, -3.0, -2.0)
rim.rotation_euler = (math.radians(110), 0, math.radians(50))

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
# Камера видит чисто белый фон, а освещение от мира — мягкое серое,
# чтобы логотип не пересвечивался.
nt = world.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
out = nt.nodes.new("ShaderNodeOutputWorld")
lp = nt.nodes.new("ShaderNodeLightPath")
mix = nt.nodes.new("ShaderNodeMixShader")
bg_light = nt.nodes.new("ShaderNodeBackground")
bg_light.inputs["Color"].default_value = (1, 1, 1, 1)
bg_light.inputs["Strength"].default_value = 0.35
bg_cam = nt.nodes.new("ShaderNodeBackground")
bg_cam.inputs["Color"].default_value = (*BG, 1.0)
bg_cam.inputs["Strength"].default_value = 1.0
nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
nt.links.new(bg_light.outputs[0], mix.inputs[1])
nt.links.new(bg_cam.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], out.inputs["Surface"])

# Стандартный view transform — чтобы белый фон был по-настоящему белым
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"

# ----------------------------------------------------------------------------
# Рендер
# ----------------------------------------------------------------------------
if ARG_CYCLES:
    scene.render.engine = "CYCLES"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
else:
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    try:
        scene.eevee.taa_render_samples = SAMPLES
    except AttributeError:
        pass

scene.render.filepath = OUT_PATH
try:
    scene.render.image_settings.media_type = "VIDEO"      # Blender 5.0+
except (AttributeError, TypeError):
    pass
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "HIGH"

scene.frame_set(1)

if bpy.app.background:
    blend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aircona_logo.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print("Saved:", blend_path)
    if ARG_RENDER:
        bpy.ops.render.render(animation=True)
        print("Rendered:", bpy.path.abspath(OUT_PATH))
