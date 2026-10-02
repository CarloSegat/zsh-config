# Phone away until 2026-10-11

The owner has no Android phone until 2026-10-11 and batch-checks all phone work then. Until that date: never ask for a phone check or list one as a loose end. Append each phone check a task needs to the list below (date, repo, what to look at), then carry on.

On or after 2026-10-11: show the list as one batch, then delete this file and run `~/.config/claude/check-links.sh`.

## Pending phone checks

- 2026-10-01, emoji-godot task 30 (river follows curve, main `1abbc13`): `make android-install`, Fight, drops cover the whole edited river course at even spacing.
- 2026-10-01, emoji-godot phone logs (main `c0242ff`): `make android-install`, a fight, then `make android-logs`: Claude reads the logs with no special steps.
- 2026-10-01, emoji-godot task 42 (cloud bolt and fade, main `6b38e3f`): `make android-install`, a bot fight with lightning: the bolt swings at half the old tempo; the cloud glyph stays steady through bolt 1, pulses from midway through bolt 2 and pulses deeper through bolt 3.
- 2026-10-01, emoji-godot task 43 (tree obstacles, main `32f8b01`): `make android-install`, Fight: both groves show under the units, a dragon's fireball burns a tree (🔥 about 0.5 s, then gone). `make android-logs`: the `rebaked in <ms> ms` lines; `make android-perf MATCHES=3 LABEL=trees`: `frame_max_ms` around tree deaths. Chunked rebake only if these call for it.
- 2026-10-02, emoji-godot task 46 (bolt tip collision, main `d25efdb`): `make android-install`, a bot fight with lightning: the bolt swings the full width every pass, rotates around its tip (never flips) so the tip faces the target, keeps swinging on the spot after its target dies, and hurts units that walk into the tip.
