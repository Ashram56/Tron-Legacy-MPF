# MSDF glyphs are generated on the main thread when first drawn (seconds per string on ARM)

**Project:** https://github.com/godotengine/godot

## Environment

- Godot 4.6.3 stable, Linux arm64, Mobile renderer
- Jetson Xavier NX, nvpmodel mode 5 (4 Carmel cores at 1.9 GHz)
- `FontFile` with `multichannel_signed_distance_field = true`, `msdf_size = 256`, `msdf_pixel_range` 16 and 192

## What happens

The first time a character is drawn, its MSDF is generated synchronously on the thread that draws it, usually the
main thread. With Orbitron (an OFL font) and the 94 printable ASCII characters:

| `msdf_pixel_range` | Time on the main thread |
|---|---|
| 16 | 6.8 s |
| 192 (wide copy, for outlines and glow) | 45 s |

So the first lines of text froze the game for 20-30 s. A larger pixel range costs much more, which the docs do not
say.

## Workaround

Generate the glyphs once offline (`font_render_glyph()` for every character in a headless script), save the
`FontFile` with `ResourceSaver.save()` (the generated glyph cache is kept), and load the saved resource at
start-up with `ResourceLoader.load_threaded_request()`. Text renders identically (0 differing pixels in our
comparison). Script: `game/tools/bake_fonts.gd`.

## Expected

Glyph generation for MSDF fonts on a worker thread (show the glyph a frame later), or an editor/import option to
pre-render a character set, and a note in the `msdf_pixel_range` docs about its cost.
