"""Render 30 product angles for the animated price-check film."""
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 20
scene.cycles.use_denoising = True
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for dev in prefs.devices:
        dev.use = dev.type == 'OPTIX'
    if any(dev.use for dev in prefs.devices):
        scene.cycles.device = 'GPU'
except (RuntimeError, TypeError):
    pass

scene.render.resolution_x = scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.color_mode = 'RGBA'
scene.world = bpy.data.worlds.new("Studio fill")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.68,.76,.81,1)
scene.world.node_tree.nodes["Background"].inputs[1].default_value = .45

glaze = bpy.data.materials.new("Ivory porcelain glaze")
glaze.use_nodes = True
bsdf = glaze.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (.92,.89,.82,1)
bsdf.inputs["Roughness"].default_value = .205
bsdf.inputs["Coat Weight"].default_value = .27
# Revolve a closed cross-section with shallow flutes fading into the foot and lip.
profile=[(.003,.085),(.55,.085),(.66,.087),(.715,.12),(.72,.155),(.775,.19),(.82,.24),(.85,.32),(.905,.65),(.947,1.0),(.982,1.38),(.992,1.49),(.988,1.525),(.973,1.54),(.948,1.535),(.935,1.515),(.92,1.42),(.885,.95),(.82,.49),(.785,.35),(.74,.30),(.63,.27),(.003,.27)]
def mesh_object(name, verts, faces):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(obj)
    obj.data.materials.append(glaze)
    for poly in mesh.polygons: poly.use_smooth=True
    return obj
def connect(rows,around):
    return [(i*around+j,i*around+(j+1)%around,(i+1)*around+(j+1)%around,(i+1)*around+j) for i in range(rows-1) for j in range(around)]
n=256
verts=[]
for i,(radius,z) in enumerate(profile):
    for k in range(n):
        a=2*math.pi*k/n
        flute=.018*(.5+.5*math.cos(a*32))**2 if 6<=i<=10 else 0
        verts.append(((radius+flute)*math.cos(a),(radius+flute)*math.sin(a),z))
body=mesh_object("Fluted mug",verts,connect(len(profile),n))
mod=body.modifiers.new("Smooth rounded profile","SUBSURF")
mod.levels=mod.render_levels=1
# Elliptical ceramic handle embedded at both ends.
verts=[]
for i in range(81):
    a=math.radians(-112+224*i/80)
    x=.92+.59*math.cos(a); z=.84+.48*math.sin(a)
    tangent=Vector((-.59*math.sin(a),0,.48*math.cos(a))).normalized()
    side=Vector((tangent.z,0,-tangent.x))
    for j in range(32):
        b=2*math.pi*j/32; pos=Vector((x,0,z))+side*(.117*math.cos(b))+Vector((0,.15*math.sin(b),0))
        verts.append(tuple(pos))
handle=mesh_object("Glazed loop handle",verts,[tuple(reversed(face)) for face in connect(81,32)])
pivot=bpy.data.objects.new("Turntable",None);scene.collection.objects.link(pivot)
body.parent=handle.parent=pivot
def aim(obj,at):
    obj.rotation_euler=(Vector(at)-obj.location).to_track_quat('-Z','Y').to_euler()
def panel(name,loc,size,power,color):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj);obj.location=loc;aim(obj,(0,0,.8))
panel("Softbox",(-3,-4,6),4,510,(1,.96,.88))
panel("Cool edge",(2.5,2.3,4),2.5,580,(.74,.91,1))
panel("Peach bounce",(3,-2,.9),2.3,85,(1,.70,.45))
cam=bpy.data.cameras.new("Product portrait");view=bpy.data.objects.new("Camera",cam);scene.collection.objects.link(view)
view.location=(2.1,-7,4.1);aim(view,(.20,0,.81));cam.type='ORTHO';cam.ortho_scale=2.83;scene.camera=view
out=Path(os.environ["CUP_RENDER_DIR"]);out.mkdir(parents=True,exist_ok=True)
for frame in range(30):
    pivot.rotation_euler.z=math.radians(-30+52*frame/29)
    scene.render.filepath=str(out/f"angle-{frame:02d}.png")
    bpy.ops.render.render(write_still=True)

