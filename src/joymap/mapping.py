import threading
from dataclasses import dataclass, field

from evdev import ecodes as e

MODE_NORMAL = "normal"
MODE_REPEAT = "repeat"
MODE_ROTATE = "rotate"

HAT_AXES = {
    e.ABS_HAT0X, e.ABS_HAT0Y,
    e.ABS_HAT1X, e.ABS_HAT1Y,
    e.ABS_HAT2X, e.ABS_HAT2Y,
    e.ABS_HAT3X, e.ABS_HAT3Y,
}

STICK_AXES = {e.ABS_X, e.ABS_Y, e.ABS_RX, e.ABS_RY}
TRIGGER_AXES = {e.ABS_Z, e.ABS_RZ, e.ABS_BRAKE, e.ABS_GAS}

DEFAULT_DEADZONE = 0.25


def axis_direction(code, value, axis_info=None, deadzone=DEFAULT_DEADZONE, axis_type=None, available_axes=None):
    if axis_type == "hat" or (axis_type is None and code in HAT_AXES):
        return (value > 0) - (value < 0)

    codes = set(available_axes or (axis_info.keys() if axis_info else []))
    is_trigger = False
    if axis_type == "trigger":
        is_trigger = True
    elif axis_type is None:
        if code in (e.ABS_BRAKE, e.ABS_GAS):
            is_trigger = True
        elif code in (e.ABS_Z, e.ABS_RZ):
            if not codes or (e.ABS_RX in codes or e.ABS_RY in codes):
                is_trigger = True

    lo, hi = (axis_info or {}).get(code, (0, 255))
    if is_trigger:
        span = (hi - lo) or 1
        return 1 if (value - lo) / span >= deadzone else 0

    center = (lo + hi) / 2.0
    half = (hi - lo) / 2.0 or 1.0
    delta = value - center
    dead = deadzone * half
    if delta <= -dead:
        return -1
    if delta >= dead:
        return 1
    return 0


@dataclass
class Assignment:
    keys: list = field(default_factory=list)

    def to_dict(self):
        return {"keys": list(self.keys)}

    @classmethod
    def from_dict(cls, data):
        return cls(keys=list(data.get("keys", [])))


@dataclass
class ButtonMapping:
    mode: str = MODE_NORMAL
    assignments: list = field(default_factory=list)
    auto_repeat: bool = False
    repeat_delay_ms: int = 300
    interval_ms: int = 100

    def __post_init__(self):
        if self.mode == MODE_REPEAT:
            self.auto_repeat = True
            if self.repeat_delay_ms == 300:
                self.repeat_delay_ms = 0

    def to_dict(self):
        return {
            "mode": self.mode,
            "auto_repeat": self.auto_repeat,
            "repeat_delay_ms": self.repeat_delay_ms,
            "interval_ms": self.interval_ms,
            "assignments": [a.to_dict() for a in self.assignments],
        }

    @classmethod
    def from_dict(cls, data):
        mode = data.get("mode", MODE_NORMAL)
        auto_repeat = data.get("auto_repeat", False)
        repeat_delay_ms = int(data.get("repeat_delay_ms", 300))
        if mode == MODE_REPEAT:
            mode = MODE_NORMAL
            auto_repeat = True
            if "repeat_delay_ms" not in data:
                repeat_delay_ms = 0
        return cls(
            mode=mode,
            auto_repeat=bool(auto_repeat),
            repeat_delay_ms=repeat_delay_ms,
            interval_ms=int(data.get("interval_ms", 100)),
            assignments=[Assignment.from_dict(a) for a in data.get("assignments", [])],
        )


@dataclass
class AxisMapping:
    negative: ButtonMapping = field(default_factory=ButtonMapping)
    positive: ButtonMapping = field(default_factory=ButtonMapping)
    deadzone: float = DEFAULT_DEADZONE

    def to_dict(self):
        return {
            "deadzone": self.deadzone,
            "negative": self.negative.to_dict(),
            "positive": self.positive.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            deadzone=float(data.get("deadzone", DEFAULT_DEADZONE)),
            negative=ButtonMapping.from_dict(data.get("negative", {})),
            positive=ButtonMapping.from_dict(data.get("positive", {})),
        )


@dataclass
class Profile:
    name: str = "default"
    buttons: dict = field(default_factory=dict)
    axes: dict = field(default_factory=dict)
    window_rules: list = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "window_rules": self.window_rules,
            "buttons": {str(k): v.to_dict() for k, v in self.buttons.items()},
            "axes": {str(k): v.to_dict() for k, v in self.axes.items()},
        }

    @classmethod
    def from_dict(cls, data):
        buttons = {
            int(k): ButtonMapping.from_dict(v)
            for k, v in data.get("buttons", {}).items()
        }
        axes = {
            int(k): AxisMapping.from_dict(v)
            for k, v in data.get("axes", {}).items()
        }
        return cls(
            name=data.get("name", "default"),
            buttons=buttons,
            axes=axes,
            window_rules=list(data.get("window_rules", [])),
        )


