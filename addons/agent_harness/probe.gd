extends Node
## AgentProbe (autoload): helpers for AI agents driving the game through godot-e2e.
## The Python side lives in tools/gdharness. Does nothing until one of its methods is called,
## so it's harmless in normal play.
##
## What it adds on top of godot-e2e:
##  - [method eval]: query any expression with a node as `self`, so tests don't need a
##    debug_* getter in the game for every question.
##  - [method invoke] / [method set_value]: pass nodes as arguments ({"_node": path}) and assign
##    typed arrays, which godot-e2e's plain call/set can't.
##  - [method capture_sequence]: screenshots taken in-engine every N physics frames, so frame
##    timing is exact (a round trip per screenshot would drift).
##  - [method watch_signal]: records every emission of a signal (args + physics frame), so tests
##    can wait on the events an event-driven game is built from.
##  - [method tree]: a text dump of the scene tree, to check structure without the editor.
##  - [method load_all] / [method isolate_scene]: every script/scene/resource parses, and a
##    scene runs on its own (no hard-coded parents, nothing leaked under /root).

const NODE_TAG := "_node"
## Engine singletons usable by name inside [method eval] expressions.
const SINGLETONS: Array[String] = ["Engine", "Input", "Time", "OS", "ProjectSettings", "DisplayServer"]
## Folders [method load_all] never enters (besides any folder holding a .gdignore).
const SKIP_DIRS: Array[String] = ["res://addons", "res://.godot", "res://tools", "res://tests", "res://screenshots"]

var sequence_running := false
var sequence_files: PackedStringArray = []

var _watches := {}  # key -> Array of {"frame": int, "args": Array}
var _watch_callables := {}  # key -> [Object, signal name, Callable]
var _sandbox: Node = null
var _root_before: Array[String] = []


## Evaluates a GDScript [Expression] with the node at [param base_path] as its base instance
## (its methods can be called by name, its properties read by name or as `self.prop`, and the
## engine singletons in [constant SINGLETONS] by name). Errors are logged,
## so the harness turns them into test failures.
func eval(expression: String, base_path := "/root") -> Variant:
	var base := get_node_or_null(base_path)
	if base == null:
		push_error("AgentProbe.eval: no node at %s" % base_path)
		return null
	var expr := Expression.new()
	if expr.parse(expression, SINGLETONS) != OK:
		push_error("AgentProbe.eval: can't parse '%s': %s" % [expression, expr.get_error_text()])
		return null
	var inputs := []
	for name in SINGLETONS:
		inputs.append(Engine.get_singleton(name))
	var result: Variant = expr.execute(inputs, base)
	if expr.has_execute_failed():
		push_error("AgentProbe.eval: '%s' failed: %s" % [expression, expr.get_error_text()])
		return null
	return _to_wire(result)


## Calls [param method] on the node at [param path]. Arguments shaped {"_node": "/root/..."}
## are replaced by that node. Nodes in the result come back as {"_node": path}.
func invoke(path: String, method: String, args: Array = []) -> Variant:
	var node := get_node_or_null(path)
	if node == null:
		push_error("AgentProbe.invoke: no node at %s" % path)
		return null
	return _to_wire(node.callv(method, _resolve(args)))


## Sets a property, converting plain arrays into typed ones when the property is typed.
func set_value(path: String, property: String, value: Variant) -> void:
	var node := get_node_or_null(path)
	if node == null:
		push_error("AgentProbe.set_value: no node at %s" % path)
		return
	var resolved: Variant = _resolve(value)
	var current: Variant = node.get(property)
	if current is Array and (current as Array).is_typed() and resolved is Array:
		(current as Array).assign(resolved)
	else:
		node.set(property, resolved)


## Physics frames since start: the harness measures game time with it.
func physics_frames() -> int:
	return Engine.get_physics_frames()


## Captures [param count] screenshots, one every [param every] physics frames, into
## [param dir] (absolute path). Returns immediately; poll [member sequence_running].
func capture_sequence(dir: String, count: int, every: int) -> void:
	if DisplayServer.get_name() == "headless":
		push_error("AgentProbe.capture_sequence: needs a window (run the harness with window=True)")
		return
	sequence_files = []
	sequence_running = true
	_capture(dir, count, maxi(every, 1))


func _capture(dir: String, count: int, every: int) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	for i in count:
		if i > 0:
			for f in every:
				await get_tree().physics_frame
		await RenderingServer.frame_post_draw
		var image := get_viewport().get_texture().get_image()
		var path := dir.path_join("%03d.png" % i)
		image.save_png(path)
		sequence_files.append(path)
	sequence_running = false


## Starts recording emissions of [param signal_name] on the node at [param path]. Returns the
## key for [method signal_log] / [method unwatch_signal]; watching the same signal twice resets it.
func watch_signal(path: String, signal_name: String) -> String:
	var node := get_node_or_null(path)
	if node == null:
		push_error("AgentProbe.watch_signal: no node at %s" % path)
		return ""
	if not node.has_signal(signal_name):
		push_error("AgentProbe.watch_signal: %s has no signal '%s'" % [path, signal_name])
		return ""
	var key := "%s:%s" % [path, signal_name]
	unwatch_signal(key)
	var callable := _record_emission.bind(key)
	node.connect(signal_name, callable)
	_watches[key] = []
	_watch_callables[key] = [node, signal_name, callable]
	return key


