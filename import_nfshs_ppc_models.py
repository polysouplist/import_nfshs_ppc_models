#-*- coding:utf-8 -*-

# Blender Need for Speed High Stakes Pocket PC importer Add-on
# Add-on developed by PolySoupList


bl_info = {
	"name": "Import Need for Speed High Stakes Pocket PC models format (.z3d, .trk)",
	"description": "Import meshes files from Need for Speed High Stakes Pocket PC",
	"author": "PolySoupList",
	"version": (1, 0, 0),
	"blender": (3, 6, 23),
	"location": "File > Import > Need for Speed High Stakes Pocket PC (.z3d, .trk)",
	"warning": "",
	"wiki_url": "",
	"tracker_url": "",
	"support": "COMMUNITY",
	"category": "Import-Export"}


import bpy
from bpy.types import (
	Operator,
	OperatorFileListElement
)
from bpy.props import (
	StringProperty,
	BoolProperty,
	EnumProperty,
	CollectionProperty
)
from bpy_extras.io_utils import (
	ImportHelper,
	orientation_helper,
	axis_conversion,
)
import bmesh
import binascii
import math
from mathutils import Matrix, Quaternion
import os
import time
import struct


def main(context, file_path, resource_version, clear_scene, global_matrix):
	if bpy.ops.object.mode_set.poll():
		bpy.ops.object.mode_set(mode='OBJECT')
	
	if clear_scene == True:
		print("Clearing scene...")
		clearScene(context)
	
	status = import_nfshs_ppc_models(context, file_path, resource_version, clear_scene, global_matrix)
	
	return status


def import_nfshs_ppc_models(context, file_path, resource_version, clear_scene, m):
	start_time = time.time()
	
	main_collection_name = os.path.basename(file_path)
	main_collection = bpy.data.collections.new(main_collection_name)
	bpy.context.scene.collection.children.link(main_collection)
	
	print("Importing file %s" % os.path.basename(file_path))
	
	## PARSING FILES
	print("Parsing file...")
	parsing_time = time.time()
	
	if resource_version == 'Z3D':
		object = read_z3d(file_path)
	elif resource_version == 'TRK':
		trk = read_trk(file_path)
	
	elapsed_time = time.time() - parsing_time
	print("... %.4fs" % elapsed_time)
	
	## IMPORTING TO SCENE
	print("Importing data to scene...")
	importing_time = time.time()
	
	if resource_version == 'Z3D':
		name, vertices, uvs, polygons, texture_name = object
		if len(vertices) > 0:
			obj = create_object(name, vertices, uvs, polygons, texture_name)
			main_collection.objects.link(obj)
			obj.matrix_world = m
	elif resource_version == 'TRK':
		positions_collection = bpy.data.collections.new("Positions")
		main_collection.children.link(positions_collection)
		objects_collection = bpy.data.collections.new("Objects")
		main_collection.children.link(objects_collection)
		walls_collection = bpy.data.collections.new("Walls")
		main_collection.children.link(walls_collection)
		road_collection = bpy.data.collections.new("Road")
		main_collection.children.link(road_collection)
		node_collection = bpy.data.collections.new("Nodes")
		road_collection.children.link(node_collection)
		sprite_collection = bpy.data.collections.new("Sprites")
		road_collection.children.link(sprite_collection)
		minimap_collection = bpy.data.collections.new("Minimap")
		main_collection.children.link(minimap_collection)
		for i in range(0, len(trk[0])):
			unk_coord, coord = trk[0][i]
			position = bpy.data.objects.new("Position", None)
			positions_collection.objects.link(position)
			position.matrix_world = m @ Matrix.Translation(coord)
			position["unknown"] = unk_coord
		for i in range(0, len(trk[1])):
			vertices, uvs, polygons, texture_name = trk[1][i]
			if len(vertices) > 0:
				obj = create_object("Object", vertices, uvs, polygons, texture_name)
				objects_collection.objects.link(obj)
				obj.matrix_world = m
		for i in range(0, len(trk[2])):
			vertices, uvs, polygons, texture_name = trk[2][i]
			walls_indices = trk[3][i]
			if len(vertices) > 0:
				obj = create_object("Wall", vertices, uvs, walls_indices, texture_name)
				walls_collection.objects.link(obj)
				obj.matrix_world = m
		vertices, uvs, polygons, texture_name = trk[4]
		unpacked_polygons = []
		for i in range(0, len(polygons)):
			unpacked_polygon = polygons[i][0]
			unpacked_locator = polygons[i][1]
			locator_quaternion = polygons[i][2]
			sprite_positions = polygons[i][3]
			
			unpacked_polygons.append(unpacked_polygon)
			locator = bpy.data.objects.new("Node", None)
			locator.empty_display_type = 'SINGLE_ARROW'
			node_collection.objects.link(locator)
			locator.matrix_world = m @ Matrix.Translation(unpacked_locator)
			locator.rotation_mode = 'QUATERNION'
			locator.rotation_quaternion = [locator_quaternion[3], locator_quaternion[2], locator_quaternion[0], locator_quaternion[1]]
			
		for i in range(0, len(sprite_positions)):
			sprite_xyz, sprite_index = sprite_positions[i]
			
			sprite_empty = bpy.data.objects.new("Sprite", None)
			sprite_empty["unk_index"] = sprite_index
			sprite_collection.objects.link(sprite_empty)
			sprite_empty.matrix_world = m @ Matrix.Translation(sprite_xyz)
		
		if len(vertices) > 0:
			obj = create_object("Road", vertices, uvs, unpacked_polygons, texture_name)
			road_collection.objects.link(obj)
			obj.matrix_world = m
		
		minimap_vertices = trk[5]
		if len(minimap_vertices) > 0:
			mesh = bpy.data.meshes.new("Minimap")
			obj = bpy.data.objects.new("Minimap", mesh)
			mesh.from_pydata(minimap_vertices, [], [])
			minimap_collection.objects.link(obj)
			obj.matrix_world = m
	
	elapsed_time = time.time() - importing_time
	print("... %.4fs" % elapsed_time)
	
	## Adjusting scene
	for window in bpy.context.window_manager.windows:
		for area in window.screen.areas:
			if area.type == 'VIEW_3D':
				for space in area.spaces:
					if space.type == 'VIEW_3D':
						space.shading.type = 'MATERIAL'
				region = next(region for region in area.regions if region.type == 'WINDOW')
				override = bpy.context.copy()
				override['area'] = area
				override['region'] = region
				bpy.ops.view3d.view_all(override, use_all_regions=False, center=False)
	
	print("Finished")
	elapsed_time = time.time() - start_time
	print("Elapsed time: %.4fs" % elapsed_time)
	return {'FINISHED'}


