"""Skill shots A (left ramp), B (right ramp), C (VUK) (assets/rules/modes/skill_shots.md)."""
from tron.features import Feature

GRACE_TICKS = 93
POLL_TICKS = 6
# key: (live task, grace task, arm flag, exclusions, base, step, cap, deff, sound, count attr)
SHOTS = {
    "A": (0x70, 0x71, 0x1e, {12, 14, 28, 35, 37}, 250000, 50000, 500000, 101, 0x046, "sk_a"),
    "B": (0x72, 0x73, 0x1f, {34, 38, 43, 46}, 300000, 50000, 500000, 102, 0x047, "sk_b"),
    "C": (0x74, 0x75, None, {11}, 500000, 50000, 750000, 103, 0x048, "sk_c"),
}


class SkillShots(Feature):
    name = "skill_shots"
    HOOKS = ("player_first_ball", "ball_served", "counting_switch", "instant_switch",
             "left_ramp_skill_shot_start", "right_ramp_skill_shot", "right_ramp_skill_shot_running",
             "left_ramp_skill_shot", "right_ramp_skill_shot_collect", "vuk_skill_shot", "tilt")

    def __init__(self, os_):
        super().__init__(os_)
        self.seen = {k: set() for k in SHOTS}     # timeout objects: distinct counting switches
        self.done = {k: False for k in SHOTS}
        os_.lamp_rule(lambda: os_.task_running(0x70), leff=109, tube=11, order=0x01028bac)
        os_.lamp_rule(lambda: os_.task_running(0x72), leff=111, tube=12, order=0x01028d98)
        os_.lamp_rule(lambda: os_.task_running(0x74), leff=113, order=0x01028f30)

    def player_first_ball(self):
        """0x010290ec: collect counts reset."""
        pd = self.pd
        pd.sk_a = pd.sk_b = pd.sk_c = 0

    # ------------------------------------------------------------------ start

    def ball_served(self, reason):
        """FUN_01029148 (serve event 0x0f)."""
        os_ = self.os
        if reason == 1:
            self.kill_all()
        elif reason in (3, 4, 5):
            os_.flag_set(0x1e)
            if os_.adj_value(79) == 1:
                self.start("B")
            else:
                os_.flag_set(0x1f)
            self.start("C")

    def start(self, key):
        live, grace = SHOTS[key][:2]
        os_ = self.os
        if os_.task_running(live) or os_.task_running(grace):
            return
        self.seen[key] = set()
        self.done[key] = False
        self._poll(key)
        os_.request_refresh()

    def _poll(self, key):
        """Task 0x70/0x72/0x74 polls its timeout object every 6 ticks; once done it becomes the grace task."""
        live, grace = SHOTS[key][:2]
        os_ = self.os
        if self.done[key]:
            os_.task_start(grace, GRACE_TICKS)
            os_.request_refresh()
            return
        os_.task_start(live, POLL_TICKS, lambda: self._poll(key))

    def left_ramp_skill_shot_start(self):
        """FUN_01028b74, first in the sw12 handler: ZEN starts A while flag 0x1e is set."""
        if self.os.flag(0x1e):
            self.os.flag_clear(0x1e)
            self.start("A")

    def right_ramp_skill_shot(self):
        """FUN_01028d60: shooter lane opens with the left flipper button held and flag 0x1f set."""
        if self.os.flag(0x1f):
            self.os.flag_clear(0x1f)
            self.start("B")

    def right_ramp_skill_shot_running(self):
        return self.os.task_running(0x72)

    # ------------------------------------------------------------------ timeout

    def running(self, key):
        live, grace = SHOTS[key][:2]
        return self.os.task_running(live) or self.os.task_running(grace)

    def counting_switch(self, sw):
        """FUN_01028a00 / FUN_01028a84: 3 distinct counting switches end a skill shot."""
        for key, spec in SHOTS.items():
            if sw in spec[3] or self.done[key]:
                continue
            if not self.os.task_running(spec[0]):
                continue
            self.seen[key].add(sw)
            if len(self.seen[key]) >= 3:
                self.done[key] = True
                if key == "A" and self.os.flag(0x1e):
                    self.os.flag_clear(0x1e)

    def instant_switch(self, sw):
        """FUN_01028b04: an instant switch ends every skill shot (and arm flag) that does not exclude it."""
        os_ = self.os
        for key, spec in SHOTS.items():
            if sw in spec[3]:
                continue
            if spec[2] is not None and os_.flag(spec[2]):
                os_.flag_clear(spec[2])
            os_.task_kill(spec[0])
            os_.task_kill(spec[1])

    def kill_all(self):
        """FUN_010291a4."""
        os_ = self.os
        for spec in SHOTS.values():
            os_.task_kill(spec[0])
            os_.task_kill(spec[1])
        os_.request_refresh()

    def tilt(self):
        self.kill_all()

    # ------------------------------------------------------------------ collect

    def _collect(self, key, show_task=None):
        if not self.running(key):
            return False
        os_ = self.os
        _, _, _, _, base, step, cap, deff, sound, attr = SHOTS[key]
        pd = self.pd
        value = min(base + step * pd[attr], cap)
        os_.score_add(value)
        pd[attr] = min(pd[attr] + 1, 0xff)
        if show_task:
            os_.show(show_task, deff, value=value)
        else:
            os_.deff_start(deff, value=value)
        os_.sound(sound)
        self.kill_all()
        return True

    def left_ramp_skill_shot(self):
        return self._collect("A")

    def right_ramp_skill_shot_collect(self):
        return self._collect("B")

    def vuk_skill_shot(self):
        return self._collect("C", show_task=0x86)


feature = SkillShots