class MappingEngine:
    def __init__(self, output, axis_info=None, axis_types=None):
        self.output = output
        self.profile = Profile()
        self.axis_info = dict(axis_info or {})
        self.axis_types = dict(axis_types or {})
        self._rotate_index = {}
        self._active_keys = {}
        self._repeat_stop = {}
        self._axis_state = {}
        self._lock = threading.Lock()

    def set_axis_info(self, axis_info, axis_types=None):
        self.axis_info = dict(axis_info or {})
        if axis_types is not None:
            self.axis_types = dict(axis_types)

    def set_profile(self, profile):
        with self._lock:
            self._stop_all_repeats()
            self.output.release_all()
            self.profile = profile
            self._rotate_index.clear()
            self._active_keys.clear()
            self._axis_state.clear()

    def _stop_all_repeats(self):
        for slot, ev in list(self._repeat_stop.items()):
            ev.set()
        self._repeat_stop.clear()

    def handle_event(self, event):
        if event.type == e.EV_KEY:
            self.handle_button(event.code, event.value)
        elif event.type == e.EV_ABS:
            self.handle_axis(event.code, event.value)

    def handle_button(self, code, value):
        mapping = self.profile.buttons.get(code)
        if not mapping or not mapping.assignments:
            return
        if value == 1:
            self._activate(code, mapping)
        elif value == 0:
            self._deactivate(code, mapping)

    def handle_axis(self, code, value):
        mapping = self.profile.axes.get(code)
        if mapping is None:
            return
        axis_type = self.axis_types.get(code)
        direction = axis_direction(
            code,
            value,
            self.axis_info,
            mapping.deadzone,
            axis_type=axis_type,
            available_axes=self.axis_info.keys(),
        )

        previous = self._axis_state.get(code, 0)
        if direction == previous:
            return
        if previous != 0:
            sub = mapping.negative if previous < 0 else mapping.positive
            self._deactivate((code, previous), sub)
        self._axis_state[code] = direction
        if direction != 0:
            sub = mapping.negative if direction < 0 else mapping.positive
            if sub.assignments:
                self._activate((code, direction), sub)

    def _activate(self, slot, mapping):
        if mapping.auto_repeat or mapping.mode == MODE_REPEAT:
            self._start_repeat(slot, mapping)
            return
        if mapping.mode == MODE_ROTATE:
            idx = self._rotate_index.get(slot, 0)
            assignment = mapping.assignments[idx % len(mapping.assignments)]
            self._rotate_index[slot] = (idx + 1) % len(mapping.assignments)
        else:
            assignment = mapping.assignments[0]
        keys = list(assignment.keys)
        self._active_keys[slot] = keys
        self.output.press(keys)

    def _deactivate(self, slot, mapping):
        if mapping.auto_repeat or mapping.mode == MODE_REPEAT:
            self._stop_repeat(slot)
            return
        keys = self._active_keys.pop(slot, [])
        self.output.release(keys)

    def _start_repeat(self, slot, mapping):
        if slot in self._repeat_stop:
            return
        stop = threading.Event()
        self._repeat_stop[slot] = stop

        delay_sec = max(0, mapping.repeat_delay_ms) / 1000.0
        interval_sec = max(mapping.interval_ms, 5) / 1000.0
        pulse_hold = min(0.02, interval_sec / 2.0)

        def get_next_keys():
            if mapping.mode == MODE_ROTATE:
                idx = self._rotate_index.get(slot, 0)
                assignment = mapping.assignments[idx % len(mapping.assignments)]
                self._rotate_index[slot] = (idx + 1) % len(mapping.assignments)
            else:
                assignment = mapping.assignments[0]
            return list(assignment.keys)

        def worker():
            held_keys = []
            try:
                # Disparo inicial inmediato al presionar
                held_keys = get_next_keys()
                self.output.press(held_keys)

                if delay_sec > 0:
                    # Espera antes de iniciar la repetición periódica
                    if stop.wait(delay_sec):
                        # Se soltó antes del delay (pulsación simple)
                        return
                    # Fin de la espera inicial: liberar la pulsación inicial
                    self.output.release(held_keys)
                    held_keys = []
                    gap = max(0.0, interval_sec - pulse_hold)
                    if stop.wait(gap):
                        return
                else:
                    # Repetición inmediata (delay = 0)
                    if stop.wait(pulse_hold):
                        return
                    self.output.release(held_keys)
                    held_keys = []
                    gap = max(0.0, interval_sec - pulse_hold)
                    if stop.wait(gap):
                        return

                # Bucle de repetición continua mientras se mantenga presionado
                while not stop.is_set():
                    held_keys = get_next_keys()
                    self.output.press(held_keys)
                    if stop.wait(pulse_hold):
                        return
                    self.output.release(held_keys)
                    held_keys = []
                    gap = max(0.0, interval_sec - pulse_hold)
                    if stop.wait(gap):
                        return
            finally:
                if held_keys:
                    self.output.release(held_keys)

        threading.Thread(target=worker, daemon=True).start()

    def _stop_repeat(self, slot):
        stop = self._repeat_stop.pop(slot, None)
        if stop is not None:
            stop.set()
