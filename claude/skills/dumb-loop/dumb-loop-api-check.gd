extends SceneTree

const BUILTINS: PackedStringArray = ["Array", "Dictionary", "String", "StringName", "NodePath", "Vector2", "Vector2i", "Vector3", "Vector3i", "Vector4", "Vector4i", "Color", "Rect2", "Rect2i", "Transform2D", "Transform3D", "Basis", "Quaternion", "Plane", "AABB", "Callable", "Signal", "RID", "PackedByteArray", "PackedColorArray", "PackedFloat32Array", "PackedFloat64Array", "PackedInt32Array", "PackedInt64Array", "PackedStringArray", "PackedVector2Array", "PackedVector3Array", "PackedVector4Array", "int", "float", "bool", "Variant"]
const MAX_DEPTH: int = 8


func _init() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.is_empty() or not FileAccess.file_exists(args[0]):
		print("APICHECK usage: tokens file missing")
		quit(2)
		return
	var missing: int = 0
	for token in FileAccess.get_file_as_string(args[0]).split("\n", false):
		var t: String = token.strip_edges()
		if t.is_empty():
			continue
		var verdict: String = _check(t)
		print("APICHECK %s %s" % [verdict, t])
		if verdict.begins_with("MISSING"):
			missing += 1
	quit(1 if missing > 0 else 0)


func _check(token: String) -> String:
	var idx: int = token.find(".")
	var cls: String = token if idx < 0 else token.substr(0, idx)
	var mem: String = "" if idx < 0 else token.substr(idx + 1)
	if cls in BUILTINS:
		return "skip (builtin)"
	var path: String = _script_path(cls)
	if not ClassDB.class_exists(cls) and path == "":
		return "MISSING (no such class)"
	if mem == "" or mem == "new":
		return "ok"
	if path == "":
		return "ok" if _engine_has_member(cls, mem) else "MISSING"
	if path.ends_with(".tscn"):
		return "skip (autoload scene)"
	return "ok" if _script_has_member(path, mem, 0) else "MISSING"


func _script_path(cls: String) -> String:
	for entry in ProjectSettings.get_global_class_list():
		if entry["class"] == cls:
			return entry["path"]
	if ProjectSettings.has_setting("autoload/" + cls):
		return str(ProjectSettings.get_setting("autoload/" + cls)).trim_prefix("*")
	return ""


func _engine_has_member(cls: String, mem: String) -> bool:
	if ClassDB.class_has_method(cls, mem, false) or ClassDB.class_has_signal(cls, mem):
		return true
	if ClassDB.class_has_integer_constant(cls, mem) or ClassDB.class_has_enum(cls, mem, false):
		return true
	for prop in ClassDB.class_get_property_list(cls, false):
		if prop["name"] == mem:
			return true
	return false


func _script_has_member(path: String, mem: String, depth: int) -> bool:
	if depth > MAX_DEPTH or not FileAccess.file_exists(path):
		return false
	var text: String = FileAccess.get_file_as_string(path)
	var decl: RegEx = RegEx.new()
	decl.compile("(?m)^\\s*(?:@\\w+(?:\\([^)]*\\))?\\s+)*(?:static\\s+)?(?:func|signal|const|var|enum|class)\\s+" + mem + "\\b")
	if decl.search(text) != null:
		return true
	var ext: RegEx = RegEx.new()
	ext.compile("(?m)^(?:class_name\\s+\\w+\\s+)?extends\\s+(\"[^\"]+\"|\\w+)")
	var m: RegExMatch = ext.search(text)
	if m == null:
		return false
	var base: String = m.get_string(1)
	if base.begins_with("\""):
		return _script_has_member(base.trim_prefix("\"").trim_suffix("\""), mem, depth + 1)
	if ClassDB.class_exists(base):
		return _engine_has_member(base, mem)
	var base_path: String = _script_path(base)
	return base_path != "" and _script_has_member(base_path, mem, depth + 1)
