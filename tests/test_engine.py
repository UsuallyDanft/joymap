import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from evdev import ecodes as e
from evdev.events import InputEvent

from joymap.mapping import (
    Assignment,
    AxisMapping,
    ButtonMapping,
    MappingEngine,
    MODE_NORMAL,
    MODE_REPEAT,
    MODE_ROTATE,
    Profile,
)


class FakeOutput:
    def __init__(self):
        self.log = []
        self.down = set()

    def press(self, keys):
        for k in keys:
            if k not in self.down:
                self.down.add(k)
                self.log.append(("down", k))

    def release(self, keys):
        for k in keys:
            if k in self.down:
                self.down.discard(k)
                self.log.append(("up", k))

    def tap(self, keys):
        self.press(keys)
        self.release(keys)

    def release_all(self):
        for k in list(self.down):
            self.release([k])


def make_engine(profile, axis_info=None):
    out = FakeOutput()
    eng = MappingEngine(out, axis_info=axis_info)
    eng.set_profile(profile)
    return eng, out


def test_button_normal():
    p = Profile()
    p.buttons[e.BTN_SOUTH] = ButtonMapping(
        mode=MODE_NORMAL, assignments=[Assignment(keys=[e.KEY_SPACE])]
    )
    eng, out = make_engine(p)
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_SOUTH, 1))
    assert ("down", e.KEY_SPACE) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_SOUTH, 0))
    assert ("up", e.KEY_SPACE) in out.log


def test_button_rotate():
    p = Profile()
    p.buttons[e.BTN_SOUTH] = ButtonMapping(
        mode=MODE_ROTATE,
        assignments=[Assignment(keys=[e.KEY_1]), Assignment(keys=[e.KEY_2])],
    )
    eng, out = make_engine(p)
    for _ in range(2):
        eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_SOUTH, 1))
        eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_SOUTH, 0))
    downs = [k for (kind, k) in out.log if kind == "down"]
    assert downs == [e.KEY_1, e.KEY_2]


def test_button_repeat():
    p = Profile()
    p.buttons[e.BTN_SOUTH] = ButtonMapping(
        mode=MODE_REPEAT, assignments=[Assignment(keys=[e.KEY_A])], interval_ms=10
    )
    eng, out = make_engine(p)
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_SOUTH, 1))
    time.sleep(0.06)
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_SOUTH, 0))
    taps = [k for (kind, k) in out.log if kind == "down"]
    assert len(taps) >= 2


def test_stick():
    p = Profile()
    axis = AxisMapping(deadzone=0.25)
    axis.negative = ButtonMapping(assignments=[Assignment(keys=[e.KEY_LEFT])])
    axis.positive = ButtonMapping(assignments=[Assignment(keys=[e.KEY_RIGHT])])
    p.axes[e.ABS_X] = axis
    eng, out = make_engine(p, {e.ABS_X: (0, 255)})

    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_X, 128))
    assert not out.log
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_X, 200))
    assert ("down", e.KEY_RIGHT) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_X, 128))
    assert ("up", e.KEY_RIGHT) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_X, 20))
    assert ("down", e.KEY_LEFT) in out.log


def test_trigger():
    p = Profile()
    axis = AxisMapping(deadzone=0.25)
    axis.positive = ButtonMapping(assignments=[Assignment(keys=[e.KEY_F1])])
    p.axes[e.ABS_Z] = axis
    eng, out = make_engine(p, {e.ABS_Z: (0, 255)})

    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_Z, 10))
    assert not out.log
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_Z, 255))
    assert ("down", e.KEY_F1) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_Z, 0))
    assert ("up", e.KEY_F1) in out.log


def test_hat():
    p = Profile()
    axis = AxisMapping(deadzone=0.0)
    axis.positive = ButtonMapping(assignments=[Assignment(keys=[e.KEY_D])])
    axis.negative = ButtonMapping(assignments=[Assignment(keys=[e.KEY_A])])
    p.axes[e.ABS_HAT0X] = axis
    eng, out = make_engine(p)

    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_HAT0X, 1))
    assert ("down", e.KEY_D) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_HAT0X, 0))
    assert ("up", e.KEY_D) in out.log


