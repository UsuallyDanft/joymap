import glob
import os
from dataclasses import dataclass, field

import evdev
from evdev import ecodes as e

BUTTON_LABELS = {
    e.BTN_SOUTH: "A / Cruz",
    e.BTN_EAST: "B / Circulo",
    e.BTN_NORTH: "Y / Triangulo",
    e.BTN_WEST: "X / Cuadrado",
    e.BTN_TL: "L1",
    e.BTN_TR: "R1",
    e.BTN_TL2: "L2",
    e.BTN_TR2: "R2",
    e.BTN_SELECT: "Select / Share",
    e.BTN_START: "Start / Options",
    e.BTN_MODE: "Home / PS",
    e.BTN_THUMBL: "L3 (stick izq)",
    e.BTN_THUMBR: "R3 (stick der)",
    e.BTN_LEFT: "Clic Touchpad",
    e.BTN_DPAD_UP: "D-Pad Arriba",
    e.BTN_DPAD_DOWN: "D-Pad Abajo",
    e.BTN_DPAD_LEFT: "D-Pad Izquierda",
    e.BTN_DPAD_RIGHT: "D-Pad Derecha",
}

GAMEPAD_BUTTONS = {
    e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST,
    e.BTN_TL, e.BTN_TR, e.BTN_TL2, e.BTN_TR2,
    e.BTN_SELECT, e.BTN_START, e.BTN_MODE,
    e.BTN_THUMBL, e.BTN_THUMBR,
    e.BTN_DPAD_UP, e.BTN_DPAD_DOWN, e.BTN_DPAD_LEFT, e.BTN_DPAD_RIGHT,
}

JOYSTICK_AXES = {
    e.ABS_X, e.ABS_Y, e.ABS_Z, e.ABS_RX, e.ABS_RY, e.ABS_RZ,
    e.ABS_THROTTLE, e.ABS_RUDDER, e.ABS_WHEEL, e.ABS_GAS, e.ABS_BRAKE,
    e.ABS_HAT0X, e.ABS_HAT0Y, e.ABS_HAT1X, e.ABS_HAT1Y,
    e.ABS_HAT2X, e.ABS_HAT2Y, e.ABS_HAT3X, e.ABS_HAT3Y,
}

HAT_AXES = {
    e.ABS_HAT0X, e.ABS_HAT0Y,
    e.ABS_HAT1X, e.ABS_HAT1Y,
    e.ABS_HAT2X, e.ABS_HAT2Y,
    e.ABS_HAT3X, e.ABS_HAT3Y,
}

IGNORED_BUTTON_NAMES = {
    "BTN_TOUCH", "BTN_TOOL_FINGER", "BTN_TOOL_DOUBLETAP",
    "BTN_TOOL_TRIPLETAP", "BTN_TOOL_QUADTAP", "BTN_TOOL_QUINTTAP",
    "BTN_TOOL_PEN", "BTN_STYLUS", "BTN_STYLUS2",
}

SENSOR_NAME_MARKERS = ("Motion Sensors", "Accelerometer", "Gyroscope")


def _resolve_name(raw):
    if isinstance(raw, (list, tuple)):
        return raw[0] if raw else ""
    return raw or ""


def button_label(code):
    if code in BUTTON_LABELS:
        return BUTTON_LABELS[code]
    name = _resolve_name(e.BTN.get(code) or e.KEY.get(code))
    if name:
        return name
    return f"Boton {code}"


def _is_button(code):
    if code in GAMEPAD_BUTTONS or code in BUTTON_LABELS:
        return True
    name = _resolve_name(e.BTN.get(code) or e.KEY.get(code))
    if not name or not str(name).startswith("BTN_"):
        return False
    return name not in IGNORED_BUTTON_NAMES


def classify_axis(code, available_codes=None, info=None):
    if code in HAT_AXES:
        return "hat"
    if code in (e.ABS_BRAKE, e.ABS_GAS):
        return "trigger"
    if code in (e.ABS_X, e.ABS_Y, e.ABS_RX, e.ABS_RY):
        return "stick"
    if code in (e.ABS_Z, e.ABS_RZ):
        codes = set(available_codes or [])
        if e.ABS_RX in codes or e.ABS_RY in codes:
            return "trigger"
        if info is not None:
            val = getattr(info, "value", None)
            min_val = getattr(info, "min", 0)
            if min_val >= 0 and val == 0:
                return "trigger"
        return "stick"
    return "stick"


def is_trigger_axis(code, available_codes=None, info=None):
    return classify_axis(code, available_codes, info) == "trigger"


