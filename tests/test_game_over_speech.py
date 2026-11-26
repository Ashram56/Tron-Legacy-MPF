"""Game-over task 0x45 [0x0100f29c]: speech 0x01e on every 4th-6th game over, or at once when no game can be
started on the credits left; then music 0x01d with leff 133 for 625 ticks (attract_and_service.md 4)."""
from tests.tron_test import TronTestCase


class TestGameOverSpeech(TronTestCase):

    def run_task(self, can_start, countdown=None):
        feat = self.tron.features_by_name["match"]
        feat.countdown = countdown
        self.tron.state |= 0x10
        self.tron.credit_model.can_start = lambda needed=1: can_start
        calls = []
        real = self.tron.sound
        self.tron.sound = lambda call, *a, **k: (calls.append(call), real(call, *a, **k))[1]
        feat._music_task()
        self.advance_time_and_run(12)
        return feat, [c for c in calls if c in (0x01d, 0x01e)]

    def test_no_credit_speech_first(self):
        feat, calls = self.run_task(False)
        self.assertEqual([0x01e, 0x01d], calls)

    def test_countdown_speech_on_the_nth_game_over(self):
        feat, calls = self.run_task(True, countdown=1)
        self.assertEqual([0x01e, 0x01d], calls)
        self.assertIn(feat.countdown, (4, 5, 6))

    def test_no_speech_while_countdown_runs(self):
        feat, calls = self.run_task(True, countdown=3)
        self.assertEqual([0x01d], calls)
        self.assertEqual(2, feat.countdown)
