"""Sea of Simulation and Portal Multiball paths that the reference scenarios do not reach
(assets/rules/modes/sea_of_simulation.md, portal_multiball.md)."""
from tests.tron_test import TronTestCase


class WizardTestCase(TronTestCase):

    def start_play(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)      # plunge
        self.hit_and_release_switch("s_zen_rollover")         # playfield valid
        self.advance_time_and_run(1)

    def items(self, lit=(), collected=()):
        for i, item in enumerate(self.tron.pd.items):
            item[0] = 1 if i in lit else 0
            item[1] = 1 if i in collected else 0

    def h(self, name, *args):
        return self.tron.hook(name, *args)

    def score(self):
        return self.machine.game.player.score


class TestSeaOfSimulation(WizardTestCase):

    def setUp(self):
        super().setUp()
        self.started = []
        self.machine.events.add_handler("tron_deff_125", lambda **kwargs: self.started.append(125))
        self.machine.events.add_handler("tron_deff_115", lambda **kwargs: self.started.append(115))
        self.machine.events.add_handler("tron_sound_112", lambda **kwargs: self.started.append(0x112))

    def test_all_stages_skips_spots_and_completion(self):
        self.start_play()
        sos = self.tron.features_by_name["sea_of_simulation"]
        self.items(lit=range(9), collected=(2, 3))
        self.assertEqual(0, self.h("arcade_sos_weight", 101))
        self.assertTrue(self.h("sos_vuk", True))
        self.assertTrue(self.tron.flag(0x34))
        self.assertEqual(1101, self.h("arcade_sos_weight", 101))
        self.assertFalse(self.h("simulation_shot", 17))          # not needed in stage 0
        score = self.score()
        self.assertTrue(self.h("arcade_sos"))                     # ADV. SOS: stage 0 spotted quietly
        self.assertEqual(score + 10000, self.score())
        self.assertEqual(1, sos.stage)
        self.h("simulation_shot", 17)                             # GEM; CLU and ZUSE are collected
        self.assertEqual(4, sos.stage)
        self.assertTrue(sos.skip_showing)                         # CLU's bonus shows, ZUSE's waits
        self.assertEqual([3], sos.skip_queue)
        self.advance_time_and_run(30)                             # both skip bonuses play in turn
        self.assertEqual([1, 1], sos.skip_paid[2:4])
        self.assertEqual(2, self.started.count(115))
        self.h("simulation_shot", 16)                             # QUORRA
        for _ in range(6):                                        # DISC: the disc opto spots each shot
            self.h("simulation_shot", 1)
        self.assertEqual(6, sos.stage)
        self.h("simulation_shot", 19)                             # LIGHT CYCLE
        self.assertFalse(self.h("simulation_shot", 19))
        self.h("simulation_shot", 18)
        self.h("simulation_shot", 15)
        self.assertEqual(7, sos.stage)
        for _ in range(5):
            self.h("simulation_shot", 13)
        self.assertEqual(7, sos.stage)
        self.h("simulation_shot", 13)                             # 6th recognizer hit
        self.assertEqual(8, sos.stage)
        self.assertTrue(self.tron.flag(0x35))                     # final stage
        self.advance_time_and_run(5)
        self.assertIn(0x112, self.started)
        for shot in (2, 3, 4, 5):
            self.h("simulation_shot", shot)
        self.advance_time_and_run(0.1)
        self.assertTrue(self.tron.flag(0x36))
        self.assertFalse(self.tron.flag(0x34))
        self.assertIn(125, self.started)
        self.assertTrue(self.h("items_all_collected"))

    def test_clu_helmets_spot_and_last_stage_skipped(self):
        self.start_play()
        sos = self.tron.features_by_name["sea_of_simulation"]
        self.items(lit=range(9), collected=(0, 1, 8))
        self.h("sos_vuk", True)
        self.assertEqual(2, sos.stage)
        self.h("simulation_shot", 6)                              # C lit
        self.h("simulation_shot", 6)                              # C again
        self.h("simulation_shot", 7)
        self.assertEqual(0x94001, sos.needed)
        self.h("simulation_shot", 8)                              # C-L-U: spots the left orbit
        self.assertEqual(0x94001 & ~(1 << 14), sos.needed)
        for shot in (16, 19, 0):
            self.h("simulation_shot", shot)
        self.assertEqual(3, sos.stage)
        sos.stage = 7
        sos.needed = 1 << 13
        sos.rec_hits = 5
        self.h("simulation_shot", 13)                             # stage 8 (TRON) collected: complete
        self.assertTrue(self.tron.flag(0x36))

    def test_tilt_pays_queued_skip_bonus(self):
        self.start_play()
        sos = self.tron.features_by_name["sea_of_simulation"]
        self.items(lit=range(9), collected=(1,))
        self.h("sos_vuk", True)
        for _ in range(2):                                        # two tilt warnings
            self.hit_and_release_switch("s_plumb_bob_tilt")
            self.advance_time_and_run(1.1)
        self.h("simulation_shot", 0)                              # stage 1 skipped: 2,000,000 queued
        self.assertEqual(0, sos.skip_paid[1])
        score = self.score()
        self.hit_and_release_switch("s_plumb_bob_tilt")           # tilt before deff 115 gets the display
        self.assertTrue(self.tron.tilted)
        self.assertEqual(score + 2000000, self.score())
        self.assertEqual(1, sos.skip_paid[1])


