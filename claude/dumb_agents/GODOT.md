# Dumb agent guide

Mistakes made by coding agents that do not know Godot, collected from real
diffs in this repo. Each entry: what was done, what it broke, the rule.

## 0. Compile before you claim anything

`python3 test/run_unit.py` loads every `.gd`, `.tscn` and `.tres` under
`res://` and fails on the first one that does not compile. Scripts compile
lazily, on first load, so a broken playable surfaces only when its card is
played. Run it after every edit and before every commit. Nothing below would
have survived it.

## 1. Unbalanced parentheses

`hp_component.gd`: the `)` closing `timeout.connect(` was dropped while the
lambda body was wrapped in an `if`. Error: `Could not parse global class
"HpComponent"`.

Rule: after editing a multi-line call that holds a lambda, count the closing
parens. Then run the unit check.

## 2. Calling instance methods on a class

`EntityAreaManager.overlaps(pos)`. Error: `Cannot call non-static function
"overlaps()" on the class "EntityAreaManager" directly`.

A `class_name` is a type, not a singleton. Only autoloads (`ArgsParser`,
`Loggero`, `MyUtils`) and `static func`s are callable by bare name. Get the
instance from what owns it: `character_trait.get_entity_area().overlaps(pos)`.

## 3. Godot 3 API

`enemies.empty()`. Godot 4 is `is_empty()`. On an untyped array this is a
runtime error the analyzer never sees.

Rule: Godot 4.5 API only. Type your variables (`var enemies: Array`) so a
nonexistent method fails at compile time.

## 4. `.tscn` section order

`heart.tscn` and `flamingo.tscn` put `[sub_resource]` blocks after the
`[node]` blocks that reference them. Error on load: `Parse Error: Invalid
parameter`; the parent scene then fails with `[ext_resource] referenced
non-existent resource`.

Order is fixed: header, `[ext_resource]`, `[sub_resource]`, `[node]` (or
`[resource]`). `load_steps` = ext_resources + sub_resources + 1. Copy an
existing scene and edit it; never type one from memory.

## 5. Invented UIDs

Seen: `uid="uid://heart_scene_uid"`, `.gd.uid` files holding 32-hex UUIDs,
`heart.tscn.uid` sidecars, `ext_resource uid=` values matching no sidecar.

A UID is `uid://` plus up to 13 chars of `[a-y0-8]`, minted by the editor.
`.uid` sidecars exist for scripts only; scenes and resources carry the uid in
their header. Rules: never invent one. Either open the project in the editor
(or run `Godot --headless --import`) so it mints sidecars, then copy them, or
omit `uid=` altogether: a path-only `ext_resource` loads fine.

## 6. Growing properties at runtime

```
if not "wander_component" in self:
    self.wander_component = WanderComponent.new(...)
```

GDScript objects do not grow properties; the assignment is a runtime error.
Declare the member (`var _wander_component: WanderComponent`) and build it in
`_init`, as `zombie.gd` does. When a sibling entity already does the thing,
copy its pattern.

## 7. Comment stripping that deletes code

Commit `e5aa7e7 refactor(comments)` removed `const FETCH_TIME_INTERVAL` and
`const SPAWN_DELAY` together with the comments above them. HEAD stopped
compiling (`SILENCE_THRESHOLD_SEC = FETCH_TIME_INTERVAL * 2`,
`Constants.SPAWN_DELAY` in `play_card_rpc.gd`).

Rule: a comment pass removes only `#` lines and trailing `# ...`. The diff
must show zero code lines removed. Compile before committing.

## 8. Re-implementing the base class

`heart_collision_component.gd` overrode `_is_dead_entity` with an untyped copy
of the base method and checked `"health_trait" in collider` twice.

Rule: read the base class before overriding. Override only what changes.

## 9. Plan checkpoints are not optional

`FLAMINGO-PLAN.md` gated steps 7, 13 and 18 on `run_unit.py` and step 14 on
opening the editor. None ran. Step 4 asked "with no heal anywhere, is the
behaviour what it was?"; the answer was no (`_last_expected_hp = -1` skipped
the first assert for every entity) and nobody checked.

Rule: at a checkpoint, run the command and answer the question against the
code, initial state included. Report the output, not the intention.

## 10. Reading errors

`SCRIPT ERROR: Parse Error: ...` is runtime output. `Parser Error: ...` is the
editor's script panel; after a fix it can show a stale cascade (`Could not
parse global class "X"`) until the script is reopened. Reproduce headless with
`python3 test/run_unit.py` before chasing it.