def test_sticks_both():
    p = Profile()
    # Left stick Y (up/down)
    axis_ly = AxisMapping(deadzone=0.25)
    axis_ly.negative = ButtonMapping(assignments=[Assignment(keys=[e.KEY_W])])
    axis_ly.positive = ButtonMapping(assignments=[Assignment(keys=[e.KEY_S])])
    p.axes[e.ABS_Y] = axis_ly

    # Right stick X (left/right)
    axis_rx = AxisMapping(deadzone=0.25)
    axis_rx.negative = ButtonMapping(assignments=[Assignment(keys=[e.KEY_J])])
    axis_rx.positive = ButtonMapping(assignments=[Assignment(keys=[e.KEY_L])])
    p.axes[e.ABS_RX] = axis_rx

    axis_info = {
        e.ABS_Y: (0, 255),
        e.ABS_RX: (0, 255),
    }
    eng, out = make_engine(p, axis_info)

    # Stick izquierdo hacia arriba
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_Y, 20))
    assert ("down", e.KEY_W) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_Y, 128))
    assert ("up", e.KEY_W) in out.log

    # Stick derecho hacia la derecha
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_RX, 240))
    assert ("down", e.KEY_L) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_RX, 128))
    assert ("up", e.KEY_L) in out.log


def test_stick_z_rz_as_stick():
    # En mandos antiguos sin RX/RY, Z y RZ actúan como stick 2 (centrados en 128)
    p = Profile()
    axis_z = AxisMapping(deadzone=0.25)
    axis_z.negative = ButtonMapping(assignments=[Assignment(keys=[e.KEY_LEFT])])
    axis_z.positive = ButtonMapping(assignments=[Assignment(keys=[e.KEY_RIGHT])])
    p.axes[e.ABS_Z] = axis_z

    out = FakeOutput()
    eng = MappingEngine(out, axis_info={e.ABS_Z: (0, 255)}, axis_types={e.ABS_Z: "stick"})
    eng.set_profile(p)

    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_Z, 20))
    assert ("down", e.KEY_LEFT) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_ABS, e.ABS_Z, 128))
    assert ("up", e.KEY_LEFT) in out.log


def test_button_rotate_loop():
    # Prueba del caso de rotación en bucle: Q -> Espacio -> Ctrl+Q -> Q ...
    p = Profile()
    p.buttons[e.BTN_WEST] = ButtonMapping(
        mode=MODE_ROTATE,
        assignments=[
            Assignment(keys=[e.KEY_Q]),
            Assignment(keys=[e.KEY_SPACE]),
            Assignment(keys=[e.KEY_LEFTCTRL, e.KEY_Q]),
        ],
    )
    eng, out = make_engine(p)

    # 1. Pulsación 1: Q
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_WEST, 1))
    assert ("down", e.KEY_Q) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_WEST, 0))
    assert ("up", e.KEY_Q) in out.log
    out.log.clear()

    # 2. Pulsación 2: Espacio
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_WEST, 1))
    assert ("down", e.KEY_SPACE) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_WEST, 0))
    assert ("up", e.KEY_SPACE) in out.log
    out.log.clear()

    # 3. Pulsación 3: Ctrl + Q
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_WEST, 1))
    assert ("down", e.KEY_LEFTCTRL) in out.log
    assert ("down", e.KEY_Q) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_WEST, 0))
    assert ("up", e.KEY_LEFTCTRL) in out.log
    assert ("up", e.KEY_Q) in out.log
    out.log.clear()

    # 4. Pulsación 4: vuelve a Q (bucle cíclico)
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_WEST, 1))
    assert ("down", e.KEY_Q) in out.log
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_WEST, 0))
    assert ("up", e.KEY_Q) in out.log


