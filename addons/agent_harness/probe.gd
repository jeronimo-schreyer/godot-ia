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

const NODE_TAG := "_node"
## Engine singletons usable by name inside [method eval] expressions.
const SINGLETONS: Array[String] = ["Engine", "Input", "Time", "OS", "ProjectSettings", "DisplayServer"]

var sequence_running := false
var sequence_files: PackedStringArray = []


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
