import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from evdev import ecodes as e
from joymap import config, jtkcfg

WASD = """[General]
FileVersion=57
NumberOfJoysticks=2
NumberOfButtons=32

[Joystick 1]
POV1-3=1, 44:00:00:00, 0.000, 0, 0
POV1-5=1, 53:00:00:00, 0.000, 0, 0
POV1-7=1, 41:00:00:00, 0.000, 0, 0
Button01=1, 5A:00:00:00, 0.000, 0, 0
Button02=1, 57:00:00:00, 0.000, 0, 0
Button09=1, 1B:00:00:00, 0.000, 0, 0
"""

COMBO = """[General]
FileVersion=61
NumberOfJoysticks=1

[Joystick 1]
Button07=1, A4:73:00:00, 0.000, 0, 0
Button01=1, 101:00:00:00, 0.000, 0, 0
Button03=9, "C:\\Program Files (x86)\\Steam\\Steam.exe"
"""

SEQ = """[General]
FileVersion=68
NumberOfJoysticks=1

[Joystick 1]
Button24=7, 3, 500, 53:0:0:0, 49:0:0:0, 0:0:0:0, 0:0:0:0, 95, 100, 0.000, 0, 0, 20, 0  ##starter
"""


def test_wasd():
    cfg = jtkcfg.parse(WASD)
    j1 = cfg.joysticks[1].entries
    assert j1["Button02"].keys == [e.KEY_W]
    assert j1["Button01"].keys == [e.KEY_Z]
    assert j1["POV1-7"].keys == [e.KEY_A]
    assert j1["POV1-3"].keys == [e.KEY_D]
    assert j1["Button09"].keys == [e.KEY_ESC]


def test_combo_and_mouse():
    cfg = jtkcfg.parse(COMBO)
    j1 = cfg.joysticks[1].entries
    assert j1["Button07"].keys == [e.KEY_LEFTALT, e.KEY_F4]
    assert j1["Button01"].keys == [e.BTN_LEFT]
    assert j1["Button03"].action == jtkcfg.TYPE_LAUNCH
    assert j1["Button03"].payload.endswith("Steam.exe")


def test_sequence():
    cfg = jtkcfg.parse(SEQ)
    entry = cfg.joysticks[1].entries["Button24"]
    assert entry.action == jtkcfg.TYPE_SEQUENCE
    assert entry.steps[0] == [e.KEY_S]
    assert entry.steps[1] == [e.KEY_I]
    assert entry.comment == "starter"


def test_roundtrip():
    cfg = jtkcfg.parse(WASD)
    out = jtkcfg.dump(cfg)
    cfg2 = jtkcfg.parse(out)
    assert cfg2.joysticks[1].entries["Button02"].keys == [e.KEY_W]


def test_scan_directory():
    folder = "/tmp/opencode/jtk-cfgs"
    files = glob.glob(os.path.join(folder, "**", "*.cfg"), recursive=True)
    if not files:
        return
    total = 0
    for path in files:
        cfg = jtkcfg.parse_file(path)
        for js in cfg.joysticks.values():
            total += len(js.entries)
    assert total > 0


def test_import_features():
    path = "/home/danft/Escritorio/Krita.cfg"
    if not os.path.exists(path):
        return
    profile, unsupp = config.import_jtkcfg(path)
    assert profile.name == "Krita"
    assert not unsupp
    # Sequence -> MODE_ROTATE
    btn5 = profile.buttons[e.BTN_TL]  # L1
    assert btn5.mode == "rotate"
    assert len(btn5.assignments) == 3
    assert btn5.assignments[0].keys == [e.KEY_B]
    assert btn5.assignments[1].keys == [e.KEY_LEFTSHIFT, e.KEY_B]
    assert btn5.assignments[2].keys == [e.KEY_LEFTSHIFT, e.KEY_V]
    # Auto-repeat & delay
    axis16_neg = profile.axes[e.ABS_HAT0X].negative
    assert axis16_neg.auto_repeat is True
    assert axis16_neg.repeat_delay_ms == 700
    assert axis16_neg.interval_ms == 125  # 1000 / 8
    # Button 14 -> Touchpad Click
    btn14 = profile.buttons[272]
    assert btn14.assignments[0].keys == [e.KEY_LEFTSHIFT]


if __name__ == "__main__":
    test_wasd()
    test_combo_and_mouse()
    test_sequence()
    test_roundtrip()
    test_scan_directory()
    test_import_features()
    print("OK - parser de .cfg funciona")
