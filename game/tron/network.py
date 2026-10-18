"""Wi-Fi for the service menu (UTILITIES > GO TO NETWORK MENU, added by this game): the connection's status,
a scan of the networks in range and joining one with its password, through Linux NetworkManager's command
line (nmcli) or, where wpa_supplicant runs on its own (the Jetson image: systemd-networkd and
wpa_supplicant@wlan0), wpa_cli. Elsewhere (Windows, macOS, the tests) the backend says it is not available
and the menu shows that; the operator then sets up the network with the system's own tools.

nmcli runs in a worker thread so the game loop never waits on it: start() a Job, poll job.done from the
MPF clock, read job.result. Nothing here touches MPF from the worker.

The password goes to nmcli on its command line (`nmcli device wifi connect SSID password ...`), so it shows
in the process list while nmcli runs; NetworkManager then keeps it in its own connection profile (root
only), not in the game's files. wpa_cli gets the PSK hashed from it instead. Joining needs the right to
change the system's network: polkit for NetworkManager, the control socket's group (sudo on the Jetson
image) for wpa_supplicant (docs/network.md).
"""
import hashlib
import os
import platform
import re
import shutil
import subprocess
import threading
import time

TIMEOUT = 45            # seconds: a connect waits for DHCP


def split_terse(line):
    """One line of `nmcli -t` output: fields split on ':' with '\\:' and '\\\\' unescaped."""
    out, cur, i = [], [], 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            cur.append(line[i + 1])
            i += 2
            continue
        if ch == ":":
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return out


class Job:
    """A function run once in a daemon thread: done, result (the function's return value, or the error)."""

    def __init__(self, func, *args):
        self.done = False
        self.result = None
        self._thread = threading.Thread(target=self._run, args=(func,) + args, daemon=True)
        self._thread.start()

    def _run(self, func, *args):
        try:
            self.result = func(*args)
        except Exception as e:      # noqa: BLE001: reported on the display, never raised into the game
            self.result = {"ok": False, "message": str(e) or e.__class__.__name__}
        self.done = True


class NoWifi:
    """No NetworkManager here: every call says so."""

    available = False
    reason = "NOT AVAILABLE"

    def status(self):
        return {"state": self.reason, "ssid": "", "ip": "", "signal": None, "device": ""}

    def scan(self):
        return []

    def connect(self, ssid, password=None, hidden=False):
        return {"ok": False, "message": self.reason}

    def forget(self, ssid):
        return {"ok": False, "message": self.reason}