def read_z3d(file_path):
	vertices = []
	uvs = []
	polygons = []
	
	with open(file_path, "rb") as f:
		header_size = struct.unpack('<I', f.read(0x4))[0]
		header = f.read(header_size)
		
		unk0 = struct.unpack('<I', f.read(0x4))[0]
		unk1 = struct.unpack('<I', f.read(0x4))[0]
		unk2 = struct.unpack('<I', f.read(0x4))[0]
		
		name_length = struct.unpack('<I', f.read(0x4))[0]
		name = f.read(name_length)
		name = str(name, 'ascii')
		f.read(0x1)
		
		num_vrtx = struct.unpack('<I', f.read(0x4))[0]
		num_plgn = struct.unpack('<I', f.read(0x4))[0]
		
		for i in range(0, num_vrtx):
			vertex = struct.unpack('<3f', f.read(0xC))
			vertices.append(vertex)
		
		for i in range(0, num_vrtx):
			uv = struct.unpack('<2f', f.read(0x8))
			uvs.append(uv)
		
		for i in range(0, num_plgn):
			polygon = struct.unpack('<3H', f.read(0x6))
			polygons.append(polygon)
		
		texture_length = struct.unpack('<I', f.read(0x4))[0]
		texture_name = f.read(texture_length)
		f.read(0x1)
	
	z3d = [name, vertices, uvs, polygons, texture_name]
	
	return z3d


