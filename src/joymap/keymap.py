from evdev import ecodes as _e


def _k(name):
    return _e.ecodes[name]


VK_TO_KEY = {
    0x08: _k("KEY_BACKSPACE"),
    0x09: _k("KEY_TAB"),
    0x0D: _k("KEY_ENTER"),
    0x10: _k("KEY_LEFTSHIFT"),
    0x11: _k("KEY_LEFTCTRL"),
    0x12: _k("KEY_LEFTALT"),
    0x13: _k("KEY_PAUSE"),
    0x14: _k("KEY_CAPSLOCK"),
    0x1B: _k("KEY_ESC"),
    0x20: _k("KEY_SPACE"),
    0x21: _k("KEY_PAGEUP"),
    0x22: _k("KEY_PAGEDOWN"),
    0x23: _k("KEY_END"),
    0x24: _k("KEY_HOME"),
    0x25: _k("KEY_LEFT"),
    0x26: _k("KEY_UP"),
    0x27: _k("KEY_RIGHT"),
    0x28: _k("KEY_DOWN"),
    0x2C: _k("KEY_SYSRQ"),
    0x2D: _k("KEY_INSERT"),
    0x2E: _k("KEY_DELETE"),
    0x5B: _k("KEY_LEFTMETA"),
    0x5C: _k("KEY_RIGHTMETA"),
    0x5D: _k("KEY_COMPOSE"),
    0x90: _k("KEY_NUMLOCK"),
    0x91: _k("KEY_SCROLLLOCK"),
    0xA0: _k("KEY_LEFTSHIFT"),
    0xA1: _k("KEY_RIGHTSHIFT"),
    0xA2: _k("KEY_LEFTCTRL"),
    0xA3: _k("KEY_RIGHTCTRL"),
    0xA4: _k("KEY_LEFTALT"),
    0xA5: _k("KEY_RIGHTALT"),
    0xBA: _k("KEY_SEMICOLON"),
    0xBB: _k("KEY_EQUAL"),
    0xBC: _k("KEY_COMMA"),
    0xBD: _k("KEY_MINUS"),
    0xBE: _k("KEY_DOT"),
    0xBF: _k("KEY_SLASH"),
    0xC0: _k("KEY_GRAVE"),
    0xDB: _k("KEY_LEFTBRACE"),
    0xDC: _k("KEY_BACKSLASH"),
    0xDD: _k("KEY_RIGHTBRACE"),
    0xDE: _k("KEY_APOSTROPHE"),
    0x6A: _k("KEY_KPASTERISK"),
    0x6B: _k("KEY_KPPLUS"),
    0x6C: _k("KEY_KPCOMMA"),
    0x6D: _k("KEY_KPMINUS"),
    0x6E: _k("KEY_KPDOT"),
    0x6F: _k("KEY_KPSLASH"),
}

for _i in range(10):
    VK_TO_KEY[0x30 + _i] = _k(f"KEY_{_i}")
    VK_TO_KEY[0x60 + _i] = _k(f"KEY_KP{_i}")

for _i in range(26):
    VK_TO_KEY[0x41 + _i] = _k(f"KEY_{chr(0x41 + _i)}")

for _i in range(24):
    VK_TO_KEY[0x70 + _i] = _k(f"KEY_F{_i + 1}")

MOUSE_VK_TO_KEY = {
    0x101: _k("BTN_LEFT"),
    0x102: _k("BTN_RIGHT"),
    0x104: _k("BTN_MIDDLE"),
    0x105: _k("BTN_SIDE"),
    0x106: _k("BTN_EXTRA"),
}

VK_TO_KEY.update(MOUSE_VK_TO_KEY)

KEY_TO_VK = {}
for _vk, _kc in VK_TO_KEY.items():
    if _vk < 0x100:
        KEY_TO_VK.setdefault(_kc, _vk)


def vk_to_key(vk):
    return VK_TO_KEY.get(vk)


def key_to_vk(key):
    return KEY_TO_VK.get(key)


def key_name(key):
    return _e.KEY.get(key, f"KEY_{key}") if hasattr(_e, "KEY") else str(key)
