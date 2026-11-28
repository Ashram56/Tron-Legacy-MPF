"""Deff 108 [0x010209b0] says the player's Disc speech call at its tick 60 when 3 or more hits are left (FUN_0101c198, task 0x78
FUN_0101c0ec): snd_play2(call, counter) while the counter is under the call's sample count, then the counter goes up."""
from tests.tron_test import TronTestCase


class TestDiscSpeech(TronTestCase):

    def test_counter_walks_the_samples_and_stops(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        rec = self.tron.features_by_name["recognizer"]
        seen = []
        self.tron.sound2 = lambda call, arg, index=None, in_deff=0: seen.append((call, arg))
        rec.speech[0] = 0xbc                         # 6 samples
        rec.pd.speech_count = 0
        for _ in range(9):
            rec.disc_speech()
        self.assertEqual([(0xbc, n) for n in range(6)], seen)
        rec.speech[0] = 0xbd                         # a new call: the pick resets the counter
        rec.speech_pick()
        self.assertEqual(0, rec.pd.speech_count)
