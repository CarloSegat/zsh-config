# Dumb agent guide

Mistakes made by coding agents that do not know Godot 4, collected from real
diffs. Each entry: what was done, what it broke, the rule. Entries name no
repo, file or commit.

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

## Planning a change

The entries above come from diffs. These come from plans: four agents planning
the same feature blind, three rounds. Same form — what was done, what it broke,
the rule.

## 19. Reaching two fields through the full parser

A screen needed three fields out of a server payload and called the parser the
game already had. That parser checks things the screen does not care about: it
rejects a row whose type it does not recognise, and builds the whole object
graph to reach two integers. Add a type on the server and the new screen
crashes, not just the feature the parser was written for. In an exported build
`assert` is stripped, so it does not even fail there — it returns a half-built
object and the crash moves to the first field you read.

Rule: parse what you need, into your own small type, where the payload arrives.
Drop rows that do not carry it, so nothing downstream — a divide by a max, a
lookup by name — is handed a zero or a null. Use the big parser only when you
want what it validates.

## 20. The signal fires before the listener exists

A view had to redraw when its data changed, so the design was one signal,
emitted wherever the data is written. That covers every later change. It does
not cover the one that already happened: a caller refreshes the data and then
opens the view, so the data is current before the view exists and the signal
fired with nobody connected. A view that only connects the signal comes up
empty.

Rule: connecting a signal handles changes after you exist, not the state you
were born into. In `_ready`, draw from the data as it is, then connect — both
paths calling the same function. Check what opens your scene: if it refreshes
first and opens second, no signal is coming.

## 21. No way to see the feature working

The feature was four speed tiers by hp. Real data almost never spans all four
at once, so launching the game shows one or two tiers and proves nothing. The
plans that skipped this ended their verification at "look at it and see".

Rule: write an e2e test, built like the fight tests already in the suite. Load
the real scene, seed the data so every state is present in one run, let it run
a few frames, then read the state back off the nodes and assert it. The seeding
belongs inside the test, not in a manual step, so the reviewer runs one command
and the machine says whether all four tiers are right.

## 22. Parking a node above the scene that owns it

A popup belonged to one screen. It was put on the layer that survives scene
changes, so it would not vanish mid-fade. Now it outlives the screen: it shows
up over the next one, and every transition needs a line to hide it. Miss one
and it hangs over the wrong screen.

Rule: put a node inside the scene it belongs to and let the scene transition
free it. Moving it higher to dodge one fade costs a hide call in every other
transition, forever.

## 23. An if-else chain per type, instead of a dictionary

A screen showed different rows for each of five card types, with one `if` per
type — the same five-way chain a parser elsewhere already had. A sixth type
means editing both.

Rule: if every arm of the chain does the same thing with different values, the
values belong in a `Dictionary` keyed by the type and the code that walks it is
written once. A chain is only right when the arms do different work.

## 24. Copying the nearest example, bug and all

A new panel had to show current and max hp. The existing card widget prints
them the wrong way round — max first. Three plans spotted that; one copied it.

Rule: read the pattern you copy and check it against what it should produce.
"The other file does it this way" is a starting point, not a justification.

## 25. Claims about the code with nothing to check them against

The plans that cited `file:line` per claim were the ones whose claims held up.
The plan that cited bare filenames, a glob, and a path that did not exist yet
was wrong most often.

Rule: every statement about existing code carries its path and line. A glob is
not a citation, and a path you intend to create is marked new, not cited.