class NmcliWifi:
    """NetworkManager through nmcli: the first Wi-Fi device it lists."""

    available = True

    def __init__(self, nmcli="nmcli", run=None):
        self.nmcli = nmcli
        self._run = run or self._subprocess

    def _subprocess(self, args):
        p = subprocess.run([self.nmcli] + args, capture_output=True, text=True, timeout=TIMEOUT,
                           env=dict(os.environ, LC_ALL="C"))
        return p.returncode, p.stdout, p.stderr

    def device(self):
        """(device, state, connection) of the first Wi-Fi device, None when there is none."""
        code, out, _ = self._run(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"])
        for line in out.splitlines() if code == 0 else []:
            f = split_terse(line)
            if len(f) >= 4 and f[1] == "wifi":
                return f[0], f[2], f[3]
        return None

    def status(self):
        dev = self.device()
        if not dev:
            return {"state": "NO WI-FI DEVICE", "ssid": "", "ip": "", "signal": None, "device": ""}
        name, state, connection = dev
        info = {"state": state.upper(), "ssid": "", "ip": "", "signal": None, "device": name}
        if state == "connected":
            code, out, _ = self._run(["-t", "-f", "IN-USE,SSID,SIGNAL", "device", "wifi", "list", "--rescan", "no"])
            for line in out.splitlines() if code == 0 else []:
                f = split_terse(line)
                if len(f) >= 3 and f[0] == "*":
                    info["ssid"], info["signal"] = f[1], int(f[2]) if f[2].isdigit() else None
            if not info["ssid"]:
                info["ssid"] = connection
            code, out, _ = self._run(["-g", "IP4.ADDRESS", "device", "show", name])
            if code == 0 and out.strip():
                info["ip"] = out.strip().split("|")[0].split("/")[0].strip()
        return info

    def scan(self):
        """The networks in range, strongest first, one entry per name: {ssid, signal, secure, in_use}."""
        code, out, err = self._run(["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                                    "--rescan", "yes"])
        if code != 0:
            raise RuntimeError(error_text(err))
        best = {}
        for line in out.splitlines():
            f = split_terse(line)
            if len(f) < 4 or not f[1]:
                continue                       # hidden networks have no name
            entry = {"ssid": f[1], "signal": int(f[2]) if f[2].isdigit() else 0,
                     "secure": f[3] not in ("", "--"), "in_use": f[0] == "*"}
            old = best.get(entry["ssid"])
            if old is None or entry["signal"] > old["signal"]:
                entry["in_use"] = entry["in_use"] or bool(old and old["in_use"])
                best[entry["ssid"]] = entry
        return sorted(best.values(), key=lambda e: (not e["in_use"], -e["signal"], e["ssid"].lower()))

    def connect(self, ssid, password=None, hidden=False):
        args = ["device", "wifi", "connect", ssid]
        if password:
            args += ["password", password]
        if hidden:
            args += ["hidden", "yes"]
        code, out, err = self._run(args)
        if code == 0:
            return {"ok": True, "message": "CONNECTED"}
        return {"ok": False, "message": error_text(err or out)}

    def forget(self, ssid):
        """Disconnect and delete the saved profile(s) named after the network."""
        code, out, err = self._run(["connection", "delete", "id", ssid])
        if code == 0:
            return {"ok": True, "message": "FORGOTTEN"}
        return {"ok": False, "message": error_text(err or out)}


def psk_hex(ssid, password):
    """WPA-PSK from the passphrase, as wpa_passphrase makes it: the password itself is never passed on."""
    return hashlib.pbkdf2_hmac("sha1", password.encode("utf-8"), ssid.encode("utf-8"), 4096, 32).hex()


def wpa_text(value):
    """wpa_cli's quoted string for a set_network value."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def wpa_unescape(text):
    """An SSID as wpa_cli prints it (printf_encode: \\xNN, \\\\, \\")."""
    out, i, raw = bytearray(), 0, text.encode("utf-8", "surrogateescape")
    while i < len(raw):
        if raw[i:i + 2] == b"\\x" and i + 4 <= len(raw):
            try:
                out.append(int(raw[i + 2:i + 4], 16))
                i += 4
                continue
            except ValueError:
                pass
        if raw[i:i + 1] == b"\\" and i + 1 < len(raw):
            out.append(raw[i + 1])
            i += 2
            continue
        out.append(raw[i])
        i += 1
    return out.decode("utf-8", "replace")


def signal_percent(dbm):
    """dBm to the 0-100 % nmcli shows (-100 dBm = 0, -50 dBm = 100)."""
    return max(0, min(100, 2 * (dbm + 100)))


class WpaCliWifi:
    """wpa_supplicant through wpa_cli, as on the Jetson image (wpa_supplicant@wlan0 with update_config=1 and
    its control socket open to the sudo group, systemd-networkd for DHCP). A network is added with its PSK
    (hashed here, like wpa_passphrase), selected, and saved to the config once it has connected; a network of
    the same name is replaced. Waiting for the connection polls `status`."""

    available = True
    CONNECT_SECONDS = 20

    def __init__(self, iface, wpa_cli="wpa_cli", run=None, sleep=None):
        self.iface = iface
        self.wpa_cli = wpa_cli
        self._run = run or self._subprocess
        self._sleep = sleep or time.sleep

    def _subprocess(self, args):
        p = subprocess.run([self.wpa_cli, "-i", self.iface] + args, capture_output=True, text=True,
                           timeout=TIMEOUT, env=dict(os.environ, LC_ALL="C"))
        return p.returncode, p.stdout, p.stderr

    def cmd(self, *args):
        code, out, err = self._run(list(args))
        if code != 0 or out.strip().startswith("FAIL"):
            raise RuntimeError(error_text(err or out or "FAILED"))
        return out

    def _status(self):
        return dict(line.split("=", 1) for line in self.cmd("status").splitlines() if "=" in line)

    def status(self):
        st = self._status()
        info = {"state": "DISCONNECTED", "ssid": "", "ip": "", "signal": None, "device": self.iface}
        if st.get("wpa_state") != "COMPLETED":
            info["state"] = {"SCANNING": "SCANNING", "INACTIVE": "DISCONNECTED", "INTERFACE_DISABLED": "OFF"}.get(
                st.get("wpa_state", ""), "CONNECTING" if st.get("wpa_state") else "DISCONNECTED")
            return info
        info.update(state="CONNECTED", ssid=wpa_unescape(st.get("ssid", "")), ip=st.get("ip_address", ""))
        try:
            poll = dict(line.split("=", 1) for line in self.cmd("signal_poll").splitlines() if "=" in line)
            info["signal"] = signal_percent(int(poll["RSSI"]))
        except (RuntimeError, KeyError, ValueError):
            pass
        return info

    def scan(self):
        self.cmd("scan")
        self._sleep(4)                       # the driver's scan takes a few seconds
        connected = self._status()
        current = wpa_unescape(connected.get("ssid", "")) if connected.get("wpa_state") == "COMPLETED" else None
        best = {}
        for line in self.cmd("scan_results").splitlines()[1:]:
            f = line.split("\t")
            if len(f) < 5 or not f[4]:
                continue
            ssid = wpa_unescape(f[4])
            try:
                signal = signal_percent(int(f[2]))
            except ValueError:
                signal = 0
            entry = {"ssid": ssid, "signal": signal, "secure": any(k in f[3] for k in ("WPA", "WEP", "SAE")),
                     "in_use": ssid == current}
            if ssid not in best or entry["signal"] > best[ssid]["signal"]:
                best[ssid] = entry
        return sorted(best.values(), key=lambda e: (not e["in_use"], -e["signal"], e["ssid"].lower()))

    def networks(self, ssid):
        """The ids of the saved networks named ssid."""
        ids = []
        for line in self.cmd("list_networks").splitlines()[1:]:
            f = line.split("\t")
            if len(f) >= 2 and wpa_unescape(f[1]) == ssid:
                ids.append(f[0])
        return ids

    def connect(self, ssid, password=None, hidden=False):
        saved = self.networks(ssid)
        if not password and saved:
            net, added = saved[0], False         # the saved password
        else:
            net, added = self.cmd("add_network").strip().splitlines()[-1], True
            self.cmd("set_network", net, "ssid", wpa_text(ssid))
            if password:
                self.cmd("set_network", net, "psk", psk_hex(ssid, password))
            else:
                self.cmd("set_network", net, "key_mgmt", "NONE")
            if hidden:
                self.cmd("set_network", net, "scan_ssid", "1")
        self.cmd("select_network", net)              # disables the others while it tries
        state, seen = "", set()
        for _ in range(self.CONNECT_SECONDS):
            self._sleep(1)
            state = self._status().get("wpa_state", "")
            seen.add(state)
            if state == "COMPLETED":
                break
        ok = state == "COMPLETED"
        if added and not ok:
            self.cmd("remove_network", net)
        if ok and added:
            for old in saved:                        # the new password replaces the old one
                self.cmd("remove_network", old)
        self.cmd("enable_network", "all")            # the other saved networks back on
        if ok:
            self.cmd("save_config")
            return {"ok": True, "message": "CONNECTED"}
        # a handshake that never completes is a wrong password; never getting that far, no network
        return {"ok": False, "message": "WRONG PASSWORD" if "4WAY_HANDSHAKE" in seen else "NO CONNECTION"}

    def forget(self, ssid):
        ids = self.networks(ssid)
        if not ids:
            return {"ok": False, "message": "NOT SAVED"}
        for net in ids:
            self.cmd("remove_network", net)
        self.cmd("save_config")
        self.cmd("reassociate")
        return {"ok": True, "message": "FORGOTTEN"}


# nmcli's messages, shortened to what fits the display
ERRORS = (
    (r"secrets were required|802-1x|psk|password", "WRONG PASSWORD"),
    (r"no network with ssid|not found", "NETWORK NOT FOUND"),
    (r"not authorized|insufficient privileges|permission", "NOT AUTHORIZED"),
    (r"timeout|timed out", "TIMED OUT"),
    (r"no wi-?fi device", "NO WI-FI DEVICE"),
    (r"not running|could not be contacted", "NETWORKMANAGER NOT RUNNING"),
    (r"unknown connection", "NOT SAVED"),
)


def error_text(message):
    text = (message or "").strip()
    for pattern, short in ERRORS:
        if re.search(pattern, text, re.I):
            return short
    text = re.sub(r"^Error:\s*", "", text.splitlines()[-1] if text else "FAILED")
    return text.upper()[:40] or "FAILED"


WPA_RUN = "/run/wpa_supplicant"       # wpa_supplicant's control sockets, one per interface


def wifi_backend():
    """On Linux: NmcliWifi when NetworkManager runs, else WpaCliWifi when wpa_supplicant has a control socket
    (the Jetson image), else NoWifi; elsewhere NoWifi. TRON_WIFI=off (or nmcli / wpa) chooses."""
    choice = os.environ.get("TRON_WIFI", "").lower()
    if choice in ("0", "off", "no") or platform.system() != "Linux":
        return NoWifi()
    nmcli, wpa_cli = shutil.which("nmcli"), shutil.which("wpa_cli")
    if nmcli and choice != "wpa" and (choice == "nmcli" or os.path.isdir("/run/NetworkManager")):
        return NmcliWifi(nmcli)
    sockets = sorted(os.listdir(WPA_RUN)) if os.path.isdir(WPA_RUN) else []
    sockets = [n for n in sockets if not n.startswith("p2p")]
    if wpa_cli and sockets:
        return WpaCliWifi(sockets[0], wpa_cli)
    return NoWifi()
