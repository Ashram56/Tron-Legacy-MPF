"""The date and time line of SET DATE/TIME [FUN_0000d814, called by FUN_01045b44 at 0x01045b44].

The record (FUN_0000d244): year u16, weekday, month, day, hour, minute, second. The fields are edited in the order of
FUN_01045b44's switch: 1 month, 2 day, 3 year, 4 hour, 5 minute, 6 second; the one being edited is not drawn on the blink's off half.
Rules of the +/- buttons: FUN_0000d438 / d5f4 (month 1-12 wrap), d460 / d620 (day 1 to the month's length, wrap; the table 0x040d7cb8,
12 bytes per month, byte 8 = days, byte 9 = days in a leap year), d41c / d5d0 (year 2000-2099 wrap), d4f4 / d6a4 (hour 0-23 wrap),
d50c / d6c0 (minute 0-59 wrap), d524 / d6dc (second 0-59 wrap).
"""
from tron import rom_draw as rd

# month names: the message at the u16 of the month table's record (0x040d7cb8 + 12 * month): 504, 506 ... 526
MONTHS = ("JAN.", "FEB.", "MAR.", "APR.", "MAY", "JUN.", "JUL.", "AUG.", "SEP.", "OCT.", "NOV.", "DEC.")
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
AM, PM = "AM", "PM"                 # messages 0x210 and 0x211
FIELDS = ("month", "day", "year", "hour", "minute", "second")
FONT = 2


def width(font, text):
    """FUN_00028a74: the extent of the text from the origin (a glyph with a negative x offset, the comma, starts left of 0 and counts
    for that): max(0, right ends) - min(0, left starts), the font spacing between glyphs."""
    m = rd.fonts().get(font)
    lo = hi = cur = 0
    for c in text:
        g = m["glyphs"].get(c)
        if g is None:
            continue
        left = cur + g["xoff"]
        lo, hi = min(lo, left), max(hi, left + g["w"])
        cur = left + g["w"] + m["spacing"]
    return hi - lo


def leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def month_days(year, month):
    return 29 if month == 2 and leap(year) else MONTH_DAYS[month - 1]


def step(rec, field, delta):
    """FUN_0000d438 ... d6dc: the field `field` (1-6) of rec = [year, month, day, hour, minute, second] moved by +1 or -1."""
    year, month, day, hour, minute, sec = rec
    if field == 1:
        month = (month - 1 + delta) % 12 + 1
    elif field == 2:
        top = month_days(year, month)
        if delta > 0:
            day = 1 if day == 0 or top <= day else day + 1
        elif day == 0:
            day = 1
        elif day == 1:
            day = top
        else:
            day = min(day, top + 1) - 1
    elif field == 3:
        year = 2000 + (year - 2000 + delta) % 100
    elif field == 4:
        hour = (hour + delta) % 24
    elif field == 5:
        minute = (minute + delta) % 60
    else:
        sec = (sec + delta) % 60
    return [year, month, day, hour, minute, sec]


def draw(rec, twelve, y, hidden=None):
    """The items FUN_0000d814 draws (font 2, left aligned, the whole line centred): month, day, ",", year, hour:minute:second and AM / PM.
    `hidden` (1-6) is the field on the blink's off half."""
    year, month, day, hour, minute, sec = rec
    ampm = None
    if twelve:
        ampm = PM if hour > 11 else AM
        hour = hour - 12 if hour > 11 else hour
        hour = hour or 12
    items = [(1, MONTHS[month - 1 if 0 < month < 13 else 0]), (0, " "), (2, "%02d" % day), (0, ","), (0, " "),
             (3, "%04d" % year), (0, " "), (0, " "), (4, "%02d" % hour), (0, ":"), (5, "%02d" % minute), (0, ":"),
             (6, "%02d" % sec)]
    if ampm:
        items.append((0, ampm))
    widths = [width(FONT, t) + 1 for _, t in items]
    x = (128 - (sum(widths) - 1)) // 2        # 0xd814: the sum of the widths and the gaps is 13 over the items, not 14
    out = []
    for (field, t), w in zip(items, widths):
        if field == 0 or field != hidden:
            if t.strip():
                out.append(rd.text(t, FONT, x, y, 1))
        x += w
    return out
