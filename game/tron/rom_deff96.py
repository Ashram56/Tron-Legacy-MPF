"""deff_96 (0x01032bd0, Zuse fast scoring: a target hit): the background of deff 95 redrawn every tick, and over it the popups "%luK".

deff_096 (0x01032bd0) spawns child 0x01032a30 (the background) and, for each new value in the ring zfs_recent (RAM 0x3b8f4.., one taken per tick from the
parent loop of 0x3e ticks, at most 5 live), a popup child 0x01032900; then it holds 2 ticks on the page of RAM 0x3d528 (the status panel redrawn) and ends.

Background child (0x01032a30), one flip per tick: page 0x12 (the popup plane) copied (FUN_000272e4) and cleared to 0xff (FUN_0002738c), then the picture
0xaee + c at (0x29, 0), the band 0x29-0x7f rows 0x1a-0x1f filled with 0, the timer left and right and "ALL TARGETS=%,02lu" as deff 95 (0x010327d8); c
(RAM 0x3b92c) goes up after every 3rd flip (iVar3 > 2, FUN_010327c0) and wraps above 0x2d.

Popup child (0x01032900), 4 stages of 6 ticks: each tick "%luK" (0x605, value / 1000, font 0x27, centred) on page 0x12 at x = (0x21, 0x57, 0x3c)[random_below(3)]
+ random_below(0xf) + 0x10 and y = random_below(8) - 1 + 0xe, minus one after the 1st and 4th tick of each stage; palette identity with level 15 replaced by
the stage's byte of 0x040d6fd0 (15, 11, 4, 1).
Order inside a tick (the scheduler, read in the decompile): task_spawn_child (0x0000b840) -> task_create (0x0000b624) with flag 2 inserts the new task after
the list tail (FUN_0000b3b4(*0x372b4, task), 0x0000b3b4), and task_sleep (0x0000b91c) walks the list by the +0x1c links, a task whose count (+0x20) is 0 running in
that pass: the parent runs first, then the background child (spawned first), then the popups in spawn order, all in the tick of the spawn. So the background
child copies page 0x12 before the popups draw on it, and a popup shows one flip after it is drawn.
"""
from . import dmd_engine as E
from .rom_deff57 import fmt
from .rom_deff95 import PICTURES

TICKS = 1
HOLD = 0x3e                     # the parent's loop
LEVELS = (15, 11, 4, 1)         # 0x040d6fd0
XBASE = (0x21, 0x57, 0x3c)
FONT = 0x27


def popup_text(points):
    return "%dK" % (points // 1000)


def popup_draw(page, points, rnd, n):
    """The n-th tick (0-23) of a popup drawn on page 0x12; rnd = (random_below(3), random_below(0xf), random_below(8))."""
    stage, w = divmod(n, 6)
    pal = E.pal_new()
    pal[15] = LEVELS[stage]
    y = rnd[2] - 1 + 0xe - (2 * stage + (w > 0) + (w > 3))
    page.text(popup_text(points), FONT, XBASE[rnd[0]] + rnd[1] + 0x10, y, 2, pal)


def background(timer, value, counter):
    p = E.Page()
    p.blit(0xaee + counter, 0x29, 0)
    p.fill(0x29, 0x1a, 0x7f, 0x1f, 0)
    p.text("%u" % timer, 1, 0x2a, 6, 1)
    p.text("%u" % timer, 1, 0x7f, 6, 4)
    p.text("ALL TARGETS=%s" % fmt(value), 0, 0x55, 0x1f, 2)
    return p


def overlay(popups, t):
    """The plane the child copies at flip t: what the popups drew at tick t - 1. popups = [(points, (r3, r15, r8), first_tick)]."""
    p = E.Page(0xff)
    for points, rnd, t0 in popups:
        n = t - 1 - t0
        if 0 <= n < 24:
            popup_draw(p, points, rnd, n)
    return p


def pages(timer, value, popups, counter=0, flips=HOLD + 2):
    out = []
    c = counter
    for t in range(flips):
        k = min(t, HOLD - 1)                        # the last 2 ticks hold the last flip
        bg, ov = background(timer, value, c), overlay(popups, k)
        if t < HOLD:
            out.append((t, bg, ov))
            if (t + 1) % 3 == 0:
                c = c + 1 if c + 1 < PICTURES else 0
    return out


def frames(timer, value, popups, counter=0):
    return [(t, E.mix(ov.b, bg.b)) for t, bg, ov in pages(timer, value, popups, counter)]


def draws(timer, value, popups, counter=0):
    out = [(t, bg.items + [dict(i, o=1) for i in ov.items]) for t, bg, ov in pages(timer, value, popups, counter)]
    # 0x01032bd0: after the loop, 2 ticks on the page of RAM 0x3d528 (the body as last shown), then the effect ends
    return out + [(HOLD, out[-1][1]), (HOLD + 1, out[-1][1]), (HOLD + 2, [])]
