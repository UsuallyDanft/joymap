import json
import os

from evdev import ecodes as e

from . import jtkcfg
from .mapping import Assignment, AxisMapping, ButtonMapping, DEFAULT_DEADZONE, HAT_AXES, Profile, MODE_NORMAL, MODE_ROTATE

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "joymap"
)
PROFILES_DIR = os.path.join(CONFIG_DIR, "profiles")
RULES_FILE = os.path.join(CONFIG_DIR, "rules.json")

DINPUT_BUTTONS = {
    1: e.BTN_SOUTH,
    2: e.BTN_EAST,
    3: e.BTN_WEST,
    4: e.BTN_NORTH,
    5: e.BTN_TL,
    6: e.BTN_TR,
    7: e.BTN_TL2,
    8: e.BTN_TR2,
    9: e.BTN_SELECT,
    10: e.BTN_START,
    11: e.BTN_THUMBL,
    12: e.BTN_THUMBR,
    13: e.BTN_MODE,
    14: getattr(e, "BTN_LEFT", 272),
}

DINPUT_AXES = {
    1: e.ABS_X,
    2: e.ABS_Y,
    3: e.ABS_Z,
    4: e.ABS_RX,
    5: e.ABS_RY,
    6: e.ABS_RZ,
}

POV_AXES = {
    "POV1-1": (e.ABS_HAT0Y, -1),
    "POV1-3": (e.ABS_HAT0X, 1),
    "POV1-5": (e.ABS_HAT0Y, 1),
    "POV1-7": (e.ABS_HAT0X, -1),
    "POV2-1": (e.ABS_HAT1Y, -1),
    "POV2-3": (e.ABS_HAT1X, 1),
    "POV2-5": (e.ABS_HAT1Y, 1),
    "POV2-7": (e.ABS_HAT1X, -1),
}


def _ensure_dirs():
    os.makedirs(PROFILES_DIR, exist_ok=True)


def save_profile(profile, path=None):
    if path is None:
        _ensure_dirs()
        path = os.path.join(PROFILES_DIR, f"{profile.name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(profile.to_dict(), fh, indent=2, ensure_ascii=False)
    return path


def load_profile(path):
    with open(path, "r", encoding="utf-8") as fh:
        return Profile.from_dict(json.load(fh))


def list_profiles():
    if not os.path.isdir(PROFILES_DIR):
        return []
    return sorted(
        os.path.join(PROFILES_DIR, f)
        for f in os.listdir(PROFILES_DIR)
        if f.endswith(".json")
    )


def get_profile_names():
    return [os.path.splitext(os.path.basename(f))[0] for f in list_profiles()]


def load_profile_by_name(name):
    filename = name if name.endswith(".json") else f"{name}.json"
    return load_profile(os.path.join(PROFILES_DIR, filename))


def load_rules():
    if os.path.exists(RULES_FILE):
        with open(RULES_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return []


def save_rules(rules):
    _ensure_dirs()
    with open(RULES_FILE, "w", encoding="utf-8") as fh:
        json.dump(rules, fh, indent=2, ensure_ascii=False)


def import_jtkcfg(path):
    cfg = jtkcfg.parse_file(path)
    profile = Profile(name=os.path.splitext(os.path.basename(path))[0])
    unsupported = []

    th1 = DEFAULT_DEADZONE
    th2 = DEFAULT_DEADZONE
    if "Threshold" in cfg.general:
        try:
            th1 = float(cfg.general["Threshold"]) / 100.0
        except ValueError:
            pass
    if "Threshold2" in cfg.general:
        try:
            th2 = float(cfg.general["Threshold2"]) / 100.0
        except ValueError:
            pass

    joysticks = cfg.joysticks.get(1)
    if joysticks is None and cfg.joysticks:
        joysticks = next(iter(cfg.joysticks.values()))
    if joysticks is None:
        return profile, unsupported

    def key_assignment(entry):
        if entry.action == jtkcfg.TYPE_KEY and entry.keys:
            auto_repeat = False
            repeat_delay_ms = 300
            interval_ms = 100
            if len(entry.raw) > 2:
                try:
                    rep_rate = float(entry.raw[2])
                    if rep_rate > 0:
                        auto_repeat = True
                        interval_ms = max(10, int(round(1000.0 / rep_rate)))
                except ValueError:
                    pass
            if auto_repeat and len(entry.raw) > 4:
                try:
                    repeat_delay_ms = int(float(entry.raw[4]))
                except ValueError:
                    pass
            return ButtonMapping(
                mode=MODE_NORMAL,
                assignments=[Assignment(keys=list(entry.keys))],
                auto_repeat=auto_repeat,
                repeat_delay_ms=repeat_delay_ms,
                interval_ms=interval_ms,
            )
        if entry.action == jtkcfg.TYPE_SEQUENCE and entry.steps:
            steps = [Assignment(keys=list(step)) for step in entry.steps if step]
            if steps:
                auto_repeat = False
                repeat_delay_ms = 300
                interval_ms = 100
                if len(entry.raw) > 9:
                    try:
                        rep_rate = float(entry.raw[9])
                        if rep_rate > 0:
                            auto_repeat = True
                            interval_ms = max(10, int(round(1000.0 / rep_rate)))
                    except ValueError:
                        pass
                if auto_repeat and len(entry.raw) > 11:
                    try:
                        repeat_delay_ms = int(float(entry.raw[11]))
                    except ValueError:
                        pass
                return ButtonMapping(
                    mode=MODE_ROTATE,
                    assignments=steps,
                    auto_repeat=auto_repeat,
                    repeat_delay_ms=repeat_delay_ms,
                    interval_ms=interval_ms,
                )
        return None

    for target, entry in joysticks.entries.items():
        if target.startswith("Button"):
            try:
                index = int(target[6:])
            except ValueError:
                index = 0
            code = DINPUT_BUTTONS.get(index)
            if code is None:
                continue
            mapping = key_assignment(entry)
            if mapping:
                profile.buttons[code] = mapping
            elif entry.action != jtkcfg.TYPE_NONE:
                unsupported.append(f"{target} (tipo {entry.action})")
            continue

        axis_dir = None
        axis_index = 0
        if target in POV_AXES:
            axis_dir = POV_AXES[target]
        elif target.startswith("Axis") and target[-1] in ("n", "p"):
            try:
                axis_index = int(target[4:-1])
            except ValueError:
                axis_index = 0
            code = DINPUT_AXES.get(axis_index)
            if code is not None:
                axis_dir = (code, -1 if target[-1] == "n" else 1)
        if axis_dir is None:
            continue

        code, direction = axis_dir
        dz = 0.0 if code in HAT_AXES else (th2 if axis_index >= 3 else th1)
        axis = profile.axes.setdefault(code, AxisMapping(deadzone=dz))
        mapping = key_assignment(entry)
        if mapping:
            if direction < 0:
                axis.negative = mapping
            else:
                axis.positive = mapping
        elif entry.action != jtkcfg.TYPE_NONE:
            unsupported.append(f"{target} (tipo {entry.action})")

    return profile, unsupported
