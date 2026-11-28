# PinMAME waivers

Last-resort exceptions to "never build from an emulator capture". Each needs the owner's prior approval, in the form
`` `path` ... approved by Vincent YYYY-MM-DD ``. None granted yet. (Unicorn, for running isolated routines, is allowed: Vincent, 2026-11-25.)

## Checker warnings that are not waivers

`tools/check_strict_rule.py` warns on file names that contain "capture" (3 warnings, 2026-11-27): `game/tools/clip_capture.gd`,
`game/tools/dmd_capture.gd`, `game/tools/slide_capture.gd`. They save the picture of the game's own Godot viewport (the DMD or one slide
rendered by this repository) to PNG for the render checks (`scripts/render_diff.py`, `scripts/conform/`); none reads PinMAME output and none
builds a game asset. Read on 2026-11-27 from the three headers; no waiver is needed.
