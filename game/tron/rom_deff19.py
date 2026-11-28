"""deff_19 (0x01023a98): the score display, drawn each tick (FUN_010241a0 / dmd_show_pages 0x27830 then task_sleep(1)) in the page's body (columns 41-127;
the status panel on the left is FUN_010230ec's).

Per tick: page cleared (FUN_000276d0, FUN_00027290), the score (FUN_01023940), then, when the bottom-line phase allows it, the bottom line.
- the score: message 0x4e4 ("%,02lu") centred on x 0x54 in the font and row of the first record of the score-size table (ROM 0x40d3484, FUN_01022f5c:
  {min score, font, row, band top, band bottom}) whose minimum the score reaches. Then a band x 0x29-0x7f, rows top..bottom is filled with 0 (FUN_0002746c):
  playfield not valid (RAM 0x372e8 = 0, FUN_0000e4c4): the score blinks, the band is blanked while (counter - 0x3e) mod 14 is 0-6 once the tick counter
  (RAM 0x21117f4) reaches 0x3f (the whole band top..bottom); valid: a wipe, counter mod (2 * (bottom - top) * 2 + 0x3e) = m; from m = 0x3f: u = (m - 0x3e) >> 1,
  band top..top + u while u < (bottom - top), then top + u - (bottom - top)..bottom (FUN_01022fc0 = (bottom - top) * 2 = h, h / 2 = bottom - top ... see wipe()).
- the bottom line phase (deff_19 loop counters): 0x9c ticks with the BALL / CREDITS line, then 0x138 ticks of the special line (FUN_01023670: FUN_000249e4's text,
  else FUN_010237a0: the replay level text FUN_01023704), then 0x4e2 ticks of BALL / CREDITS, then the special line again every 1562 ticks (see special_phase). BALL / CREDITS: message 0x300 ("BALL %u", font 0, flag 1,
  x 0x2a, row 0x1e) and the credits text FUN_00004ff4 (font 0, flag 4, right edge 0x7f, row 0x1e). A special line is a text centred on 0x54 at row 0x1e (newlines to spaces).
"""
from . import dmd_engine as E

TABLE = ((100000000, 22, 18, 4, 20), (1000000, 17, 18, 4, 20), (100000, 24, 21, 2, 23), (0, 26, 21, 2, 23))   # ROM 0x40d3484


def record(score):
    for r in TABLE:
        if score >= r[0]:
            return r
    return TABLE[-1]


from .rom_deff57 import fmt   # message 0x4e4 "%,02lu"


def special_phase(t):
    """Is the special line's phase running at tick t of the effect (t = 0 the first loop)? The loop counters (0x9c, then 0x138 of special line, then 0x4e2,
    then 0x138 again ...) are decremented before the line is chosen: the first special tick is 0x9b, then every 0x138 + 0x4e2 = 1562 ticks."""
    return t >= 0x9b and (t - 0x9b) % 1562 < 0x138


def band(score, valid, counter):
    """The rows of the band blanked by the score's blink / wipe at that tick counter, or None."""
    _, _, _, top, bottom = record(score)
    if not valid:
        if counter < 0x3f or (counter - 0x3e) % 14 > 6:
            return None
        return top, bottom
    h = (bottom - top) * 2
    m = counter % (h * 2 + 0x3e)
    if m < 0x3f:
        return None
    u = (m - 0x3e) >> 1
    if h // 2 <= u:
        return top + (u - h // 2), bottom
    return top, top + u


def page(score, ball, credits, valid=False, counter=0, tick=0, special="", replay=""):
    """The page of one tick. special / replay: the lines FUN_01023670 / FUN_010237a0 give (the first non empty one is drawn instead of BALL / CREDITS)."""
    p = E.Page()
    _, font, row, _, _ = record(score)
    p.text(fmt(score), font, 0x54, row, 2)
    b = band(score, valid, counter)
    if b:
        p.fill(0x29, b[0], 0x7f, b[1], 0)
    line = ""
    if special_phase(tick):
        line = (special or replay).replace("\n", " ")
    if line:
        p.text(line, 0, 0x54, 0x1e, 2)
    else:
        p.text("BALL %u" % ball, 0, 0x2a, 0x1e, 1)
        if credits:
            p.text(credits, 0, 0x7f, 0x1e, 4)
    return p