class TestPortal(WizardTestCase):

    def test_grace_restart_ball_end_total(self):
        self.start_play()
        portal = self.tron.features_by_name["portal"]
        self.items(collected=range(9))
        self.assertTrue(self.h("portal_vuk", True))
        self.assertTrue(self.h("portal_running"))
        self.assertEqual(1, self.tron.pd.portal_count)
        self.advance_time_and_run(10)
        self.h("multiball_end")                                   # down to one ball: grace
        self.assertFalse(self.tron.flag(0x37))
        self.assertTrue(self.tron.task_running(0xd2))
        portal.counts[0] = 3
        self.assertTrue(self.h("portal_mb_shot", 0))              # completes a shot: add-a-ball restarts
        self.assertTrue(self.tron.flag(0x37))
        self.assertFalse(self.tron.task_running(0xd2))
        self.assertFalse(self.h("portal_mb_shot", 0))             # at max
        self.h("ball_end")
        self.assertFalse(self.tron.flag(0x37))
        self.assertGreater(self.h("ball_end_wait"), 0)            # deff 145 total before the bonus
        self.tron.state |= 0x200
        self.assertEqual(0, portal.show_total())                  # no total when tilted
        self.assertEqual(0, self.tron.features_by_name["sea_of_simulation"].show_total())
        self.assertFalse(self.h("portal_vuk", True))              # no multiball while tilted
        self.assertFalse(portal.add_a_ball())
        self.assertFalse(self.h("arcade_sos"))                    # SOS not running
        self.h("tilt_start")


class TestMultiballTask(WizardTestCase):
    """OS multiball_start [0x0001ed7c]: one multiball task; later requests while it runs keep the larger save."""

    def test_requests_while_running(self):
        self.start_play()
        os_ = self.tron
        self.assertTrue(os_.multiball_start(2, 0, 30))           # no save: grace only
        self.assertTrue(os_.task_running(0x35))
        self.assertTrue(os_.multiball_start(3, 1000, 0))         # while launching: save restarts
        self.assertGreater(os_.task_ticks_left(0x34), 900)
        self.advance_time_and_run(6)
        self.assertEqual(3, os_.balls_in_play())
        self.assertFalse(os_.task_running("multiball"))
        self.assertTrue(os_.multiball_start(4, 10, 0))           # save still running: a shorter one loses
        self.assertGreater(os_.task_ticks_left(0x34), 10)
        self.assertTrue(os_.task_running("multiball"))           # the added ball is launched
        self.advance_time_and_run(3)
        self.assertEqual(4, os_.balls_in_play())
        os_.ball_held = True                                     # a request while the VUK keeps a ball
        os_.kill_mb_save()
        self.assertTrue(os_.multiball_start(4, 100, 50))
        self.assertTrue(os_.multiball_start(4, 300, 60))         # still waiting: the larger values
        self.assertEqual((300, 60), os_._mb_save)
        os_.ball_held = False
        self.advance_time_and_run(1)
        self.assertGreater(os_.task_ticks_left(0x34), 200)
