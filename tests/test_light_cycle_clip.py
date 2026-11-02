"""The Light Cycle Jackpot (deff 87) plays the first clip of the level every time (Serum knows no other: the ROM names the clip by the
level, it does not advance to the next clip of the level at each Jackpot)."""
from tests.tron_test import TronTestCase


class TestJackpotClip(TronTestCase):

    def test_same_clip_at_every_jackpot_of_a_level(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)
        self.hit_and_release_switch("s_zen_rollover")
        self.advance_time_and_run(1)
        os_ = self.tron
        lc = os_.features_by_name["light_cycle"]
        seen = []
        orig = os_.deff_start

        def spy(deff, **kw):
            if deff == 87:
                seen.append(kw.get("clip"))
            return orig(deff, **kw)
        os_.deff_start = spy
        os_.pd.lc_clip_level = 0
        lc.award(1)
        lc.award(1)
        self.assertEqual([0, 0], seen)
        os_.pd.lc_clip_level = 2
        lc.award(1)
        self.assertEqual(3, seen[-1])             # level 2's first clip: variants 0-1 are level 0, 2 is level 1
