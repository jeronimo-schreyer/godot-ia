@tool
extends EditorPlugin

const AUTOLOAD := "AgentProbe"


func _enable_plugin() -> void:
	add_autoload_singleton(AUTOLOAD, "res://addons/agent_harness/probe.gd")


func _disable_plugin() -> void:
	remove_autoload_singleton(AUTOLOAD)