def axis_label(code, direction, available_codes=None):
    codes = set(available_codes or [])
    axis_type = classify_axis(code, codes)

    if axis_type == "trigger":
        if code in (e.ABS_Z, e.ABS_BRAKE):
            return "Gatillo L2"
        if code in (e.ABS_RZ, e.ABS_GAS):
            return "Gatillo R2"
        axis_name = e.ABS.get(code, f"ABS_{code}")
        return f"Gatillo {axis_name}"

    if code == e.ABS_X:
        return "Stick Izq ← (Izquierda)" if direction < 0 else "Stick Izq → (Derecha)"
    if code == e.ABS_Y:
        return "Stick Izq ↑ (Arriba)" if direction < 0 else "Stick Izq ↓ (Abajo)"

    has_rx_ry = e.ABS_RX in codes or e.ABS_RY in codes
    if has_rx_ry or (code in (e.ABS_RX, e.ABS_RY)):
        if code == e.ABS_RX:
            return "Stick Der ← (Izquierda)" if direction < 0 else "Stick Der → (Derecha)"
        if code == e.ABS_RY:
            return "Stick Der ↑ (Arriba)" if direction < 0 else "Stick Der ↓ (Abajo)"
    else:
        if code == e.ABS_Z:
            return "Stick Der ← (Izquierda)" if direction < 0 else "Stick Der → (Derecha)"
        if code == e.ABS_RZ:
            return "Stick Der ↑ (Arriba)" if direction < 0 else "Stick Der ↓ (Abajo)"

    if code == e.ABS_HAT0X:
        return "D-Pad Izquierda" if direction < 0 else "D-Pad Derecha"
    if code == e.ABS_HAT0Y:
        return "D-Pad Arriba" if direction < 0 else "D-Pad Abajo"
    if code == e.ABS_HAT1X:
        return "POV2 Izquierda" if direction < 0 else "POV2 Derecha"
    if code == e.ABS_HAT1Y:
        return "POV2 Arriba" if direction < 0 else "POV2 Abajo"

    axis_name = e.ABS.get(code, f"ABS_{code}")
    return f"{axis_name} {'negativo' if direction < 0 else 'positivo'}"


def axis_group_name(code, available_codes=None):
    codes = set(available_codes or [])
    axis_type = classify_axis(code, codes)
    if axis_type == "hat":
        return "Cruceta (D-Pad)"
    if axis_type == "trigger":
        return "Gatillos"
    if code in (e.ABS_X, e.ABS_Y):
        return "Stick Izquierdo"
    if code in (e.ABS_RX, e.ABS_RY) or (code in (e.ABS_Z, e.ABS_RZ) and not is_trigger_axis(code, codes)):
        return "Stick Derecho"
    return "Otros Ejes"


def _is_sensor(dev):
    return any(marker in dev.name for marker in SENSOR_NAME_MARKERS)


@dataclass
class Controller:
    name: str
    uniq: str = ""
    paths: list = field(default_factory=list)
    touchpad_paths: list = field(default_factory=list)
    buttons: list = field(default_factory=list)
    axes: list = field(default_factory=list)
    axis_info: dict = field(default_factory=dict)
    axis_types: dict = field(default_factory=dict)
    unreadable_nodes: list = field(default_factory=list)
    _devices: list = field(default_factory=list)

    @property
    def path(self):
        return self.paths[0] if self.paths else ""

    def open_all(self):
        self._devices = []
        for path in self.paths:
            try:
                self._devices.append(evdev.InputDevice(path))
            except (PermissionError, OSError):
                continue
        return self._devices

    def is_touchpad_device(self, dev):
        dev_path = getattr(dev, "path", "")
        if dev_path and dev_path in self.touchpad_paths:
            return True
        name = getattr(dev, "name", "").lower()
        if "touchpad" in name or "trackpad" in name:
            return True
        try:
            caps = dev.capabilities()
            abs_codes = [c for c, _ in caps.get(e.EV_ABS, [])]
            return e.ABS_MT_POSITION_X in abs_codes
        except Exception:
            return False


def _sysfs_parent(path):
    try:
        ev = os.path.basename(path)
        sys_path = f"/sys/class/input/{ev}/device"
        if os.path.exists(sys_path):
            real = os.path.realpath(sys_path)
            return os.path.dirname(real)
    except Exception:
        pass
    return ""


def _looks_like_gamepad(keys, abs_codes):
    if keys & GAMEPAD_BUTTONS:
        return True
    return any(ax in abs_codes for ax in (e.ABS_X, e.ABS_Y, e.ABS_HAT0X, e.ABS_HAT0Y))