def read_trk(file_path):
	coords = {}
	sprite_names = []
	objects = {}
	walls = {}
	roads = {}
	
	with open(file_path, "rb") as f:
		
		num_coords = struct.unpack('<I', f.read(0x4))[0]
		
		for i in range(0, num_coords):
			unk_coord = struct.unpack('<I', f.read(0x4))[0]
			coord = struct.unpack('<3f', f.read(0xC))
			coords[i] = [unk_coord, coord]
		
		num_spritenames = struct.unpack('<I', f.read(0x4))[0]
		
		for i in range(0, num_spritenames):
			sprite_name_length = struct.unpack('<I', f.read(0x4))[0]
			sprite_name = f.read(sprite_name_length)
			sprite_names.append(str(sprite_name, 'ascii'))
		
		num_objects = struct.unpack('<I', f.read(0x4))[0]
		
		for i in range(0, num_objects):
			vertices = []
			uvs = []
			polygons = []
			
			num_vrtx = struct.unpack('<I', f.read(0x4))[0]
			
			for j in range(0, num_vrtx):
				vertex = struct.unpack('<3f', f.read(0xC))
				vertices.append(vertex)
			
			for j in range(0, num_vrtx):
				uv = struct.unpack('<2f', f.read(0x8))
				uvs.append(uv)
			
			num_plgn = struct.unpack('<I', f.read(0x4))[0]
			
			for j in range(0, num_plgn):
				polygon = struct.unpack('<3H', f.read(0x6))
				polygons.append(polygon)
			
			texture_length = struct.unpack('<I', f.read(0x4))[0]
			texture_name = f.read(texture_length)
			
			objects[i] = [vertices, uvs, polygons, texture_name]
		
		num_walls = struct.unpack('<I', f.read(0x4))[0]
		
		for i in range (0, num_walls):
			vertices = []
			uvs = []
			
			num_vrtx = struct.unpack('<I', f.read(0x4))[0]
			
			for j in range(0, num_vrtx):
				vertex = struct.unpack('<3f', f.read(0xC))
				vertices.append(vertex)
			
			for j in range(0, num_vrtx):
				uv = struct.unpack('<2f', f.read(0x8))
				uv = [uv[0], -uv[1] + 1.0]
				uvs.append(uv)
			
			texture_length = struct.unpack('<I', f.read(0x4))[0]
			texture_name = f.read(texture_length)
			
			walls[i] = [vertices, uvs, [], texture_name]
		
		vertices = []
		uvs = []
		quads = {}
		sprite = []
		
		polygon_indices = {}
		
		num_vrtx = struct.unpack('<I', f.read(0x4))[0]
		
		for j in range(0, num_vrtx):
			vertex = struct.unpack('<3f', f.read(0xC))
			vertices.append(vertex)
		
		for j in range(0, num_vrtx):
			uv = struct.unpack('<2f', f.read(0x8))
			uv = [uv[0], -uv[1] + 1.0]
			uvs.append(uv)
		
		num_quad = struct.unpack('<I', f.read(0x4))[0]
		
		for j in range(0, num_quad):
			quad_indices = struct.unpack('<4H', f.read(0x8))
			quad_center = struct.unpack('<3f', f.read(0xC))
			quad_quaternion = struct.unpack('<4f', f.read(0x10))
			num_plgn = struct.unpack('<I', f.read(0x4))[0]
			for k in range(0, num_plgn):
				wall_index = struct.unpack('<I', f.read(0x4))[0]
				polygon = struct.unpack('<3H', f.read(0x6))
				if wall_index not in polygon_indices:
					polygon_indices[wall_index] = []
				polygon_indices[wall_index].append(polygon)
			
			flat_images = struct.unpack('<I', f.read(0x4))[0]
			
			for k in range (0, flat_images):
				flat_image = struct.unpack('<I', f.read(0x4))[0]
			
			some_count = struct.unpack('<I', f.read(0x4))[0]
			
			for k in range(0, some_count):
				some_xyz = struct.unpack('<3f', f.read(0xC))
				some_index = struct.unpack('<I', f.read(0x4))[0]
				
				some_combined = [some_xyz, some_index]
				
				sprite.append(some_combined)
				
			quads[j] = [quad_indices, quad_center, quad_quaternion, sprite]
		
		texture_length = struct.unpack('<I', f.read(0x4))[0]
		texture_name = f.read(texture_length)
		
		walls_indices = polygon_indices
		
		road = [vertices, uvs, quads, texture_name]
		
		minimap_vertices = []
		for i in range(0, int(num_vrtx/2)):
			minimap_vertex = struct.unpack('<3f', f.read(0xC))
			minimap_vertices.append(minimap_vertex)
	
	trk = [coords, objects, walls, walls_indices, road, minimap_vertices]
	
	return trk


