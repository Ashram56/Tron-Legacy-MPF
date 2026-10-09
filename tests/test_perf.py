"""scripts/perf/summary.py on a synthetic run (docs/performance.md)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "perf"))
import summary  # noqa: E402


class TestPerfSummary(unittest.TestCase):

    def run_dir(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        t, lines = 0.0, ["t_ms,delta_ms,draw_ms"]
        for i in range(30 * 60):                    # 30 s at 60 FPS, with one 500 ms stall at 20 s
            dt = 500.0 if i == 20 * 60 else 1000.0 / 60
            t += dt
            lines.append("%.1f,%.3f,%.3f" % (t, dt, 5.0))
        open(os.path.join(d, "frames.csv"), "w").write("\n".join(lines) + "\n")
        open(os.path.join(d, "video.csv"), "w").write(
            "t_ms,screen,file,frame,step,late_ms\n10000,2,a.mp4,1,1,0\n10033,2,a.mp4,2,1,1\n10133,2,a.mp4,5,3,2\n")
        open(os.path.join(d, "av.csv"), "w").write("t_ms,screen,file,av_ms\n11000,2,a.mp4,30\n12000,2,a.mp4,-50\n")
        open(os.path.join(d, "events.csv"), "w").write(
            "t_ms,kind,screen,detail\n100,open,2,a.mp4\n120,open,12,b.mp4\n300,open,13,c.mp4\n5000,black,2,250 ms\n")
        open(os.path.join(d, "mpf.log"), "w").write(
            "2026-10-09 13:01:16,341 : INFO : EventManager : Event: ======'tron_deff_85'====== Args={}\n"
            "2026-10-09 13:01:17,319 : INFO : EventManager : Event: ======'slide_deff_085_created'====== Args={}\n")
        open(os.path.join(d, "godot.log"), "w").write("ERROR: something\nfine\n")
        return d

    def test_summary(self):
        d = self.run_dir()
        text, f, v, vals = summary.summarize(d)
        self.assertAlmostEqual(60.0, f["fps_avg"], delta=2.0)
        self.assertEqual([(20.0, 0.5)], [(round(s, 0), round(n, 2)) for s, n in f["stalls"]])
        self.assertEqual(1, f["long_frames"])
        self.assertEqual(2, v["video_skipped"])
        self.assertEqual(40.0, v["av_avg_ms"])
        self.assertEqual(["0.0 s: screens 12+13+2"], v["bursts"])
        self.assertEqual(1, v["black"])
        self.assertEqual(1, vals["errors"])
        self.assertIn("deff 85 0.98 s", text)
        self.assertIn("FAIL video frames skipped", text)
        self.assertTrue(os.path.exists(os.path.join(d, "summary.md")))


if __name__ == "__main__":
    unittest.main()