def list_controllers(include_all=False):
    groups = {}
    order = []
    blocked_nodes = []

    # Escanear todos los nodos /dev/input/event*
    all_paths = sorted(glob.glob("/dev/input/event*"))
    for path in all_paths:
        try:
            dev = evdev.InputDevice(path)
        except PermissionError:
            ev = os.path.basename(path)
            sys_name = f"/sys/class/input/{ev}/device/name"
            sys_uniq = f"/sys/class/input/{ev}/device/uniq"
            name = open(sys_name).read().strip() if os.path.exists(sys_name) else ""
            uniq = open(sys_uniq).read().strip() if os.path.exists(sys_uniq) else ""
            parent = _sysfs_parent(path)
            blocked_nodes.append({"path": path, "name": name, "uniq": uniq, "parent": parent})
            continue
        except OSError:
            continue

        if _is_sensor(dev):
            continue
        caps = dev.capabilities()
        keys = set(caps.get(e.EV_KEY, []))
        abs_entries = caps.get(e.EV_ABS, [])
        abs_codes = [code for code, _ in abs_entries]
        is_gamepad = bool(keys & GAMEPAD_BUTTONS) or (
            any(ax in abs_codes for ax in (e.ABS_X, e.ABS_Y, e.ABS_HAT0X, e.ABS_HAT0Y))
            and not (e.BTN_LEFT in keys and e.ABS_MT_POSITION_X in abs_codes)
        )
        is_touchpad = (e.BTN_LEFT in keys and e.ABS_MT_POSITION_X in abs_codes) or (
            e.BTN_LEFT in keys and any(t in dev.name.lower() for t in ("touchpad", "trackpad"))
        )
        if not include_all and not (is_gamepad or is_touchpad):
            continue
        if not include_all and not keys and not abs_codes:
            continue

        parent_dev = _sysfs_parent(path)
        key = dev.uniq or parent_dev or dev.name
        if key not in groups:
            groups[key] = {
                "name": dev.name,
                "uniq": dev.uniq,
                "parent": parent_dev,
                "paths": [],
                "buttons": set(),
                "axis_info": {},
                "unreadable_nodes": [],
                "has_gamepad": False,
            }
            order.append(key)
        group = groups[key]
        group["paths"].append(path)
        if is_touchpad:
            group.setdefault("touchpad_paths", []).append(path)

        if is_gamepad:
            group["has_gamepad"] = True
            group["name"] = dev.name
            available_codes = [c for c, _ in abs_entries if c in JOYSTICK_AXES]
            for code, info in abs_entries:
                if code in JOYSTICK_AXES:
                    group["axis_info"][code] = (info.min, info.max)
                    group.setdefault("axis_types", {})[code] = classify_axis(code, available_codes, info)
        for code in keys:
            if _is_button(code):
                group["buttons"].add(code)

    controllers = []
    for key in order:
        group = groups[key]
        if not group["buttons"] and not group["axis_info"]:
            continue
        axis_types = group.get("axis_types", {})
        axes = sorted(group["axis_info"].keys())
        for ax in axes:
            if ax not in axis_types:
                axis_types[ax] = classify_axis(ax, axes)

        buttons = set(group["buttons"])
        triggers = [ax for ax, t in axis_types.items() if t == "trigger"]
        if any(ax in (e.ABS_Z, e.ABS_BRAKE) for ax in triggers):
            buttons.discard(e.BTN_TL2)
        if any(ax in (e.ABS_RZ, e.ABS_GAS) for ax in triggers):
            buttons.discard(e.BTN_TR2)

        # Buscar si algún nodo de touchpad bloqueado pertenece a este mando y falta
        unreadable = []
        if e.BTN_LEFT not in buttons:
            for bn in blocked_nodes:
                if any(marker in bn["name"] for marker in SENSOR_NAME_MARKERS):
                    continue
                if (group["uniq"] and bn["uniq"] == group["uniq"]) or (
                    group.get("parent") and bn["parent"] == group["parent"]
                ):
                    unreadable.append(f"{bn['name']} ({bn['path']})")

        controllers.append(
            Controller(
                name=group["name"],
                uniq=group["uniq"],
                paths=group["paths"],
                touchpad_paths=group.get("touchpad_paths", []),
                buttons=sorted(buttons),
                axes=axes,
                axis_info=group["axis_info"],
                axis_types=axis_types,
                unreadable_nodes=unreadable,
            )
        )
    return controllers
