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

## 13. `custom_minimum_size` inside a container

A `Control` inside a `VBoxContainer` was given `custom_minimum_size =
Vector2(520, 480)`; it measured 690 wide. `size_flags_horizontal` defaults to
`FILL`, so the container stretches it to the widest sibling and the `520` does
nothing.

Rule: in a container `custom_minimum_size` is a floor, not the size. To hold a
width, set `size_flags_horizontal = Control.SIZE_SHRINK_CENTER` (`4` in a
`.tscn`).

## 15. The unit check does not run your code

A load-everything check calls `load()` and `can_instantiate()`. It compiles
scripts; it never instantiates a scene and never ticks a frame, so nothing
inside `_ready`, `_process` or a tween callback is exercised. A green check
proves the file parses, nothing more.

Rule: to prove behaviour, instantiate the scene headless and step frames:
`godot --headless --path . --script <probe>.gd` with `extends SceneTree`,
`await process_frame`, print what you measured, delete the probe.

## 16. `PathFollow2D.rotates` turns local +X, not a Label's glyph axis

`PathFollow2D.rotates = true` (the default) sets the follow's local +X axis
along the path tangent. A `Label` draws its glyph upright, "down" along local
+Y. Left uncompensated, a text/icon child ends up rotated 90° off the
direction of travel, consistently, at every point on the path.

Rule: a `Control` child of a rotating `PathFollow2D` needs its own
compensating `rotation` so its forward axis lines up with local +X. Don't
trust a memorized sign; verify empirically: read `rotation` on a straight
test segment of known direction, work out which offset makes the child's
forward axis match it.

## 17. `Curve2D.add_point()` with no handles + `PathFollow2D.v_offset` swings at corners

`curve.add_point(p)` with default (zero) in/out handles makes a straight
segment; the tangent jumps instantly at each interior point. `v_offset` is
applied in the follow's local (rotated) frame, so at a sharp corner an
offset child doesn't just re-orient, it swings sideways by up to `2 *
v_offset` in a single frame — far more than a `v_offset = 0` child hitting
the same corner. Reads as "jerky" motion, worse the further a lane sits from
center.

Rule: give interior points real Bezier handles (e.g. Catmull-Rom-style:
average the incoming/outgoing segment directions, scale to a fraction of the
shorter segment) so the tangent turns gradually. Confirm headless: step
frames, diff position between consecutive frames, corner crossings must not
spike above neighboring frames.

## 18. Sibling paths sharing leading points drift back into full overlap

Two `PackedVector2Array` courses that start with the same points, then
diverge, each get their own looping population of nodes on the shared
segment. Their loop periods differ (different total course length), so the
two populations drift in and out of phase forever, periodically landing back
on the exact same pixels.

Symptom looks like a rendering "flicker" or pop-in but is real duplicate
icons repeatedly coinciding and separating; only on the shared segment, and
never settles since the two course lengths set an unrelated drift period.

Rule: a fork/confluence point is one shared point, not a shared prefix.
Exactly one course owns a given segment; a course starting after a merge
begins at the fork coordinate, not a copy of the segment before it. Grep
sibling point-array constants for identical leading elements before
shipping.