## Emissions recorded for [param key] since [method watch_signal] (or the last clear):
## [{"frame": physics frame, "args": [...]}, ...].
func signal_log(key: String, clear := false) -> Array:
	var entries: Array = _watches.get(key, [])
	if clear and _watches.has(key):
		_watches[key] = []
	return entries


func unwatch_signal(key: String) -> void:
	if _watch_callables.has(key):
		var entry: Array = _watch_callables[key]
		var node: Object = entry[0]
		if is_instance_valid(node) and node.is_connected(entry[1], entry[2]):
			node.disconnect(entry[1], entry[2])
	_watch_callables.erase(key)
	_watches.erase(key)


# Bound arguments go last, so the key arrives after the signal's own arguments.
func _record_emission(...args: Array) -> void:
	var key: String = args.pop_back()
	if _watches.has(key):
		_watches[key].append({"frame": Engine.get_physics_frames(), "args": _to_wire(args)})


## The tree under [param path] as indented text: "Name (Type) script.gd", up to [param depth]
## levels. Cheap way to check scene structure (and what a spawner left behind).
func tree(path := "/root", depth := 4) -> String:
	var node := get_node_or_null(path)
	if node == null:
		push_error("AgentProbe.tree: no node at %s" % path)
		return ""
	var lines: PackedStringArray = []
	_tree_lines(node, 0, depth, lines)
	return "\n".join(lines)


func _tree_lines(node: Node, level: int, depth: int, lines: PackedStringArray) -> void:
	var script: Script = node.get_script()
	var extra := "  " + script.resource_path.get_file() if script else ""
	var unique := "%" if node.is_unique_name_in_owner() else ""
	lines.append("%s%s%s (%s)%s" % ["  ".repeat(level), unique, node.name, node.get_class(), extra])
	if level >= depth:
		if node.get_child_count() > 0:
			lines.append("%s  ... %d children" % ["  ".repeat(level), node.get_child_count()])
		return
	for child in node.get_children():
		_tree_lines(child, level + 1, depth, lines)


## Loads every .gd/.tscn/.tres/.res under [param dir] (skipping [constant SKIP_DIRS] and folders
## with a .gdignore). Parse errors and broken dependencies are logged by the engine, so the
## harness turns them into failures. Returns the paths that failed to load.
func load_all(dir := "res://") -> PackedStringArray:
	var failed: PackedStringArray = []
	for path in _resource_files(dir):
		var res := ResourceLoader.load(path)
		# A script with a parse error still loads, as a Script that can't be instantiated.
		if res == null or (res is Script and not (res as Script).can_instantiate() and not (res as Script).is_abstract()):
			failed.append(path)
	return failed


## Every .tscn under [param dir] (same skipping rules as [method load_all]).
func scene_files(dir := "res://") -> PackedStringArray:
	var out: PackedStringArray = []
	for path in _resource_files(dir):
		if path.ends_with(".tscn"):
			out.append(path)
	return out


func _resource_files(dir: String) -> PackedStringArray:
	var out: PackedStringArray = []
	if dir.trim_suffix("/") in SKIP_DIRS or FileAccess.file_exists(dir.path_join(".gdignore")):
		return out
	for file in DirAccess.get_files_at(dir):
		if file.get_extension() in ["gd", "tscn", "tres", "res"]:
			out.append(dir.path_join(file))
	for sub in DirAccess.get_directories_at(dir):
		if not sub.begins_with("."):
			out.append_array(_resource_files(dir.path_join(sub)))
	return out


## Instances [param scene_path] alone under a sandbox node at /root/AgentSandbox (the "F6 test":
## a scene must run without a particular parent). Advance frames, then [method end_isolation].
func isolate_scene(scene_path: String) -> bool:
	end_isolation()
	var packed := load(scene_path) as PackedScene
	if packed == null:
		push_error("AgentProbe.isolate_scene: can't load %s" % scene_path)
		return false
	_root_before = []
	for child in get_tree().root.get_children():
		_root_before.append(str(child.name))
	_sandbox = Node.new()
	_sandbox.name = "AgentSandbox"
	get_tree().root.add_child(_sandbox)
	_sandbox.add_child(packed.instantiate())
	return true


## Frees the isolated scene. Returns the names of nodes it left directly under /root (spawned
## into the root instead of a container it owns: they would survive a restart).
func end_isolation() -> PackedStringArray:
	var leaked: PackedStringArray = []
	if _sandbox == null:
		return leaked
	for child in get_tree().root.get_children():
		if child != _sandbox and not str(child.name) in _root_before:
			leaked.append(str(child.name))
			child.queue_free()
	_sandbox.queue_free()
	_sandbox = null
	return leaked


func _resolve(value: Variant) -> Variant:
	if value is Dictionary:
		if value.size() == 1 and value.has(NODE_TAG):
			return get_node_or_null(str(value[NODE_TAG]))
		var out := {}
		for k in value:
			out[k] = _resolve(value[k])
		return out
	if value is Array:
		var out := []
		for v in value:
			out.append(_resolve(v))
		return out
	return value


func _to_wire(value: Variant) -> Variant:
	if value is Node:
		return {NODE_TAG: str((value as Node).get_path())} if (value as Node).is_inside_tree() else null
	if value is Object:
		return str(value)
	if value is Array:
		var out := []
		for v in value:
			out.append(_to_wire(v))
		return out
	if value is Dictionary:
		var out := {}
		for k in value:
			out[_to_wire(k) if not (k is Node) else str((k as Node).get_path())] = _to_wire(value[k])
		return out
	return value
