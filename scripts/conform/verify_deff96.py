#!/usr/bin/env python3
"""Check the game's Zuse popup frames (deff 96 over deff 95, light cycle) against the ported ROM routines: for each missed frame saved by dump_misses.py
(MISSDIR/*_e55_*, *_e19_*, *_e95_*), search the background counter (0x3b92c), the popup draws (random_below(3), (15), (8)) and the popup tick that draw it.

    python3 scripts/conform/verify_deff96.py MISSDIR TIMER[,TIMER...]       (the timer is the 95/96 timer shown in the corners)

2026-11-28, light cycle: 22 of the 36 missed frames are reproduced exactly with the draws (0, 12, 0..2) and (0, 7, 4..6): the game draws what the code draws; the
frames are missing from the sweeps only (the random draws and the counter are not enumerated by sweep_engine.py).
"""
import os
import sys,glob
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','game'))
from PIL import Image
from tron import dmd_engine as E, rom_deff96 as R
miss=[]
for name in sorted(glob.glob(sys.argv[1]+'/*_e55_*.png'))+sorted(glob.glob(sys.argv[1]+'/*_e19_*.png'))+sorted(glob.glob(sys.argv[1]+'/*_e95_*.png')):
    im=Image.open(name).resize((128,32),Image.NEAREST)
    g=bytes(v//17 for v in im.tobytes())
    miss.append((name[-18:], bytes(g[y*128+x] for y in range(32) for x in range(41,128))))
timers=[int(t) for t in sys.argv[2].split(',')]
found={}
for timer in timers:
  for c in range(R.PICTURES):
    bg=R.background(timer,10000,c)
    for r3 in range(3):
      for r15 in range(15):
        for r8 in range(8):
          for n in range(24):
            ov=E.Page(0xff); R.popup_draw(ov,10000,(r3,r15,r8),n)
            f=E.mix(ov.b,bg.b)
            cl=bytes(f[y*128+x] for y in range(32) for x in range(41,128))
            for nm,m in miss:
                if m==cl: found.setdefault(nm,(timer,c,(r3,r15,r8),n))
print(len(found),len(miss)); print(found)