def create_object(name, vertices, uvs, faces, texture_name):
	#==================================================================================================
	#Building Mesh
	#==================================================================================================
	me_ob = bpy.data.meshes.new(name)
	obj = bpy.data.objects.new(name, me_ob)
	
	#Get a BMesh representation
	bm = bmesh.new()
	
	BMVert_dictionary = {}
	
	uvName = "UVMap" #or UV1Map
	uv_layer = bm.loops.layers.uv.get(uvName) or bm.loops.layers.uv.new(uvName)
	
	for i, position in enumerate(vertices):
		BMVert = bm.verts.new(position)
		BMVert.index = i
		BMVert_dictionary[i] = BMVert
	
	for i, face in enumerate(faces):
		if len(face) == 4:
			face_vertices = [BMVert_dictionary[face[3]], BMVert_dictionary[face[2]], BMVert_dictionary[face[0]], BMVert_dictionary[face[1]]]
			face_uvs = [uvs[face[3]], uvs[face[2]], uvs[face[0]], uvs[face[1]]]
		else:
			face_vertices = [BMVert_dictionary[face[0]], BMVert_dictionary[face[1]], BMVert_dictionary[face[2]]]
			face_uvs = [uvs[face[0]], uvs[face[1]], uvs[face[2]]]
		try:
			BMFace = bm.faces.get(face_vertices) or bm.faces.new(face_vertices)
		except:
			pass
		if BMFace.index != -1:
			BMFace = BMFace.copy(verts=False, edges=False)
		BMFace.index = i
		
		for loop, uv in zip(BMFace.loops, face_uvs):
			loop[uv_layer].uv = uv
	
	material_name = str(texture_name, 'ascii')
	mat = bpy.data.materials.get(material_name)
	if mat == None:
		mat = bpy.data.materials.new(material_name)
		mat.use_nodes = True
		mat.name = material_name
		
		if mat.node_tree.nodes[0].bl_idname != "ShaderNodeOutputMaterial":
			mat.node_tree.nodes[0].name = material_name
	
	if mat.name not in me_ob.materials:
		me_ob.materials.append(mat)
	
	#Finish up, write the bmesh back to the mesh
	bm.to_mesh(me_ob)
	bm.free()
	
	return obj


def option_to_resource_version(resource_version):
	if resource_version == 'OPT_A':
		return "Z3D"
	elif resource_version == 'OPT_B':
		return "TRK"
	return "None"


def clearScene(context): # OK
	#for obj in bpy.context.scene.objects:
	#	obj.select_set(True)
	#bpy.ops.object.delete()

	for block in bpy.data.objects:
		#if block.users == 0:
		bpy.data.objects.remove(block, do_unlink = True)

	for block in bpy.data.meshes:
		if block.users == 0:
			bpy.data.meshes.remove(block)

	for block in bpy.data.materials:
		if block.users == 0:
			bpy.data.materials.remove(block)

	for block in bpy.data.textures:
		if block.users == 0:
			bpy.data.textures.remove(block)

	for block in bpy.data.images:
		if block.users == 0:
			bpy.data.images.remove(block)
	
	for block in bpy.data.cameras:
		if block.users == 0:
			bpy.data.cameras.remove(block)
	
	for block in bpy.data.lights:
		if block.users == 0:
			bpy.data.lights.remove(block)
	
	for block in bpy.data.armatures:
		if block.users == 0:
			bpy.data.armatures.remove(block)
	
	for block in bpy.data.collections:
		if block.users == 0:
			bpy.data.collections.remove(block)
		else:
			bpy.data.collections.remove(block, do_unlink=True)


