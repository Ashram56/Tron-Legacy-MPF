#!/usr/bin/env python3
"""Start the game on Windows, macOS or Linux: Godot (GMC, the BCP server) first, then MPF, optionally MPF Monitor.

    python scripts/run.py                          # virtual hardware (hw_virtual: smart_virtual, trough full)
    python scripts/run.py --monitor                # ... plus MPF Monitor (setup.py --monitor installs it)
    python scripts/run.py --hw proc                # the real machine on the P-ROC (Godot feeds the DMD)
    python scripts/run.py --scenario NAME          # play assets/rules/traces/NAME.txt in real time
    python scripts/run.py --seconds 20             # stop everything after 20 s

Godot's log goes to game/logs/godot.log. MPF runs in this terminal; quitting it (Ctrl+C or Esc in its text UI)
stops Godot and MPF Monitor too. On Linux without a display, Godot runs under Xvfb (xvfb-run).
"""
import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolchain as tc  # noqa: E402

IS_WINDOWS = os.name == "nt"


def port_in_use(port):
    """True when something listens on port. Binds instead of connecting: GMC quits when its client hangs up."""
    for host in ("", "127.0.0.1"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if IS_WINDOWS:      # without it a Windows bind can share a port that is taken
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:               # ignore TIME_WAIT leftovers of the last run; a listener still blocks the bind
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
            except OSError:
                return True
    return False


def wait_for_port(port, procs, timeout):
    """Wait until port is taken; fail early when one of procs exits."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if port_in_use(port):
            return True
        for p in procs:
            if p.poll() is not None:
                return False
        time.sleep(0.2)
    return False


def spawn(cmd, *, log=None, cwd=None, env=None, group=False):
    """Start cmd; log is a path (stdout + stderr) or None to inherit the terminal."""
    out = open(log, "w", encoding="utf-8") if log else None
    kw = {}
    if group:       # its own process group, so stop() also ends its children (xvfb-run -> Godot)
        if IS_WINDOWS:
            kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kw["start_new_session"] = True
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT if out else None,
                            stdin=subprocess.DEVNULL if group else None, **kw)
    proc.log_file = out
    proc.group = group
    return proc


def stop(proc, grace=10):
    """Ask proc to end, then kill it after grace seconds."""
    if proc is None:
        return None
    if proc.poll() is None:
        try:
            if proc.group and not IS_WINDOWS:
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
            proc.wait(grace)
        except subprocess.TimeoutExpired:
            if proc.group and not IS_WINDOWS:
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            proc.wait()
        except (ProcessLookupError, PermissionError):
            pass
    if proc.log_file:
        proc.log_file.close()
    return proc.returncode


def godot_command(godot_args, virtual_display=None):
    exe = tc.godot_path()
    if not os.path.exists(exe) and not shutil.which(exe):
        raise SystemExit("Godot not found at {} (run `python scripts/setup.py`, or set GODOT)".format(exe))
    cmd = [exe, "--path", tc.GAME] + list(godot_args)
    if virtual_display is None:
        virtual_display = tc.needs_virtual_display()
    if virtual_display:
        if not shutil.which("xvfb-run"):
            raise SystemExit("no display and no xvfb-run: install xvfb (apt install xvfb) or set DISPLAY")
        cmd = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24"] + cmd
    return cmd


def mpf_args(hw, scenario=None, text_ui=False):
    args = ["game", ".", "-c", "config,hw_" + hw]
    if not text_ui:
        args.append("-t")
    if scenario:
        args.append("-X")       # smart_virtual: the scenario's coil pulses move balls (hw_virtual uses it too)
    return args


def run(hw="virtual", *, monitor=False, scenario=None, seconds=None, text_ui=False, godot_args=(),
        godot_log=None, mpf_log=None, trace=None, virtual_display=None, wait_godot_exit=False):
    """Godot, then MPF (and MPF Monitor); returns MPF's exit code. Everything is stopped on the way out."""
    logs = os.path.join(tc.GAME, "logs")
    os.makedirs(logs, exist_ok=True)
    godot_log = godot_log or os.path.join(logs, "godot.log")
    gargs = list(godot_args)
    if hw == "proc" and "--proc-dmd" not in gargs:
        gargs = (gargs + ["--proc-dmd"]) if "--" in gargs else (gargs + ["--", "--proc-dmd"])
    if port_in_use(tc.BCP_PORT):
        raise SystemExit("port {} is already taken: is another Godot/GMC running?".format(tc.BCP_PORT))
    env = dict(os.environ)
    if scenario:
        env["TRON_LIVE_SCENARIO"] = scenario
    if trace:
        env["TRON_TRACE"] = trace
    godot = mpf = mon = None
    try:
        godot = spawn(godot_command(gargs, virtual_display), log=godot_log, group=True)
        print("Godot started (log: {}), waiting for GMC on port {}".format(godot_log, tc.BCP_PORT), flush=True)
        if not wait_for_port(tc.BCP_PORT, [godot], 120):
            raise SystemExit("GMC did not open port {} (see {})".format(tc.BCP_PORT, godot_log))
        print("Starting MPF: mpf " + " ".join(mpf_args(hw, scenario, text_ui)), flush=True)
        mpf = spawn(tc.mpf_command() + mpf_args(hw, scenario, text_ui), log=mpf_log, cwd=tc.GAME, env=env)
        if monitor:
            if wait_for_port(tc.MONITOR_PORT, [mpf], 120):
                mon = spawn(tc.mpf_command() + ["monitor"], cwd=tc.GAME, group=True,
                            log=os.path.join(logs, "monitor.log"))
                print("MPF Monitor started (log: game/logs/monitor.log)", flush=True)
            else:
                print("MPF did not open port {}: no MPF Monitor".format(tc.MONITOR_PORT), flush=True)
        try:
            mpf.wait(seconds)
        except subprocess.TimeoutExpired:
            print("{} s elapsed, stopping MPF".format(seconds), flush=True)
            stop(mpf)
            mpf.returncode = 0          # a planned stop, not a failure
        if wait_godot_exit:         # a Godot capture run quits on its own when its time is up
            try:
                godot.wait(30)
            except subprocess.TimeoutExpired:
                pass
        return mpf.returncode
    except KeyboardInterrupt:
        print("interrupted, stopping", flush=True)
        return 130
    finally:
        for p in (mon, mpf, godot):
            stop(p)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--hw", choices=["virtual", "proc"], default="virtual",
                   help="hardware overlay: game/config/hw_<hw>.yaml (default virtual)")
    p.add_argument("--monitor", action="store_true", help="also start MPF Monitor (layout in game/monitor/)")
    p.add_argument("--scenario", help="play assets/rules/traces/NAME.txt in real time (smart_virtual)")
    p.add_argument("--seconds", type=float, help="stop after this many seconds")
    p.add_argument("--trace", help="write MPF's trace (jsonl) to this file")
    p.add_argument("--text-ui", dest="text_ui", action="store_true", default=None,
                   help="MPF's text UI (default: on in a terminal without --seconds)")
    p.add_argument("--no-text-ui", dest="text_ui", action="store_false")
    p.add_argument("godot_args", nargs="*", help="extra Godot arguments, after --")
    args = p.parse_args(argv)
    text_ui = args.text_ui
    if text_ui is None:
        text_ui = sys.stdin.isatty() and sys.stdout.isatty() and args.seconds is None
    return run(args.hw, monitor=args.monitor, scenario=args.scenario, seconds=args.seconds, text_ui=text_ui,
               godot_args=args.godot_args, trace=args.trace and os.path.abspath(args.trace))


if __name__ == "__main__":
    sys.exit(main() or 0)
