import os
import shutil
import subprocess
import threading
import time


def _tool():
    if shutil.which("kdotool"):
        return "kdotool"
    if shutil.which("xdotool"):
        return "xdotool"
    return None


def _run(args):
    try:
        env = dict(os.environ)
        uid_bus = f"/run/user/{os.getuid()}/bus"
        if os.path.exists(uid_bus):
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={uid_bus}"
        out = subprocess.run(args, capture_output=True, text=True, timeout=2, env=env)
        return out.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def active_window():
    tool = _tool()
    if tool == "kdotool":
        title = _run(["kdotool", "getactivewindow", "getwindowname"])
        cls = _run(["kdotool", "getactivewindow", "getwindowclassname"])
        return {"title": title, "class": cls}
    if tool == "xdotool":
        title = _run(["xdotool", "getactivewindow", "getwindowname"])
        return {"title": title, "class": ""}
    return None


def match_rules(info, rules):
    if not info:
        return None
    haystack = f"{info.get('title', '')} {info.get('class', '')}".lower()
    for rule in rules:
        pattern = str(rule.get("match", "")).lower()
        if pattern and pattern in haystack:
            return rule.get("profile")
    return None


class ProfileSwitcher(threading.Thread):
    def __init__(
        self,
        engine,
        rules,
        load_profile,
        default_profile_name=None,
        interval=0.5,
        on_switch=None,
    ):
        super().__init__(daemon=True)
        self.engine = engine
        self.rules = list(rules)
        self.load_profile = load_profile
        self.default_profile_name = default_profile_name
        self.interval = interval
        self.on_switch = on_switch
        self._stop = threading.Event()
        self._current = default_profile_name

    def set_rules(self, rules):
        self.rules = list(rules)

    def set_default_profile(self, name):
        self.default_profile_name = name

    def run(self):
        while not self._stop.is_set():
            info = active_window()
            name = match_rules(info, self.rules)
            target = name if name else self.default_profile_name
            if target and target != self._current:
                try:
                    profile = self.load_profile(target)
                    self.engine.set_profile(profile)
                    self._current = target
                    if self.on_switch is not None:
                        self.on_switch(target, profile)
                except (OSError, ValueError):
                    pass
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
