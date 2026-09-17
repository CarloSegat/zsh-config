# Dumb agent guide

Mistakes made by coding agents that do not know Godot 4, collected from real
diffs. Each entry: what was done, what it broke, the rule. Entries name no
repo, file or commit; that provenance is in `RUNS.md`.

## 0. Compile before you claim anything

Godot compiles a script lazily, on first load, so a broken script surfaces
only when something instantiates it. The plan's check command loads every
`.gd`, `.tscn` and `.tres` and fails on the first that does not compile. Run
it after every edit and before every commit. Nothing below would have
survived it.

## 1. Unbalanced parentheses

Wrapping a lambda body in an `if` dropped the `)` that closed the call:

    timer.timeout.connect(func() -> void:
        if _alive:
            _tick()

Error: `Could not parse global class "X"`.

Rule: after editing a multi-line call that holds a lambda, count the closing
parens. Then run the check.

## 2. Calling instance methods on a class

`EntityArea.overlaps(pos)`, where `EntityArea` is a `class_name`. Error:
`Cannot call non-static function "overlaps()" on the class "EntityArea"
directly`.

A `class_name` is a type, not a singleton. Only autoloads (the `[autoload]`
section of `project.godot`) and `static func`s are callable by bare name. Get
the instance from whatever holds it: `holder.get_entity_area().overlaps(pos)`.

## 3. Godot 3 API

`enemies.empty()`. Godot 4 is `is_empty()`. On an untyped array this is a
runtime error the analyzer never sees.

Rule: Godot 4.5 API only. Type your variables (`var enemies: Array`) so a
nonexistent method fails at compile time.

## 4. `.tscn` section order

Two new scenes put `[sub_resource]` blocks after the `[node]` blocks that
reference them. Error on load: `Parse Error: Invalid parameter`; the parent
scene then fails with `[ext_resource] referenced non-existent resource`.

Order is fixed: header, `[ext_resource]`, `[sub_resource]`, `[node]` (or
`[resource]`). `load_steps` = ext_resources + sub_resources + 1. Copy an
existing scene and edit it; never type one from memory.

## 5. Invented UIDs

Seen: `uid="uid://my_scene_uid"`, `.gd.uid` files holding 32-hex UUIDs,
`.tscn.uid` sidecars, `ext_resource uid=` values matching no sidecar.

A UID is `uid://` plus up to 13 chars of `[a-y0-8]`, minted by the editor.
`.uid` sidecars exist for scripts only; scenes and resources carry the uid in
their header. Rules: never invent one. Either run `godot --headless --import`
(or open the editor) so it mints sidecars, then copy them, or omit `uid=`
altogether: a path-only `ext_resource` loads fine.

## 6. Growing properties at runtime

    if not "wander_component" in self:
        self.wander_component = WanderComponent.new(...)

GDScript objects do not grow properties; the assignment is a runtime error.
Declare the member and build it in `_init`:

    var _wander_component: WanderComponent

    func _init() -> void:
        _wander_component = WanderComponent.new(...)

When a sibling class already does the thing, copy its pattern.

## 7. Comment stripping that deletes code

A "remove comments" pass deleted this whole block:

    # seconds between polls
    const FETCH_TIME_INTERVAL := 2.0

The constant went with its comment. Its reader, `FETCH_TIME_INTERVAL * 2` in
another file, stopped compiling.

Rule: a comment pass removes only `#` lines and trailing `# ...`. Prove it per
touched file; the command prints nothing when only comments changed:

    strip() { sed 's/#.*$//' "$@" | grep -v '^[[:space:]]*$' | sed 's/[[:space:]]*$//'; }
    diff <(git show HEAD:<path> | strip) <(strip <path>)

## 8. Re-implementing the base class

A subclass overrode `_is_dead(collider)` with an untyped paste of the base
body, plus a second copy of a check the base already made.

Rule: read the base class before overriding. Override only what changes.

## 9. Plan checkpoints are not optional

A plan gated three steps on the check command and one on opening the editor.
None ran. One step asked "with the feature off, is the behaviour what it
was?"; the answer was no (a `-1` sentinel made the first assert skip for every
entity) and nobody checked.

Rule: at a checkpoint, run the command and answer the question against the
code, initial state included. Report the output, not the intention.

## 10. Reading errors

`SCRIPT ERROR: Parse Error: ...` is runtime output. `Parser Error: ...` is the
editor's script panel; after a fix it can show a stale cascade (`Could not
parse global class "X"`) until the script is reopened. Reproduce headless with
the check command before chasing it.

## 11. Work that runs while the node is hidden

An overlay that is a permanent child of the main scene, toggled with
`show()`/`hide()` and never freed, drove `position` from `_process` and looped
an infinite tween over a label's `text`. Both ran for the whole process:
through every fight and inside the headless dedicated server.

Rule: a node that lives in the tree from startup and is toggled with
`show()`/`hide()` gates its work on visibility:

    func _ready() -> void:
        visibility_changed.connect(_on_visibility_changed)
        _on_visibility_changed()

    func _on_visibility_changed() -> void:
        var shown := is_visible_in_tree()
        set_process(shown)
        if _tween:
            _tween.kill()
        if shown:
            _tween = _build_tween()

## 12. Constants measured off a glyph

An amplitude constant of `30.0` px was chosen against `30.6` px of measured
slack between an emoji glyph and its parent. Emoji come from the platform
fallback font and its metrics differ per OS, so where the glyph renders
taller the animated node leaves its parent, which does not clip.

Rule: never size a layout against a glyph box measured on one machine. Keep the
clearance a fraction of the box, or clip the parent.

## 13. `custom_minimum_size` inside a container

A `Control` inside a `VBoxContainer` was given `custom_minimum_size =
Vector2(520, 480)`; it measured 690 wide. `size_flags_horizontal` defaults to
`FILL`, so the container stretches it to the widest sibling and the `520` does
nothing.

Rule: in a container `custom_minimum_size` is a floor, not the size. To hold a
width, set `size_flags_horizontal = Control.SIZE_SHRINK_CENTER` (`4` in a
`.tscn`).

## 14. Text that grows under a centre alignment

`horizontal_alignment = 1` with `text = base + frames[i]`: the box stays the
same width, so every added dot re-centres the line and the word before it
slides left.

Rule: text that changes length under a centre alignment moves everything around
it. Pad every frame to the width of the widest, or give the growing part its own
left-aligned node.

## 15. The unit check does not run your code

A load-everything check calls `load()` and `can_instantiate()`. It compiles
scripts; it never instantiates a scene and never ticks a frame, so nothing
inside `_ready`, `_process` or a tween callback is exercised. A green check
proves the file parses, nothing more.

Rule: to prove behaviour, instantiate the scene headless and step frames:
`godot --headless --path . --script <probe>.gd` with `extends SceneTree`,
`await process_frame`, print what you measured, delete the probe.