@orientation_helper(axis_forward='-Y', axis_up='Z')
class ImportNFSHSPPC(Operator, ImportHelper):
	"""Load a Need for Speed High Stakes Pocket PC model file"""
	bl_idname = "import_nfshsppc.data"	# important since its how bpy.ops.import_test.some_data is constructed
	bl_label = "Import models"
	bl_options = {'PRESET'}
	
	# ImportHelper mixin class uses this
	filename_ext = "*.z3d;*.trk",
	
	filter_glob: StringProperty(
			options={'HIDDEN'},
			default="*.z3d;*.trk",
			maxlen=255,	 # Max internal buffer length, longer would be clamped.
			)
	
	files: CollectionProperty(
			type=OperatorFileListElement,
			)
	
	directory: StringProperty(
			# subtype='DIR_PATH' is not needed to specify the selection mode.
			subtype='DIR_PATH',
			)
	
	# List of operator properties, the attributes will be assigned
	# to the class instance from the operator settings before calling.
	
	resource_version: EnumProperty(
			name="Resource version",
			description="Choose the resource version you want to load",
			items=(('OPT_A', "Z3D", "Car models"),
				   ('OPT_B', "TRK", "Track models")),
			default='OPT_A',
			)
	
	clear_scene: BoolProperty(
			name="Clear scene",
			description="Check in order to clear the scene",
			default=True,
			)
	
	def execute(self, context): # OK
		global_matrix = axis_conversion(from_forward='Z', from_up='Y', to_forward=self.axis_forward, to_up=self.axis_up).to_4x4()
		
		if len(self.files) > 1:
			os.system('cls')
		
			files_path = []
			for file_elem in self.files:
				files_path.append(os.path.join(self.directory, file_elem.name))
			
			print("Importing %d files" % len(files_path))
			
			if self.clear_scene == True:
				print("Clearing initial scene...")
				clearScene(context)
				print("Setting 'clear_scene' to False now...")
				self.clear_scene = False
			
			print()
			
			for file_path in files_path:
				status = main(context, file_path, option_to_resource_version(self.resource_version), self.clear_scene, global_matrix)
				
				if status == {"CANCELLED"}:
					self.report({"ERROR"}, "Importing of file %s has been cancelled. Check the system console for information." % os.path.splitext(os.path.basename(file_path))[0])
				
				print()
				
			return {'FINISHED'}
		elif os.path.isfile(self.filepath) == False:
			os.system('cls')
			
			files_path = []
			for file in os.listdir(self.filepath):
				file_path = os.path.join(self.filepath, file)
				if os.path.isfile(file_path) == True:
					files_path.append(file_path)
				print("Importing %d files" % len(files_path))
			
			for file_path in files_path:
				status = main(context, file_path, option_to_resource_version(self.resource_version), self.clear_scene, global_matrix)
				
				if status == {"CANCELLED"}:
					self.report({"ERROR"}, "Importing of file %s has been cancelled. Check the system console for information." % os.path.splitext(os.path.basename(file_path))[0])
				
				print()
				
			return {'FINISHED'}
		else:
			os.system('cls')
			
			status = main(context, self.filepath, option_to_resource_version(self.resource_version), self.clear_scene, global_matrix)
			
			if status == {"CANCELLED"}:
				self.report({"ERROR"}, "Importing has been cancelled. Check the system console for information.")
			
			return status
	
	def draw(self, context):
		layout = self.layout
		layout.use_property_split = True
		layout.use_property_decorate = False  # No animation.
		
		sfile = context.space_data
		operator = sfile.active_operator
		
		##
		box = layout.box()
		split = box.split(factor=0.75)
		col = split.column(align=True)
		col.label(text="Settings", icon="SETTINGS")
		
		box.prop(operator, "resource_version")
		if operator.resource_version == 'OPT_B':
			box.label(text="Experimental", icon="ERROR")
		
		##
		box = layout.box()
		split = box.split(factor=0.75)
		col = split.column(align=True)
		col.label(text="Preferences", icon="OPTIONS")
		
		box.prop(operator, "clear_scene")
		
		##
		box = layout.box()
		split = box.split(factor=0.75)
		col = split.column(align=True)
		col.label(text="Blender orientation", icon="OBJECT_DATA")
		
		row = box.row(align=True)
		row.label(text="Forward axis")
		row.use_property_split = False
		row.prop_enum(operator, "axis_forward", 'X', text='X')
		row.prop_enum(operator, "axis_forward", 'Y', text='Y')
		row.prop_enum(operator, "axis_forward", 'Z', text='Z')
		row.prop_enum(operator, "axis_forward", '-X', text='-X')
		row.prop_enum(operator, "axis_forward", '-Y', text='-Y')
		row.prop_enum(operator, "axis_forward", '-Z', text='-Z')
		
		row = box.row(align=True)
		row.label(text="Up axis")
		row.use_property_split = False
		row.prop_enum(operator, "axis_up", 'X', text='X')
		row.prop_enum(operator, "axis_up", 'Y', text='Y')
		row.prop_enum(operator, "axis_up", 'Z', text='Z')
		row.prop_enum(operator, "axis_up", '-X', text='-X')
		row.prop_enum(operator, "axis_up", '-Y', text='-Y')
		row.prop_enum(operator, "axis_up", '-Z', text='-Z')


def menu_func_import(self, context): # OK
	pcoll = preview_collections["main"]
	my_icon = pcoll["my_icon"]
	self.layout.operator(ImportNFSHSPPC.bl_idname, text="Need for Speed High Stakes Pocket PC (.z3d, .trk)", icon_value=my_icon.icon_id)


classes = (
		ImportNFSHSPPC,
)

preview_collections = {}


def register(): # OK
	import bpy.utils.previews
	pcoll = bpy.utils.previews.new()
	
	my_icons_dir = os.path.join(os.path.dirname(__file__), "polly_icons")
	pcoll.load("my_icon", os.path.join(my_icons_dir, "nfshs_ppc_icon.png"), 'IMAGE')

	preview_collections["main"] = pcoll
	
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister(): # OK
	for pcoll in preview_collections.values():
		bpy.utils.previews.remove(pcoll)
	preview_collections.clear()
	
	for cls in classes:
		bpy.utils.unregister_class(cls)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
	register()
