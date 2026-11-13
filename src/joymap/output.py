import threading

from evdev import UInput, ecodes as e


def _key_codes():
    codes = set(e.KEY.keys()) | set(e.BTN.keys())
    return sorted(c for c in codes if 0 < c <= 0x2FF)


def create_virtual(name="joymap-virtual"):
    caps = {
        e.EV_KEY: _key_codes(),
        e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL, e.REL_HWHEEL],
    }
    return UInput(caps, name=name)


class VirtualOutput:
    def __init__(self, name="joymap-virtual"):
        self.ui = create_virtual(name)
        self._lock = threading.Lock()
        self._down = set()

    def key_down(self, key):
        with self._lock:
            if key in self._down:
                return
            self._down.add(key)
            self.ui.write(e.EV_KEY, key, 1)
            self.ui.syn()

    def key_up(self, key):
        with self._lock:
            if key not in self._down:
                return
            self._down.discard(key)
            self.ui.write(e.EV_KEY, key, 0)
            self.ui.syn()

    def press(self, keys):
        for key in keys:
            self.key_down(key)

    def release(self, keys):
        for key in keys:
            self.key_up(key)

    def tap(self, keys):
        self.press(keys)
        self.release(keys)

    def move(self, dx=0, dy=0, wheel=0, hwheel=0):
        with self._lock:
            if dx:
                self.ui.write(e.EV_REL, e.REL_X, int(dx))
            if dy:
                self.ui.write(e.EV_REL, e.REL_Y, int(dy))
            if wheel:
                self.ui.write(e.EV_REL, e.REL_WHEEL, int(wheel))
            if hwheel:
                self.ui.write(e.EV_REL, e.REL_HWHEEL, int(hwheel))
            self.ui.syn()

    def release_all(self):
        for key in list(self._down):
            self.key_up(key)

    def close(self):
        self.release_all()
        self.ui.close()