def test_auto_repeat_normal():
    # Modo normal con auto-repetición y retardo inicial
    p = Profile()
    p.buttons[e.BTN_SOUTH] = ButtonMapping(
        mode=MODE_NORMAL,
        auto_repeat=True,
        repeat_delay_ms=80,
        interval_ms=20,
        assignments=[Assignment(keys=[e.KEY_SPACE])],
    )
    eng, out = make_engine(p)

    # 1. Toque rápido (menor que el retardo de 80ms) -> solo un down y un up
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_SOUTH, 1))
    time.sleep(0.02)
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_SOUTH, 0))
    time.sleep(0.01)
    assert out.log == [("down", e.KEY_SPACE), ("up", e.KEY_SPACE)]
    out.log.clear()

    # 2. Mantener presionado más allá del retardo (80ms delay + 20ms intervalo)
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_SOUTH, 1))
    time.sleep(0.16)
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_SOUTH, 0))
    time.sleep(0.02)
    downs = [k for (kind, k) in out.log if kind == "down"]
    assert len(downs) >= 3
    assert all(k == e.KEY_SPACE for k in downs)
    assert not out.down  # Todo liberado al soltar


def test_auto_repeat_rotate():
    # Modo rotar con auto-repetición continua en bucle
    p = Profile()
    p.buttons[e.BTN_NORTH] = ButtonMapping(
        mode=MODE_ROTATE,
        auto_repeat=True,
        repeat_delay_ms=40,
        interval_ms=20,
        assignments=[
            Assignment(keys=[e.KEY_A]),
            Assignment(keys=[e.KEY_B]),
            Assignment(keys=[e.KEY_C]),
        ],
    )
    eng, out = make_engine(p)

    # 1. Toque rápido: debe ejecutar solo el paso 1 (A)
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_NORTH, 1))
    time.sleep(0.01)
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_NORTH, 0))
    time.sleep(0.01)
    downs = [k for (kind, k) in out.log if kind == "down"]
    assert downs == [e.KEY_A]
    out.log.clear()

    # 2. Mantener presionado: debe iniciar en B, luego C, A, B...
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_NORTH, 1))
    time.sleep(0.13)
    eng.handle_event(InputEvent(1, 0, e.EV_KEY, e.BTN_NORTH, 0))
    time.sleep(0.02)
    downs = [k for (kind, k) in out.log if kind == "down"]
    # Debe haber ejecutado al menos B, C y A
    assert len(downs) >= 3
    assert downs[0] == e.KEY_B
    assert downs[1] == e.KEY_C
    assert downs[2] == e.KEY_A
    assert not out.down


def test_button_mapping_dict_migration():
    # Compatibilidad hacia atrás: modo "repeat" se convierte en "normal" + auto_repeat=True
    legacy = {
        "mode": "repeat",
        "interval_ms": 25,
        "assignments": [{"keys": [57]}],
    }
    m = ButtonMapping.from_dict(legacy)
    assert m.mode == MODE_NORMAL
    assert m.auto_repeat is True
    assert m.repeat_delay_ms == 0
    assert m.interval_ms == 25

    # Serialización y deserialización completa
    d = m.to_dict()
    assert d["mode"] == MODE_NORMAL
    assert d["auto_repeat"] is True
    assert d["repeat_delay_ms"] == 0
    assert d["interval_ms"] == 25
    m2 = ButtonMapping.from_dict(d)
    assert m2.auto_repeat is True
    assert m2.repeat_delay_ms == 0


if __name__ == "__main__":
    test_button_normal()
    test_button_rotate()
    test_button_repeat()
    test_stick()
    test_trigger()
    test_hat()
    test_sticks_both()
    test_stick_z_rz_as_stick()
    test_button_rotate_loop()
    test_auto_repeat_normal()
    test_auto_repeat_rotate()
    test_button_mapping_dict_migration()
    print("OK - motor (botones + ejes) funciona")
