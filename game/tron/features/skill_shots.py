"""Skill shots A (left ramp), B (right ramp), C (VUK) (assets/rules/modes/skill_shots.md).

Each skill shot owns a switch timeout object (switch_timeout_obj_* [0x00010c08..0x00010c70]): 3 slots that
fill with distinct counting switches (event 0x6b), cleared only when that skill shot starts. The objects
count all the time, armed or not; when the 3rd slot fills the object is done and posts event 0x6a, whose
hook [skill_timeout_expired 0x01028b04] kills that skill shot (skillX_kill: tasks and A/B arm flag).
An instant switch (event 0x6c) expires and kills every skill shot that does not exclude it
[skill_instant_switch 0x01028a84]. The task's own 93-tick grace (id 0x71/0x73/0x75 once it sees its object
done) is not modelled: event 0x6a is synchronous, so the kill always comes first and the grace never runs.
"""
from tron.features import Feature

POLL_TICKS = 6
# key: (live task, grace task, arm flag, exclusions, base, step, cap, deff, count attr)
SHOTS = {
    "A": (0x70, 0x71, 0x1e, {12, 14, 28, 35, 37}, 250000, 50000, 500000, 101, "sk_a"),
    "B": (0x72, 0x73, 0x1f, {34, 38, 43, 46}, 300000, 50000, 500000, 102, "sk_b"),
    "C": (0x74, 0x75, None, {11}, 500000, 50000, 750000, 103, "sk_c"),
}
SLOTS = 3


class SkillShots(Feature):
    name = "skill_shots"
    HOOKS = ("player_first_ball", "ball_served", "counting_switch", "instant_switch",
             "left_ramp_skill_shot_start", "right_ramp_skill_shot", "right_ramp_skill_shot_running",
             "left_ramp_skill_shot", "right_ramp_skill_shot_collect", "vuk_skill_shot", "tilt", "ball_end")

    def __init__(self, os_):
        super().__init__(os_)
        self.slots = {k: set() for k in SHOTS}     # timeout objects: distinct counting switches
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
        """skill_on_serve [0x01029148] (serve event 0x0f)."""
        os_ = self.os
        if reason == 1:
            self.kill_all()
            os_.request_refresh()
        elif reason in (3, 4, 5):
            os_.flag_set(0x1e)
            if os_.adj_value(79) == 1:
                self.start("B")
            else:
                os_.flag_set(0x1f)
            self.start("C")

    def running(self, key):
        """task_running_range(live, grace)."""
        return self.os.task_running(SHOTS[key][0])

    def start(self, key):
        """skillX_start: only when its task pair is not running; clears its timeout object."""
        if self.running(key):
            return False
        self.slots[key] = set()
        self.done[key] = False
        self._poll(key)
        self.os.request_refresh()
        return True

    def _poll(self, key):
        """Task 0x70/0x72/0x74: polls its object every 6 ticks until a kill ends it."""
        self.os.task_start(SHOTS[key][0], POLL_TICKS, lambda: self._poll(key))

    def left_ramp_skill_shot_start(self):
        """skillA_start_from_zen [0x01028b74], first in the sw12 handler."""
        if self.os.flag(0x1e) and self.start("A"):
            self.os.flag_clear(0x1e)

    def right_ramp_skill_shot(self):
        """skillB_start_from_plunge [0x01028d60]: shooter lane opens with the left flipper button held."""
        if self.os.flag(0x1f) and self.start("B"):
            self.os.flag_clear(0x1f)

    def right_ramp_skill_shot_running(self):
        return self.os.task_running(0x72)

    # ------------------------------------------------------------------ timeout

    def counting_switch(self, sw):
        """skill_count_switch [0x01028a00]: switch_timeout_obj_add on each object not excluding sw."""
        for key, spec in SHOTS.items():
            if sw in spec[3] or self.done[key]:
                continue
            self.slots[key].add(sw)
            if len(self.slots[key]) >= SLOTS:
                self.expire(key)

    def expire(self, key):
        """switch_timeout_obj_expire: done, event 0x6a -> skill_timeout_expired [0x01028b04]."""
        if not self.done[key]:
            self.done[key] = True
            self.kill(key)

    def instant_switch(self, sw):
        """skill_instant_switch [0x01028a84]: expire and kill every skill shot that does not exclude sw."""
        for key, spec in SHOTS.items():
            if sw not in spec[3]:
                self.expire(key)
                self.kill(key)

    def kill(self, key):
        """skillA_kill / skillB_kill / skillC_kill: arm flag (A, B) and the task pair."""
        live, _, flag = SHOTS[key][:3]
        if flag is not None:
            self.os.flag_clear(flag)
        self.os.task_kill(live)

    def kill_all(self):
        """skill_kill_all [0x010291a4]."""
        for key in SHOTS:
            self.kill(key)

    def tilt(self):
        self.kill_all()

    def ball_end(self):
        """The skill shot tasks die with the ball (end of ball kills the ball's tasks)."""
        self.kill_all()

    # ------------------------------------------------------------------ collect

    def _collect(self, key, show_task=None):
        if not self.running(key):
            return False
        os_ = self.os
        base, step, cap, deff, attr = SHOTS[key][4:]
        pd = self.pd
        value = os_.score_add(min(base + step * pd[attr], cap))
        if show_task:
            os_.show(show_task, deff, value=value)       # task 0x86: queue_fullscreen_deff(103)
        else:
            os_.deff_start(deff, value=value)            # its sound 0x46/0x47/0x48 plays from the deff
        pd[attr] = min(pd[attr] + 1, 0xff)
        self.kill_all()
        os_.request_refresh()
        return True

    def left_ramp_skill_shot(self):
        return self._collect("A")

    def right_ramp_skill_shot_collect(self):
        return self._collect("B")

    def vuk_skill_shot(self):
        return self._collect("C", show_task=0x86)


feature = SkillShots
