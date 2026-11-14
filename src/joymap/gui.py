import os
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from evdev import ecodes as e

from . import config, devices, windowwatch
from .mapping import (
    Assignment,
    AxisMapping,
    ButtonMapping,
    DEFAULT_DEADZONE,
    HAT_AXES,
    MappingEngine,
    MODE_NORMAL,
    MODE_REPEAT,
    MODE_ROTATE,
    Profile,
    axis_direction,
)
from .output import VirtualOutput

MODES = [
    (MODE_NORMAL, "Normal (pulsación o combinación)"),
    (MODE_ROTATE, "Rotar asignaciones en cada pulsación"),
]

KEYVAL_FALLBACK = {
    Gdk.KEY_space: e.KEY_SPACE,
    Gdk.KEY_Return: e.KEY_ENTER,
    Gdk.KEY_KP_Enter: e.KEY_ENTER,
    Gdk.KEY_Escape: e.KEY_ESC,
    Gdk.KEY_BackSpace: e.KEY_BACKSPACE,
    Gdk.KEY_Tab: e.KEY_TAB,
    Gdk.KEY_Left: e.KEY_LEFT,
    Gdk.KEY_Right: e.KEY_RIGHT,
    Gdk.KEY_Up: e.KEY_UP,
    Gdk.KEY_Down: e.KEY_DOWN,
    Gdk.KEY_Home: e.KEY_HOME,
    Gdk.KEY_End: e.KEY_END,
    Gdk.KEY_Page_Up: e.KEY_PAGEUP,
    Gdk.KEY_Page_Down: e.KEY_PAGEDOWN,
    Gdk.KEY_Insert: e.KEY_INSERT,
    Gdk.KEY_Delete: e.KEY_DELETE,
    Gdk.KEY_Control_L: e.KEY_LEFTCTRL,
    Gdk.KEY_Control_R: e.KEY_RIGHTCTRL,
    Gdk.KEY_Shift_L: e.KEY_LEFTSHIFT,
    Gdk.KEY_Shift_R: e.KEY_RIGHTSHIFT,
    Gdk.KEY_Alt_L: e.KEY_LEFTALT,
    Gdk.KEY_Alt_R: e.KEY_RIGHTALT,
    Gdk.KEY_Super_L: e.KEY_LEFTMETA,
    Gdk.KEY_Super_R: e.KEY_RIGHTMETA,
}

HAT_LABELS = {
    (e.ABS_HAT0X, -1): "Izquierda",
    (e.ABS_HAT0X, 1): "Derecha",
    (e.ABS_HAT0Y, -1): "Arriba",
    (e.ABS_HAT0Y, 1): "Abajo",
    (e.ABS_HAT1X, -1): "POV2 Izquierda",
    (e.ABS_HAT1X, 1): "POV2 Derecha",
    (e.ABS_HAT1Y, -1): "POV2 Arriba",
    (e.ABS_HAT1Y, 1): "POV2 Abajo",
}

FRIENDLY_KEY_NAMES = {
    e.KEY_LEFTCTRL: "Ctrl",
    e.KEY_RIGHTCTRL: "Ctrl Der",
    e.KEY_LEFTSHIFT: "Shift",
    e.KEY_RIGHTSHIFT: "Shift Der",
    e.KEY_LEFTALT: "Alt",
    e.KEY_RIGHTALT: "AltGr",
    e.KEY_LEFTMETA: "Super / Win",
    e.KEY_RIGHTMETA: "Super Der",
    e.KEY_SPACE: "Espacio",
    e.KEY_ENTER: "Enter",
    e.KEY_KPENTER: "Enter Num",
    e.KEY_BACKSPACE: "Retroceso",
    e.KEY_TAB: "Tab",
    e.KEY_ESC: "Esc",
    e.KEY_CAPSLOCK: "Bloq Mayús",
    e.KEY_UP: "Flecha Arriba",
    e.KEY_DOWN: "Flecha Abajo",
    e.KEY_LEFT: "Flecha Izq",
    e.KEY_RIGHT: "Flecha Der",
    e.KEY_PAGEUP: "Re Pág",
    e.KEY_PAGEDOWN: "Av Pág",
    e.KEY_HOME: "Inicio",
    e.KEY_END: "Fin",
    e.KEY_INSERT: "Insert",
    e.KEY_DELETE: "Supr",
}


def keyval_to_evdev(keyval, hardware_keycode):
    code = hardware_keycode - 8
    if code in e.KEY:
        return code
    if hardware_keycode in e.KEY:
        return hardware_keycode
    if keyval in KEYVAL_FALLBACK:
        return KEYVAL_FALLBACK[keyval]
    if 0x41 <= keyval <= 0x5A:
        return e.ecodes.get(f"KEY_{chr(keyval)}")
    if 0x61 <= keyval <= 0x7A:
        return e.ecodes.get(f"KEY_{chr(keyval).upper()}")
    if 0x30 <= keyval <= 0x39:
        return e.ecodes.get(f"KEY_{chr(keyval)}")
    return None


def key_label(code):
    if code in FRIENDLY_KEY_NAMES:
        return FRIENDLY_KEY_NAMES[code]
    name = e.KEY.get(code)
    if name:
        if isinstance(name, list):
            name = name[0]
        return name.replace("KEY_", "")
    return f"{code}"


def target_label(target, available_codes=None):
    if target[0] == "btn":
        return devices.button_label(target[1])
    code, direction = target[1], target[2]
    return devices.axis_label(code, direction, available_codes)


ICONS_DIRS = [
    os.path.join(os.path.dirname(__file__), "icons"),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "icons")),
    "/usr/share/joymap/icons",
    "/usr/local/share/joymap/icons",
    os.path.expanduser("~/.local/share/joymap/icons"),
]


def get_icon_path(filename):
    for d in ICONS_DIRS:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None


TARGET_ICONS = {
    e.BTN_SOUTH: "x.svg",
    e.BTN_EAST: "circle.svg",
    e.BTN_NORTH: "triangle.svg",
    e.BTN_WEST: "square.svg",
    e.BTN_TL: "l1.svg",
    e.BTN_TR: "r1.svg",
    e.BTN_TL2: "lt.svg",
    e.BTN_TR2: "rt.svg",
    e.BTN_SELECT: "share.svg",
    e.BTN_START: "options.svg",
    e.BTN_MODE: "home.svg",
    e.BTN_THUMBL: "l3.svg",
    e.BTN_THUMBR: "r3.svg",
    e.BTN_LEFT: "trackpadclic.svg",
    e.BTN_DPAD_UP: "cross-piece-up.svg",
    e.BTN_DPAD_DOWN: "cross-piece-down.svg",
    e.BTN_DPAD_LEFT: "cross-piece-left.svg",
    e.BTN_DPAD_RIGHT: "cross-piece-right.svg",
}


def get_target_icon_path(target, controller=None):
    if target[0] == "btn":
        code = target[1]
        filename = TARGET_ICONS.get(code)
        if filename:
            if filename == "r1.svg":
                p = get_icon_path("r1.svg") or get_icon_path("l2.svg")
                if p:
                    return p
            p = get_icon_path(filename)
            if p:
                return p
            if "cross-piece" in filename:
                return get_icon_path("cross-piece.svg")
        return None

    code, direction = target[1], target[2]
    axes = controller.axes if controller else []
    axis_types = controller.axis_types if controller else {}

    # Ejes D-Pad (Hats)
    if code in (e.ABS_HAT0X, e.ABS_HAT1X):
        fn = "cross-piece-left.svg" if direction < 0 else "cross-piece-right.svg"
        return get_icon_path(fn) or get_icon_path("cross-piece.svg")
    if code in (e.ABS_HAT0Y, e.ABS_HAT1Y):
        fn = "cross-piece-up.svg" if direction < 0 else "cross-piece-down.svg"
        return get_icon_path(fn) or get_icon_path("cross-piece.svg")

    if code in HAT_AXES or axis_types.get(code) == "hat":
        return get_icon_path("cross-piece.svg")

    # Ejes Stick 1 (Stick Izquierdo)
    if code == e.ABS_X:
        fn = "joypad1l.svg" if direction < 0 else "joypad1r.svg"
        return get_icon_path(fn) or get_icon_path("joypad1.svg")
    if code == e.ABS_Y:
        fn = "joypad1up.svg" if direction < 0 else "joypad1down.svg"
        return get_icon_path(fn) or get_icon_path("joypad1.svg")

    # Ejes Stick 2 (Stick Derecho)
    has_rx_ry = (e.ABS_RX in axes) or (e.ABS_RY in axes)
    if has_rx_ry or code in (e.ABS_RX, e.ABS_RY):
        if code == e.ABS_RX:
            fn = "joypad2l.svg" if direction < 0 else "joypad2r.svg"
            return get_icon_path(fn) or get_icon_path("joypad2.svg")
        if code == e.ABS_RY:
            fn = "joypad2up.svg" if direction < 0 else "joypad2down.svg"
            return get_icon_path(fn) or get_icon_path("joypad2.svg")
    else:
        if code == e.ABS_Z and axis_types.get(code) == "stick":
            fn = "joypad2l.svg" if direction < 0 else "joypad2r.svg"
            return get_icon_path(fn) or get_icon_path("joypad2.svg")
        if code == e.ABS_RZ and axis_types.get(code) == "stick":
            fn = "joypad2up.svg" if direction < 0 else "joypad2down.svg"
            return get_icon_path(fn) or get_icon_path("joypad2.svg")

    if code in (e.ABS_Z, e.ABS_BRAKE) or (axis_types.get(code) == "trigger" and code == e.ABS_Z):
        return get_icon_path("lt.svg") or get_icon_path("l2.svg")
    if code in (e.ABS_RZ, e.ABS_GAS) or (axis_types.get(code) == "trigger" and code == e.ABS_RZ):
        return get_icon_path("rt.svg") or get_icon_path("r2.svg")

    return None


class CaptureDialog(Adw.Window):
    def __init__(self, parent, multiple=True, initial_keys=None, on_done=None):
        super().__init__(
            title="Capturar combinación de teclas",
            transient_for=parent,
            modal=True,
            default_width=440,
            default_height=260,
        )
        self.captured = list(initial_keys or [])
        self.multiple = multiple
        self.on_done = on_done

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)

        cancel_btn = Gtk.Button(label="Cancelar")
        cancel_btn.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_btn)

        save_btn = Gtk.Button(label="Aceptar")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_accept)
        header.pack_end(save_btn)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)

        hint = Gtk.Label(
            label="Pulsa en tu teclado la tecla o combinación deseada (ej: <b>Ctrl + Q</b>):",
            use_markup=True,
            xalign=0.5,
        )
        content.append(hint)

        self.keys_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.keys_box.set_halign(Gtk.Align.CENTER)
        self.keys_box.set_valign(Gtk.Align.CENTER)
        content.append(self.keys_box)

        clear_btn = Gtk.Button(label="Limpiar")
        clear_btn.set_halign(Gtk.Align.CENTER)
        clear_btn.connect("clicked", self._on_clear)
        content.append(clear_btn)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(header)
        main_box.append(content)
        self.set_content(main_box)

        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        self._update_display()

    def _update_display(self):
        while (child := self.keys_box.get_first_child()) is not None:
            self.keys_box.remove(child)

        if not self.captured:
            lbl = Gtk.Label(label="Esperando pulsación de tecla...")
            lbl.add_css_class("dim-label")
            self.keys_box.append(lbl)
        else:
            for idx, c in enumerate(self.captured):
                if idx > 0:
                    plus = Gtk.Label(label="+")
                    plus.add_css_class("dim-label")
                    self.keys_box.append(plus)
                badge = Gtk.Label(label=key_label(c))
                badge.add_css_class("joymap-key-badge")
                self.keys_box.append(badge)

    def _on_clear(self, _btn):
        self.captured.clear()
        self._update_display()

    def _on_key_pressed(self, _controller, keyval, keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        code = keyval_to_evdev(keyval, keycode)
        if code is None:
            return True
        if not self.multiple:
            self.captured = [code]
        elif code not in self.captured:
            self.captured.append(code)
        self._update_display()
        return True

    def _on_accept(self, _btn):
        if self.on_done:
            self.on_done(list(self.captured))
        self.close()


class RulesDialog(Adw.Window):
    def __init__(self, parent, profile_names, current_rules, on_save_rules=None):
        super().__init__(
            title="Reglas por programa",
            transient_for=parent,
            modal=True,
            default_width=620,
            default_height=560,
        )
        self.rules = [dict(r) for r in current_rules]
        self.profile_names = list(profile_names) or ["default"]
        self.on_save_rules = on_save_rules
        self._rule_rows = []

        header = Adw.HeaderBar()
        close_btn = Gtk.Button(label="Listo")
        close_btn.add_css_class("suggested-action")
        close_btn.connect("clicked", self._on_close)
        header.pack_end(close_btn)

        clamp = Adw.Clamp(maximum_size=580)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        clamp.set_child(box)

        self.rules_group = Adw.PreferencesGroup(
            title="Reglas activas",
            description="Joymap activará automáticamente el perfil asociado cuando la ventana o juego esté en primer plano.",
        )
        box.append(self.rules_group)

        new_group = Adw.PreferencesGroup(title="Añadir nueva regla")

        self.match_row = Adw.EntryRow(title="Ventana o clase (ej: retroarch, celeste, steam)")
        new_group.add(self.match_row)

        detect_row = Adw.ActionRow(title="Detección de ventana")
        detect_row.set_subtitle("Detecta automáticamente el nombre de la ventana en primer plano")
        self.detect_btn = Gtk.Button(label="🔍 Detectar en 2s")
        self.detect_btn.set_valign(Gtk.Align.CENTER)
        self.detect_btn.connect("clicked", self._on_detect_clicked)
        detect_row.add_suffix(self.detect_btn)
        new_group.add(detect_row)

        self.detect_info_lbl = Gtk.Label(xalign=0)
        self.detect_info_lbl.set_margin_start(12)
        new_group.add(self.detect_info_lbl)

        self.profile_combo = Adw.ComboRow(title="Activar perfil")
        self.profile_model = Gtk.StringList.new(self.profile_names)
        self.profile_combo.set_model(self.profile_model)
        new_group.add(self.profile_combo)

        add_row = Adw.ActionRow()
        add_btn = Gtk.Button(label="➕ Añadir a la lista")
        add_btn.add_css_class("suggested-action")
        add_btn.set_valign(Gtk.Align.CENTER)
        add_btn.connect("clicked", self._on_add_rule)
        add_row.add_suffix(add_btn)
        new_group.add(add_row)

        box.append(new_group)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(clamp)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(header)
        main_box.append(scrolled)
        self.set_content(main_box)

        self._refresh_rules()

    def _refresh_rules(self):
        for r in self._rule_rows:
            self.rules_group.remove(r)
        self._rule_rows.clear()

        if not self.rules:
            empty_row = Adw.ActionRow(title="No hay reglas configuradas")
            empty_row.set_subtitle("Añade una regla abajo para asociar programas a perfiles.")
            self.rules_group.add(empty_row)
            self._rule_rows.append(empty_row)
            return

        for idx, rule in enumerate(self.rules):
            row = Adw.ActionRow(
                title=rule.get("match", ""),
                subtitle=f"Activa perfil: {rule.get('profile', '')}",
            )
            del_btn = Gtk.Button(icon_name="user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("destructive-action")
            del_btn.set_tooltip_text("Eliminar regla")
            del_btn.connect("clicked", self._on_delete_rule, idx)
            row.add_suffix(del_btn)
            self.rules_group.add(row)
            self._rule_rows.append(row)

    def _on_add_rule(self, _btn):
        match_text = self.match_row.get_text().strip()
        idx = self.profile_combo.get_selected()
        prof = self.profile_names[idx] if 0 <= idx < len(self.profile_names) else ""
        if not match_text or not prof:
            return
        self.rules.append({"match": match_text, "profile": prof})
        self.match_row.set_text("")
        self._refresh_rules()

    def _on_delete_rule(self, _btn, idx):
        if 0 <= idx < len(self.rules):
            del self.rules[idx]
            self._refresh_rules()

    def _on_detect_clicked(self, _btn):
        self.detect_btn.set_sensitive(False)
        self.detect_btn.set_label("⏳ Cambia a la ventana...")
        self.detect_info_lbl.set_markup(
            "<small><i>Haz clic en el juego o programa (detectando en 2 segundos)...</i></small>"
        )
        GLib.timeout_add(2000, self._do_detect)

    def _do_detect(self):
        self.detect_btn.set_sensitive(True)
        self.detect_btn.set_label("🔍 Detectar en 2s")
        info = windowwatch.active_window()
        if not info:
            self.detect_info_lbl.set_markup(
                "<small><span foreground='#e74c3c'>No se pudo detectar la ventana activa.</span></small>"
            )
            return False
        cls = info.get("class", "").strip()
        title = info.get("title", "").strip()
        chosen = cls or title
        if chosen:
            self.match_row.set_text(chosen.lower())
            self.detect_info_lbl.set_markup(
                f"<small>Detectado: <b>{chosen}</b></small>"
            )
        else:
            self.detect_info_lbl.set_markup(
                "<small><i>No se detectó el nombre de la ventana.</i></small>"
            )
        return False

    def _on_close(self, _btn):
        if self.on_save_rules:
            self.on_save_rules(self.rules)
        self.close()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="joymap")
        self.set_default_size(1120, 680)
        self.set_icon_name("joymap")

        self._updating_profiles_list = False
        self.switcher = None
        self._auto_switch_enabled = True
        self._isolate_touchpad_enabled = True

        saved_names = config.get_profile_names()
        if "default" in saved_names:
            self.profile = config.load_profile_by_name("default")
        elif saved_names:
            self.profile = config.load_profile_by_name(saved_names[0])
        else:
            self.profile = Profile(name="default")
        self._saved_profile_dict = self.profile.to_dict()

        self.controllers = devices.list_controllers()
        self.current_controller = self.controllers[0] if self.controllers else None
        self.engine = None
        self.output = None
        self.reader_stop = None
        self.current_target = None
        self._grabbed_devices = []
        self._row_by_button = {}
        self._row_by_axis = {}
        self._assignment_rows = []

        self._setup_css()

        # Layout Principal
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(root_box)
        self.set_content(self.toast_overlay)

        # HeaderBar Adwaita
        self.header_bar = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title="joymap", subtitle=self._device_subtitle())
        self.header_bar.set_title_widget(self.window_title)

        # Botones Izquierda de HeaderBar
        rules_btn = Gtk.Button(label="Reglas")
        rules_btn.set_icon_name("preferences-system-symbolic")
        rules_btn.set_tooltip_text("Reglas de cambio automático por programa / juego")
        rules_btn.connect("clicked", self.on_rules)
        self.header_bar.pack_start(rules_btn)

        import_btn = Gtk.Button(label="Importar")
        import_btn.set_icon_name("document-open-symbolic")
        import_btn.set_tooltip_text("Importar perfil de JoyToKey (.cfg)")
        import_btn.connect("clicked", self.on_import)
        self.header_bar.pack_start(import_btn)

        self.refresh_btn = Gtk.Button(label="Detectar mando")
        self.refresh_btn.set_icon_name("view-refresh-symbolic")
        self.refresh_btn.set_tooltip_text("Buscar y refrescar mandos conectados")
        self.refresh_btn.connect("clicked", self.on_refresh_controllers)
        self.header_bar.pack_start(self.refresh_btn)

        # Botones Derecha de HeaderBar
        self.status_pill = Gtk.Label(label="INACTIVO")
        self.status_pill.add_css_class("joymap-status-pill")
        self.status_pill.add_css_class("joymap-status-inactive")
        self.status_pill.set_valign(Gtk.Align.CENTER)
        self.header_bar.pack_end(self.status_pill)

        self.mapping_switch = Gtk.Switch()
        self.mapping_switch.set_valign(Gtk.Align.CENTER)
        self.mapping_switch.set_tooltip_text("Activa o detiene el envío de teclas a los programas")
        self.mapping_switch.connect("notify::active", self.on_switch_toggled)
        self.header_bar.pack_end(self.mapping_switch)

        # Menú desplegable de opciones (Popover)
        menu_popover = Gtk.Popover()
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        menu_box.set_margin_top(8)
        menu_box.set_margin_bottom(8)
        menu_box.set_margin_start(8)
        menu_box.set_margin_end(8)

        opts_group = Adw.PreferencesGroup(title="Opciones")

        self.auto_switch_row = Adw.SwitchRow(title="Auto-cambio por programa")
        self.auto_switch_row.set_subtitle("Cambia de perfil según la ventana activa")
        self.auto_switch_row.set_active(self._auto_switch_enabled)
        self.auto_switch_row.connect("notify::active", self.on_auto_switch_toggled)
        opts_group.add(self.auto_switch_row)

        self.isolate_tp_row = Adw.SwitchRow(title="Aislar touchpad")
        self.isolate_tp_row.set_subtitle("Bloquea clics accidentales de KDE durante el mapeo")
        self.isolate_tp_row.set_active(self._isolate_touchpad_enabled)
        self.isolate_tp_row.connect("notify::active", self.on_isolate_touchpad_toggled)
        opts_group.add(self.isolate_tp_row)

        menu_box.append(opts_group)

        about_btn = Gtk.Button(label="Acerca de Joymap")
        about_btn.connect("clicked", self.on_about)
        menu_box.append(about_btn)

        menu_popover.set_child(menu_box)

        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", popover=menu_popover)
        menu_btn.set_tooltip_text("Opciones adicionales")
        self.header_bar.pack_end(menu_btn)

        root_box.append(self.header_bar)

        # ----------------------------------------------------
        # Estructura Paned de 3 Columnas
        # 1. Perfiles (Izquierda)
        # 2. Botones y Ejes (Centro)
        # 3. Editor de Mapeo (Derecha)
        # ----------------------------------------------------
        paned1 = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned1.set_shrink_start_child(False)
        paned1.set_shrink_end_child(False)
        paned1.set_position(230)
        root_box.append(paned1)

        # ----------------------------------------------------
        # COLUMNA 1: Perfiles
        # ----------------------------------------------------
        col1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        col1.set_size_request(210, -1)
        col1.set_margin_top(10)
        col1.set_margin_bottom(10)
        col1.set_margin_start(10)
        col1.set_margin_end(6)

        c1_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        c1_title = Gtk.Label(label="<b>Perfiles</b>", use_markup=True, xalign=0)
        c1_header.append(c1_title)

        add_prof_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_prof_btn.add_css_class("flat")
        add_prof_btn.set_tooltip_text("Crear nuevo perfil")
        add_prof_btn.set_valign(Gtk.Align.CENTER)
        add_prof_btn.connect("clicked", self.on_new_profile)
        c1_header.append(add_prof_btn)
        col1.append(c1_header)

        prof_scroll = Gtk.ScrolledWindow()
        prof_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        prof_scroll.set_vexpand(True)
        self.profiles_listbox = Gtk.ListBox()
        self.profiles_listbox.add_css_class("navigation-sidebar")
        self.profiles_listbox.connect("row-selected", self.on_select_profile_row)
        prof_scroll.set_child(self.profiles_listbox)
        col1.append(prof_scroll)

        # Indicador visual de cambios sin guardar
        self.unsaved_badge = Gtk.Label(xalign=0.5)
        self.unsaved_badge.set_margin_top(4)
        self.unsaved_badge.set_margin_bottom(2)
        self.unsaved_badge.set_markup("<small><span foreground='#e5a50a'><b>● Cambios sin guardar</b></span></small>")
        self.unsaved_badge.set_visible(False)
        col1.append(self.unsaved_badge)

        # Fila 1: Confirmar Guardado y Descartar / Cancelar
        save_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        save_box.set_homogeneous(True)

        self.save_btn = Gtk.Button(label="Guardar")
        self.save_btn.set_icon_name("document-save-symbolic")
        self.save_btn.set_tooltip_text("Confirmar y guardar cambios del perfil")
        self.save_btn.connect("clicked", self.on_save)
        save_box.append(self.save_btn)

        self.discard_btn = Gtk.Button(label="Descartar")
        self.discard_btn.set_icon_name("edit-undo-symbolic")
        self.discard_btn.set_tooltip_text("Cancelar las modificaciones no guardadas")
        self.discard_btn.set_sensitive(False)
        self.discard_btn.connect("clicked", self.on_discard)
        save_box.append(self.discard_btn)

        col1.append(save_box)

        # Fila 2: Copiar perfil y Borrar perfil
        manage_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        manage_box.set_homogeneous(True)

        copy_btn = Gtk.Button(label="Copiar")
        copy_btn.set_icon_name("edit-copy-symbolic")
        copy_btn.set_tooltip_text("Guardar una copia con otro nombre")
        copy_btn.connect("clicked", self.on_save_as)
        manage_box.append(copy_btn)

        del_btn = Gtk.Button(label="Borrar")
        del_btn.set_icon_name("user-trash-symbolic")
        del_btn.add_css_class("destructive-action")
        del_btn.set_tooltip_text("Eliminar el perfil seleccionado")
        del_btn.connect("clicked", self.on_delete_profile)
        manage_box.append(del_btn)

        col1.append(manage_box)

        paned1.set_start_child(col1)

        # Divisor Secundario: Columna 2 y Columna 3
        paned2 = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned2.set_shrink_start_child(False)
        paned2.set_shrink_end_child(False)
        paned2.set_position(360)
        paned1.set_end_child(paned2)

        # ----------------------------------------------------
        # COLUMNA 2: Entradas del Mando (Botones y Ejes)
        # ----------------------------------------------------
        col2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        col2.set_size_request(320, -1)
        col2.set_margin_top(10)
        col2.set_margin_bottom(10)
        col2.set_margin_start(6)
        col2.set_margin_end(6)

        c2_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        c2_title = Gtk.Label(label="<b>Entradas del Mando</b>", use_markup=True, xalign=0, hexpand=True)
        c2_header.append(c2_title)

        c2_refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        c2_refresh_btn.add_css_class("flat")
        c2_refresh_btn.set_tooltip_text("Buscar y refrescar mandos conectados")
        c2_refresh_btn.set_valign(Gtk.Align.CENTER)
        c2_refresh_btn.connect("clicked", self.on_refresh_controllers)
        c2_header.append(c2_refresh_btn)
        col2.append(c2_header)

        inputs_scroll = Gtk.ScrolledWindow()
        inputs_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        inputs_scroll.set_vexpand(True)
        self.listbox = Gtk.ListBox()
        self.listbox.add_css_class("boxed-list")
        self.listbox.connect("row-selected", self.on_select_target)
        inputs_scroll.set_child(self.listbox)
        col2.append(inputs_scroll)

        paned2.set_start_child(col2)

        # ----------------------------------------------------
        # COLUMNA 3: Editor de Mapeo
        # ----------------------------------------------------
        col3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        col3.set_size_request(380, -1)
        col3.set_margin_top(10)
        col3.set_margin_bottom(10)
        col3.set_margin_start(6)
        col3.set_margin_end(10)

        c3_title = Gtk.Label(label="<b>Ajustes de Mapeo</b>", use_markup=True, xalign=0)
        col3.append(c3_title)

        editor_scroll = Gtk.ScrolledWindow()
        editor_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        editor_scroll.set_vexpand(True)

        clamp = Adw.Clamp(maximum_size=520)
        self.editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.editor_box.set_margin_bottom(16)
        clamp.set_child(self.editor_box)
        editor_scroll.set_child(clamp)

        col3.append(editor_scroll)
        paned2.set_end_child(col3)

        self._refresh_profiles_list()
        self._populate()
        self._build_editor()
        self._start_monitor()
        self._saved_profile_dict = self.profile.to_dict()
        self._update_dirty_ui()

        self.connect("close-request", self.on_close_request)

    def on_close_request(self, _window):
        if self.has_unsaved_changes():
            dialog = Adw.AlertDialog(
                heading="Cambios sin guardar",
                body=f"Tienes modificaciones sin guardar en el perfil '{self.profile.name}'. ¿Deseas guardarlas antes de salir?",
            )
            dialog.add_response("cancel", "Cancelar")
            dialog.add_response("discard", "Salir sin guardar")
            dialog.add_response("save", "Guardar y salir")
            dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("save")
            dialog.set_close_response("cancel")

            def on_resp(_dlg, resp):
                if resp == "save":
                    self._do_save_profile()
                    self._do_close()
                elif resp == "discard":
                    self._do_close()

            dialog.connect("response", on_resp)
            dialog.present(self)
            return True

        self._do_close()
        return False

    def _do_close(self):
        self._stop_listen()
        self._stop_monitor()
        self.destroy()

    def _setup_css(self):
        css = """
        .joymap-pressed {
            background-color: alpha(@accent_bg_color, 0.40);
            border-color: @accent_bg_color;
            color: @accent_fg_color;
        }

        .joymap-key-badge {
            background-color: @card_bg_color;
            border: 1px solid @card_border_color;
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: bold;
            font-size: 1.15em;
        }

        .joymap-badge {
            background-color: alpha(@accent_bg_color, 0.16);
            color: @accent_color;
            border-radius: 10px;
            padding: 2px 8px;
            font-size: 0.85em;
            font-weight: bold;
        }

        .joymap-btn-icon {
            -gtk-icon-shadow: 0 2px 5px rgba(0, 0, 0, 0.40);
            filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.35));
            margin-right: 6px;
        }

        .joymap-btn-icon-large {
            -gtk-icon-shadow: 0 3px 8px rgba(0, 0, 0, 0.45);
            filter: drop-shadow(0 3px 6px rgba(0, 0, 0, 0.40));
            margin-right: 6px;
        }

        .joymap-pressed .joymap-btn-icon {
            -gtk-icon-shadow: 0 0 10px @accent_bg_color;
            filter: drop-shadow(0 0 8px @accent_bg_color);
        }

        .joymap-status-pill {
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 0.8em;
            margin-right: 6px;
        }

        .joymap-status-active {
            background-color: alpha(#2ecc71, 0.2);
            color: #27ae60;
            border: 1px solid alpha(#2ecc71, 0.4);
        }

        .joymap-status-inactive {
            background-color: alpha(#888888, 0.15);
            color: #888888;
            border: 1px solid alpha(#888888, 0.3);
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _device_subtitle(self):
        if self.current_controller is None:
            return "Sin mandos detectados"
        text = f"{self.current_controller.name} ({self.current_controller.path})"
        touchpads = [n for n in self.current_controller.unreadable_nodes if "touchpad" in n.lower()]
        if touchpads:
            text += "  ⚠️ (Touchpad sin permisos uaccess)"
        return text

    def _populate(self):
        while (child := self.listbox.get_first_child()) is not None:
            self.listbox.remove(child)
        self._row_by_button.clear()
        self._row_by_axis.clear()

        if self.current_controller is None:
            empty_row = Adw.ActionRow(
                title="Sin mandos conectados",
                subtitle="Conecta tu mando y pulsa 'Detectar mando'",
            )
            empty_icon = Gtk.Image.new_from_icon_name("input-gaming-symbolic")
            empty_icon.set_pixel_size(24)
            empty_row.add_prefix(empty_icon)
            empty_row.set_activatable(False)
            empty_row.set_selectable(False)
            self.listbox.append(empty_row)
            return

        axes = self.current_controller.axes
        buttons = self.current_controller.buttons
        axis_types = self.current_controller.axis_types
        added = set()

        def add_target(target, group):
            if target in added:
                return
            added.add(target)
            self._add_row(target, group)

        # ----------------------------------------------------
        # 1. Cruceta / D-Pad (todos los botones/ejes de cruceta al principio)
        # ----------------------------------------------------
        for hat_ax in [e.ABS_HAT0Y, e.ABS_HAT0X, e.ABS_HAT1Y, e.ABS_HAT1X]:
            if hat_ax in axes:
                add_target(("axis", hat_ax, -1), "Cruceta")
                add_target(("axis", hat_ax, 1), "Cruceta")

        dpad_axes = [
            ax for ax in axes
            if axis_types.get(ax) == "hat" and ax not in (e.ABS_HAT0X, e.ABS_HAT0Y, e.ABS_HAT1X, e.ABS_HAT1Y)
        ]
        for hat_ax in dpad_axes:
            add_target(("axis", hat_ax, -1), "Cruceta")
            add_target(("axis", hat_ax, 1), "Cruceta")

        for dpad_btn in [e.BTN_DPAD_UP, e.BTN_DPAD_DOWN, e.BTN_DPAD_LEFT, e.BTN_DPAD_RIGHT]:
            if dpad_btn in buttons:
                add_target(("btn", dpad_btn), "Cruceta")

        # ----------------------------------------------------
        # 2. Stick Izquierdo
        # ----------------------------------------------------
        if e.ABS_X in axes:
            add_target(("axis", e.ABS_X, -1), "Stick Izquierdo")
            add_target(("axis", e.ABS_X, 1), "Stick Izquierdo")
        if e.ABS_Y in axes:
            add_target(("axis", e.ABS_Y, -1), "Stick Izquierdo")
            add_target(("axis", e.ABS_Y, 1), "Stick Izquierdo")

        # ----------------------------------------------------
        # 3. L3 y R3 debajo de stick izq abajo
        # ----------------------------------------------------
        if e.BTN_THUMBL in buttons:
            add_target(("btn", e.BTN_THUMBL), "Sticks (Clic)")
        if e.BTN_THUMBR in buttons:
            add_target(("btn", e.BTN_THUMBR), "Sticks (Clic)")

        # ----------------------------------------------------
        # 4. Stick Derecho
        # ----------------------------------------------------
        has_rx_ry = (e.ABS_RX in axes) or (e.ABS_RY in axes)
        if has_rx_ry:
            if e.ABS_RX in axes:
                add_target(("axis", e.ABS_RX, -1), "Stick Derecho")
                add_target(("axis", e.ABS_RX, 1), "Stick Derecho")
            if e.ABS_RY in axes:
                add_target(("axis", e.ABS_RY, -1), "Stick Derecho")
                add_target(("axis", e.ABS_RY, 1), "Stick Derecho")
        else:
            if e.ABS_Z in axes and axis_types.get(e.ABS_Z) == "stick":
                add_target(("axis", e.ABS_Z, -1), "Stick Derecho")
                add_target(("axis", e.ABS_Z, 1), "Stick Derecho")
            if e.ABS_RZ in axes and axis_types.get(e.ABS_RZ) == "stick":
                add_target(("axis", e.ABS_RZ, -1), "Stick Derecho")
                add_target(("axis", e.ABS_RZ, 1), "Stick Derecho")

        # ----------------------------------------------------
        # 5. Botones de acción (Face buttons)
        # ----------------------------------------------------
        for btn in [e.BTN_WEST, e.BTN_NORTH, e.BTN_SOUTH, e.BTN_EAST]:
            if btn in buttons:
                add_target(("btn", btn), "Botones")

        # ----------------------------------------------------
        # 6. Bumpers y Gatillos (gatillos debajo de r1)
        # ----------------------------------------------------
        if e.BTN_TL in buttons:
            add_target(("btn", e.BTN_TL), "Bumpers")
        if e.BTN_TR in buttons:
            add_target(("btn", e.BTN_TR), "Bumpers")

        # Gatillo L2
        if e.ABS_Z in axes and axis_types.get(e.ABS_Z) == "trigger":
            add_target(("axis", e.ABS_Z, 1), "Gatillos")
        elif e.ABS_BRAKE in axes:
            add_target(("axis", e.ABS_BRAKE, 1), "Gatillos")
        if e.BTN_TL2 in buttons:
            add_target(("btn", e.BTN_TL2), "Gatillos")

        # Gatillo R2
        if e.ABS_RZ in axes and axis_types.get(e.ABS_RZ) == "trigger":
            add_target(("axis", e.ABS_RZ, 1), "Gatillos")
        elif e.ABS_GAS in axes:
            add_target(("axis", e.ABS_GAS, 1), "Gatillos")
        if e.BTN_TR2 in buttons:
            add_target(("btn", e.BTN_TR2), "Gatillos")

        # Otros gatillos analógicos
        trigger_axes = [ax for ax in axes if axis_types.get(ax) == "trigger"]
        for code in trigger_axes:
            add_target(("axis", code, 1), "Gatillos")

        # ----------------------------------------------------
        # 7. Sistema y Touchpad
        # ----------------------------------------------------
        for btn in [e.BTN_SELECT, e.BTN_START, e.BTN_MODE, e.BTN_LEFT]:
            if btn in buttons:
                add_target(("btn", btn), "Sistema")

        # ----------------------------------------------------
        # 8. Ejes y botones adicionales restantes
        # ----------------------------------------------------
        for code in axes:
            if ("axis", code, -1) not in added and ("axis", code, 1) not in added:
                add_target(("axis", code, -1), "Otros Ejes")
                add_target(("axis", code, 1), "Otros Ejes")

        for code in buttons:
            if ("btn", code) not in added:
                add_target(("btn", code), "Otros Botones")

        # Seleccionar la fila activa previa o la primera
        selected_row = None
        if self.current_target:
            if self.current_target[0] == "btn":
                selected_row = self._row_by_button.get(self.current_target[1])
            else:
                selected_row = self._row_by_axis.get((self.current_target[1], self.current_target[2]))

        if selected_row is not None:
            self.listbox.select_row(selected_row)
        else:
            first = self.listbox.get_row_at_index(0)
            if first is not None:
                self.listbox.select_row(first)

    def _add_row(self, target, group):
        row = Adw.ActionRow()
        available = self.current_controller.axes if self.current_controller else None
        lbl_text = target_label(target, available)
        row.set_title(lbl_text)
        row.set_subtitle(group)

        # Icono SVG personalizado con sombra
        icon_path = get_target_icon_path(target, self.current_controller)
        if icon_path:
            img = Gtk.Image.new_from_file(icon_path)
            img.set_pixel_size(32)
            img.add_css_class("joymap-btn-icon")
            img.set_valign(Gtk.Align.CENTER)
            row.add_prefix(img)

        summary = self._mapping_summary(target)
        badge = Gtk.Label(label=summary)
        badge.add_css_class("joymap-badge")
        badge.set_visible(bool(summary))
        badge.set_valign(Gtk.Align.CENTER)
        row.add_suffix(badge)

        row.target = target
        row.mapping_label = badge

        if target[0] == "btn":
            self._row_by_button[target[1]] = row
        else:
            self._row_by_axis[(target[1], target[2])] = row

        self.listbox.append(row)

    def _mapping_summary(self, target):
        mapping = self._mapping_for(target, create=False)
        if not mapping or not mapping.assignments:
            return ""
        if mapping.mode == MODE_ROTATE:
            steps = [" + ".join(key_label(k) for k in a.keys) for a in mapping.assignments]
            summary = " ➔ ".join(steps) if steps else ""
        else:
            summary = " + ".join(key_label(k) for k in mapping.assignments[0].keys)

        if mapping.auto_repeat:
            rate = max(1, round(1000.0 / max(mapping.interval_ms, 5)))
            summary += f"  [🔁 {rate}/s]"
        return summary

    def _update_row_label(self, target):
        row = (
            self._row_by_button.get(target[1])
            if target[0] == "btn"
            else self._row_by_axis.get((target[1], target[2]))
        )
        if row is not None and hasattr(row, "mapping_label"):
            sum_text = self._mapping_summary(target)
            row.mapping_label.set_text(sum_text)
            row.mapping_label.set_visible(bool(sum_text))
        if self.engine is not None:
            self.engine.set_profile(self.profile)

    def _mapping_for(self, target, create=True):
        if target[0] == "btn":
            code = target[1]
            if create:
                return self.profile.buttons.setdefault(code, ButtonMapping())
            return self.profile.buttons.get(code)
        code, direction = target[1], target[2]
        axis = self.profile.axes.get(code)
        if axis is None:
            if not create:
                return None
            axis = AxisMapping(deadzone=0.0 if code in HAT_AXES else DEFAULT_DEADZONE)
            self.profile.axes[code] = axis
        return axis.negative if direction < 0 else axis.positive

    def on_select_target(self, _lb, row):
        if row is None or not hasattr(row, "target"):
            return
        self.current_target = row.target
        self._build_editor()

    def _speed_desc(self, rate, ms):
        if rate == 1:
            return "1 pulsación/seg (cada 1000 ms)"
        elif rate <= 5:
            return f"{rate} pulsaciones/seg (lento - cada {ms} ms)"
        elif rate <= 15:
            return f"{rate} pulsaciones/seg (normal - cada {ms} ms)"
        elif rate <= 30:
            return f"{rate} pulsaciones/seg (rápido - cada {ms} ms)"
        else:
            return f"{rate} pulsaciones/seg (ultra rápido - cada {ms} ms)"

    def _build_editor(self):
        while (child := self.editor_box.get_first_child()) is not None:
            self.editor_box.remove(child)

        if self.current_controller is None:
            status_page = Adw.StatusPage(
                icon_name="input-gaming-symbolic",
                title="Sin mandos detectados",
                description="Conecta tu mando por USB o Bluetooth y pulsa 'Detectar mando'.",
            )
            refresh_page_btn = Gtk.Button(label="Detectar mando")
            refresh_page_btn.set_icon_name("view-refresh-symbolic")
            refresh_page_btn.add_css_class("pill")
            refresh_page_btn.add_css_class("suggested-action")
            refresh_page_btn.set_halign(Gtk.Align.CENTER)
            refresh_page_btn.connect("clicked", self.on_refresh_controllers)
            status_page.set_child(refresh_page_btn)
            self.editor_box.append(status_page)
            return

        target = self.current_target
        if target is None:
            status_page = Adw.StatusPage(
                icon_name="input-gaming-symbolic",
                title="Sin selección",
                description="Selecciona un botón o eje en la lista central para configurar sus opciones.",
            )
            self.editor_box.append(status_page)
            return

        available = self.current_controller.axes if self.current_controller else None
        target_name = target_label(target, available)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon_path = get_target_icon_path(target, self.current_controller)
        if icon_path:
            img = Gtk.Image.new_from_file(icon_path)
            img.set_pixel_size(44)
            img.add_css_class("joymap-btn-icon-large")
            img.set_valign(Gtk.Align.CENTER)
            header_box.append(img)

        header_lbl = Gtk.Label(label=f"<b>{target_name}</b>", use_markup=True, xalign=0)
        header_lbl.add_css_class("title-3")
        header_lbl.set_valign(Gtk.Align.CENTER)
        header_box.append(header_lbl)
        self.editor_box.append(header_box)

        mapping = self._mapping_for(target)
        if mapping.mode == MODE_REPEAT:
            mapping.mode = MODE_NORMAL
            mapping.auto_repeat = True

        # Grupo 1: General (Modo y Zona Muerta)
        gen_group = Adw.PreferencesGroup(title="Comportamiento")

        if target[0] == "axis":
            code = target[1]
            axis_map = self.profile.axes.setdefault(
                code, AxisMapping(deadzone=0.0 if code in HAT_AXES else DEFAULT_DEADZONE)
            )
            dz_row = Adw.SpinRow.new_with_range(0, 95, 1)
            dz_row.set_title("Zona muerta (%)")
            dz_row.set_subtitle("Ignora movimientos involuntarios pequeños del stick")
            dz_row.set_value(int(round(axis_map.deadzone * 100)))
            dz_row.connect("notify::value", self.on_deadzone_changed, code)
            gen_group.add(dz_row)

        mode_row = Adw.ComboRow(title="Modo de ejecución")
        mode_model = Gtk.StringList.new([label for _, label in MODES])
        mode_row.set_model(mode_model)
        mode_idx = 1 if mapping.mode == MODE_ROTATE else 0
        mode_row.set_selected(mode_idx)
        if mapping.mode == MODE_ROTATE:
            mode_row.set_subtitle("Avanza un paso de la secuencia con cada pulsación")
        else:
            mode_row.set_subtitle("Ejecuta la tecla o combinación asignada")
        mode_row.connect("notify::selected", self.on_mode_changed, target)
        gen_group.add(mode_row)

        self.editor_box.append(gen_group)

        # Grupo 2: Auto-repetición continua (Turbo)
        repeat_group = Adw.PreferencesGroup(title="Auto-repetición continua (Turbo)")

        repeat_sw = Adw.SwitchRow(title="Activar auto-repetición continua")
        repeat_sw.set_subtitle(
            "Al mantener pulsado, repite continuamente la asignación"
            if mapping.mode == MODE_NORMAL
            else "Al mantener pulsado, cicla repetidamente por los pasos de la rotación"
        )
        repeat_sw.set_active(mapping.auto_repeat)
        repeat_sw.connect("notify::active", self.on_auto_repeat_toggled, target)
        repeat_group.add(repeat_sw)

        delay_row = Adw.SpinRow.new_with_range(0.0, 5.0, 0.05)
        delay_row.set_title("Espera inicial antes de repetir (segundos)")
        delay_row.set_subtitle("0.0 s = repetir de inmediato al pulsar")
        delay_row.set_digits(2)
        delay_row.set_value(round(mapping.repeat_delay_ms / 1000.0, 2))
        delay_row.set_sensitive(mapping.auto_repeat)
        delay_row.connect("notify::value", self.on_delay_changed, target)
        repeat_group.add(delay_row)
        self._delay_row = delay_row

        current_rate = max(1, min(100, round(1000.0 / max(mapping.interval_ms, 5))))
        speed_row = Adw.SpinRow.new_with_range(1, 100, 1)
        speed_row.set_title("Velocidad de repetición (pulsaciones/seg)")
        speed_row.set_subtitle(self._speed_desc(current_rate, mapping.interval_ms))
        speed_row.set_value(current_rate)
        speed_row.set_sensitive(mapping.auto_repeat)
        speed_row.connect("notify::value", self.on_speed_changed, target)
        repeat_group.add(speed_row)
        self._speed_row = speed_row

        self.editor_box.append(repeat_group)

        # Grupo 3: Asignaciones / Pasos
        self._assignment_rows.clear()
        sec_title = (
            "Secuencia de pasos (rotación)"
            if mapping.mode == MODE_ROTATE
            else "Teclas asignadas"
        )
        self.assign_group = Adw.PreferencesGroup(title=sec_title)
        self.editor_box.append(self.assign_group)

        self._refresh_assignments_in_group(target)

        add_lbl = (
            "➕ Añadir paso a la rotación"
            if mapping.mode == MODE_ROTATE
            else "➕ Añadir tecla o combinación"
        )
        add_btn = Gtk.Button(label=add_lbl)
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self.on_add_assignment, target)
        self.editor_box.append(add_btn)

    def _refresh_assignments_in_group(self, target):
        for r in list(self._assignment_rows):
            try:
                self.assign_group.remove(r)
            except Exception:
                pass
        self._assignment_rows.clear()

        mapping = self._mapping_for(target, create=False)
        if not mapping or not mapping.assignments:
            empty_row = Adw.ActionRow(title="Sin teclas asignadas")
            empty_row.set_subtitle("Haz clic abajo para asignar una tecla o combinación.")
            self.assign_group.add(empty_row)
            self._assignment_rows.append(empty_row)
            self._update_row_label(target)
            return

        total = len(mapping.assignments)
        for idx, assignment in enumerate(mapping.assignments):
            keys_text = " + ".join(key_label(k) for k in assignment.keys) or "(vacía)"
            prefix = f"Paso {idx + 1}" if mapping.mode == MODE_ROTATE else f"Asignación {idx + 1}"

            row = Adw.ActionRow(title=keys_text, subtitle=prefix)

            if mapping.mode == MODE_ROTATE and total > 1:
                up_btn = Gtk.Button(icon_name="go-up-symbolic")
                up_btn.add_css_class("flat")
                up_btn.set_tooltip_text("Mover arriba en la secuencia")
                up_btn.set_sensitive(idx > 0)
                up_btn.connect("clicked", self.on_move_assignment, target, idx, -1)
                row.add_suffix(up_btn)

                down_btn = Gtk.Button(icon_name="go-down-symbolic")
                down_btn.add_css_class("flat")
                down_btn.set_tooltip_text("Mover abajo en la secuencia")
                down_btn.set_sensitive(idx < total - 1)
                down_btn.connect("clicked", self.on_move_assignment, target, idx, 1)
                row.add_suffix(down_btn)

            edit_btn = Gtk.Button(label="Cambiar")
            edit_btn.add_css_class("flat")
            edit_btn.connect("clicked", self.on_edit_assignment, target, idx)
            row.add_suffix(edit_btn)

            del_btn = Gtk.Button(icon_name="user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("destructive-action")
            del_btn.set_tooltip_text("Quitar asignación")
            del_btn.connect("clicked", self.on_remove_assignment, target, idx)
            row.add_suffix(del_btn)

            self.assign_group.add(row)
            self._assignment_rows.append(row)

        self._update_row_label(target)

    def on_deadzone_changed(self, spin, _pspec, code):
        axis_map = self.profile.axes.setdefault(code, AxisMapping())
        axis_map.deadzone = round(spin.get_value() / 100.0, 3)
        self._update_dirty_ui()

    def on_mode_changed(self, combo, _pspec, target):
        idx = combo.get_selected()
        if 0 <= idx < len(MODES):
            self._mapping_for(target).mode = MODES[idx][0]
            self._build_editor()
            self._update_row_label(target)
            self._update_dirty_ui()

    def on_auto_repeat_toggled(self, sw, _pspec, target):
        active = sw.get_active()
        self._mapping_for(target).auto_repeat = active
        if hasattr(self, "_delay_row"):
            self._delay_row.set_sensitive(active)
        if hasattr(self, "_speed_row"):
            self._speed_row.set_sensitive(active)
        self._update_row_label(target)
        self._update_dirty_ui()

    def on_delay_changed(self, spin, _pspec, target):
        self._mapping_for(target).repeat_delay_ms = int(round(spin.get_value() * 1000.0))
        self._update_row_label(target)
        self._update_dirty_ui()

    def on_speed_changed(self, spin, _pspec, target):
        rate = max(1, int(spin.get_value()))
        mapping = self._mapping_for(target)
        mapping.interval_ms = max(10, int(round(1000.0 / rate)))
        if hasattr(self, "_speed_row"):
            self._speed_row.set_subtitle(self._speed_desc(rate, mapping.interval_ms))
        self._update_row_label(target)
        self._update_dirty_ui()

    def on_move_assignment(self, _btn, target, idx, delta):
        mapping = self._mapping_for(target)
        new_idx = idx + delta
        if 0 <= new_idx < len(mapping.assignments):
            mapping.assignments[idx], mapping.assignments[new_idx] = (
                mapping.assignments[new_idx],
                mapping.assignments[idx],
            )
            self._refresh_assignments_in_group(target)
            self._update_dirty_ui()

    def on_add_assignment(self, _btn, target):
        def on_done(keys):
            if keys:
                self._mapping_for(target).assignments.append(Assignment(keys=keys))
                self._refresh_assignments_in_group(target)
                self._update_dirty_ui()

        dialog = CaptureDialog(self, multiple=True, on_done=on_done)
        dialog.present()

    def on_edit_assignment(self, _btn, target, idx):
        mapping = self._mapping_for(target)
        current_keys = mapping.assignments[idx].keys if 0 <= idx < len(mapping.assignments) else []

        def on_done(keys):
            if keys and 0 <= idx < len(mapping.assignments):
                mapping.assignments[idx] = Assignment(keys=keys)
                self._refresh_assignments_in_group(target)
                self._update_dirty_ui()

        dialog = CaptureDialog(self, multiple=True, initial_keys=current_keys, on_done=on_done)
        dialog.present()

    def on_remove_assignment(self, _btn, target, idx):
        mapping = self._mapping_for(target)
        if 0 <= idx < len(mapping.assignments):
            keys_label = " + ".join(key_label(k) for k in mapping.assignments[idx].keys) or "(vacía)"
            dialog = Adw.AlertDialog(
                heading="¿Quitar asignación?",
                body=f"¿Deseas quitar la asignación '{keys_label}'?",
            )
            dialog.add_response("cancel", "Cancelar")
            dialog.add_response("remove", "Quitar")
            dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_resp(_dlg, resp):
                if resp == "remove":
                    if 0 <= idx < len(mapping.assignments):
                        del mapping.assignments[idx]
                    self._refresh_assignments_in_group(target)
                    self._update_dirty_ui()

            dialog.connect("response", on_resp)
            dialog.present(self)

    def _refresh_profiles_list(self, select_name=None):
        target_name = select_name or self.profile.name
        self._updating_profiles_list = True

        while (child := self.profiles_listbox.get_first_child()) is not None:
            self.profiles_listbox.remove(child)

        names = config.get_profile_names()
        if not names:
            names = [self.profile.name]

        target_row = None
        for name in names:
            row = Adw.ActionRow(title=name)
            icon = Gtk.Image.new_from_icon_name("input-gaming-symbolic")
            row.add_prefix(icon)
            row.profile_name = name
            self.profiles_listbox.append(row)

            if name == target_name:
                target_row = row

        if target_row is not None:
            self.profiles_listbox.select_row(target_row)

        self._updating_profiles_list = False

    def has_unsaved_changes(self):
        if not hasattr(self, "_saved_profile_dict") or self._saved_profile_dict is None:
            return False
        return self.profile.to_dict() != self._saved_profile_dict

    def _update_dirty_ui(self):
        dirty = self.has_unsaved_changes()
        if hasattr(self, "discard_btn"):
            self.discard_btn.set_sensitive(dirty)
        if hasattr(self, "save_btn"):
            if dirty:
                self.save_btn.add_css_class("suggested-action")
            else:
                self.save_btn.remove_css_class("suggested-action")
        if hasattr(self, "unsaved_badge"):
            self.unsaved_badge.set_visible(dirty)

    def on_select_profile_row(self, _lb, row):
        if row is None or getattr(self, "_updating_profiles_list", False):
            return
        name = getattr(row, "profile_name", None)
        if not name or name == self.profile.name:
            return

        if self.has_unsaved_changes():
            dialog = Adw.AlertDialog(
                heading="Cambios sin guardar",
                body=f"Tienes cambios sin guardar en '{self.profile.name}'. ¿Deseas guardarlos antes de cambiar a '{name}'?",
            )
            dialog.add_response("cancel", "Cancelar")
            dialog.add_response("discard", "Descartar y cambiar")
            dialog.add_response("save", "Guardar y cambiar")
            dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("save")
            dialog.set_close_response("cancel")

            def on_resp(_dlg, resp):
                if resp == "save":
                    self._do_save_profile()
                    self._switch_to_profile(name)
                elif resp == "discard":
                    self._do_discard_changes()
                    self._switch_to_profile(name)
                else:
                    self._refresh_profiles_list(select_name=self.profile.name)

            dialog.connect("response", on_resp)
            dialog.present(self)
            return

        self._switch_to_profile(name)

    def _switch_to_profile(self, name):
        try:
            self.profile = config.load_profile_by_name(name)
            self._populate()
            self._build_editor()
            self._saved_profile_dict = self.profile.to_dict()
            self._update_dirty_ui()
            if self.engine is not None:
                self.engine.set_profile(self.profile)
            if self.mapping_switch.get_active():
                self._update_status_active()
            if hasattr(self, "switcher") and self.switcher is not None:
                self.switcher.set_default_profile(name)
        except Exception as err:
            self._info(f"Error cargando perfil '{name}': {err}")

    def on_new_profile(self, _btn):
        if self.has_unsaved_changes():
            dialog = Adw.AlertDialog(
                heading="Cambios sin guardar",
                body=f"Tienes cambios sin guardar en '{self.profile.name}'. ¿Deseas guardarlos antes de crear un nuevo perfil?",
            )
            dialog.add_response("cancel", "Cancelar")
            dialog.add_response("discard", "Descartar y continuar")
            dialog.add_response("save", "Guardar y continuar")
            dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("save")
            dialog.set_close_response("cancel")

            def on_resp(_dlg, resp):
                if resp == "save":
                    self._do_save_profile()
                    self._show_new_profile_dialog()
                elif resp == "discard":
                    self._do_discard_changes()
                    self._show_new_profile_dialog()

            dialog.connect("response", on_resp)
            dialog.present(self)
            return

        self._show_new_profile_dialog()

    def _show_new_profile_dialog(self):
        dialog = Adw.AlertDialog(heading="Nuevo perfil", body="Introduce el nombre del nuevo perfil:")
        entry = Gtk.Entry(text="nuevo_perfil")
        entry.set_margin_top(8)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("create", "Crear")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("create")
        dialog.set_close_response("cancel")

        def on_resp(_dlg, resp):
            if resp == "create":
                name = entry.get_text().strip()
                if name:
                    self.profile = Profile(name=name)
                    self._do_save_profile()
                    self._refresh_profiles_list(select_name=name)
                    self._populate()
                    self._build_editor()
                    if self.engine is not None:
                        self.engine.set_profile(self.profile)
                    if self.mapping_switch.get_active():
                        self._update_status_active()

        dialog.connect("response", on_resp)
        dialog.present(self)

    def on_save(self, _btn=None):
        if not self.has_unsaved_changes():
            self.toast_overlay.add_toast(
                Adw.Toast(title=f"El perfil '{self.profile.name}' ya está guardado (sin cambios pendientes)")
            )
            return

        dialog = Adw.AlertDialog(
            heading="¿Guardar cambios?",
            body=f"¿Deseas confirmar y guardar los cambios realizados en el perfil '{self.profile.name}'?",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("save", "Confirmar y Guardar")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def on_resp(_dlg, resp):
            if resp == "save":
                self._do_save_profile()

        dialog.connect("response", on_resp)
        dialog.present(self)

    def _do_save_profile(self):
        config.save_profile(self.profile)
        self._saved_profile_dict = self.profile.to_dict()
        self._update_dirty_ui()
        self._refresh_profiles_list(select_name=self.profile.name)
        if self.mapping_switch.get_active():
            self._update_status_active()
        self.toast_overlay.add_toast(
            Adw.Toast(title=f"Perfil '{self.profile.name}' guardado correctamente")
        )

    def on_discard(self, _btn=None):
        if not self.has_unsaved_changes():
            self.toast_overlay.add_toast(
                Adw.Toast(title="No hay cambios pendientes para descartar")
            )
            return

        dialog = Adw.AlertDialog(
            heading="¿Descartar cambios?",
            body=f"¿Estás seguro de que deseas cancelar las modificaciones no guardadas en '{self.profile.name}'?\n\nSe restaurará la última versión guardada en disco.",
        )
        dialog.add_response("keep", "Continuar editando")
        dialog.add_response("discard", "Descartar cambios")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("keep")
        dialog.set_close_response("keep")

        def on_resp(_dlg, resp):
            if resp == "discard":
                self._do_discard_changes()

        dialog.connect("response", on_resp)
        dialog.present(self)

    def _do_discard_changes(self):
        self.profile = Profile.from_dict(self._saved_profile_dict)
        self._update_dirty_ui()
        self._populate()
        self._build_editor()
        if self.engine is not None:
            self.engine.set_profile(self.profile)
        self.toast_overlay.add_toast(
            Adw.Toast(title=f"Cambios cancelados en '{self.profile.name}'")
        )

    def on_save_as(self, _btn):
        dialog = Adw.AlertDialog(heading="Guardar perfil como...", body="Introduce el nombre para la copia:")
        entry = Gtk.Entry(text=f"{self.profile.name}_copia")
        entry.set_margin_top(8)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("save", "Guardar")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def on_resp(_dlg, resp):
            if resp == "save":
                name = entry.get_text().strip()
                if name:
                    self.profile.name = name
                    self._do_save_profile()
                    self._refresh_profiles_list(select_name=name)

        dialog.connect("response", on_resp)
        dialog.present(self)

    def on_delete_profile(self, _btn):
        names = config.get_profile_names()
        if len(names) <= 1:
            self._info("No puedes eliminar el único perfil disponible.")
            return

        name = self.profile.name
        dialog = Adw.AlertDialog(
            heading=f"¿Eliminar '{name}'?",
            body="Esta acción eliminará el perfil permanentemente.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("delete", "Eliminar")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_resp(_dlg, resp):
            if resp == "delete":
                path = os.path.join(config.PROFILES_DIR, f"{name}.json")
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                remaining = config.get_profile_names()
                next_name = remaining[0] if remaining else "default"
                self._switch_to_profile(next_name)
                self._refresh_profiles_list(select_name=next_name)

        dialog.connect("response", on_resp)
        dialog.present(self)

    def on_rules(self, _btn):
        rules = config.load_rules()
        names = config.get_profile_names()

        def on_save_rules(updated_rules):
            config.save_rules(updated_rules)
            if hasattr(self, "switcher") and self.switcher is not None:
                self.switcher.set_rules(updated_rules)
            elif self._auto_switch_enabled and self.engine is not None:
                self._start_switcher()

        dialog = RulesDialog(self, names, rules, on_save_rules=on_save_rules)
        dialog.present()

    def on_import(self, _btn):
        file_dialog = Gtk.FileDialog(title="Importar .cfg de JoyToKey")
        cfg_filter = Gtk.FileFilter()
        cfg_filter.set_name("Archivos JoyToKey (*.cfg)")
        cfg_filter.add_pattern("*.cfg")
        all_filter = Gtk.FileFilter()
        all_filter.set_name("Todos los archivos")
        all_filter.add_pattern("*")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(cfg_filter)
        store.append(all_filter)
        file_dialog.set_filters(store)

        def on_file_selected(dialog, result):
            try:
                gfile = dialog.open_finish(result)
                path = gfile.get_path()
                if path:
                    profile, unsupported = config.import_jtkcfg(path)
                    config.save_profile(profile)
                    self.profile = profile
                    self._refresh_profiles_list(select_name=profile.name)
                    self._populate()
                    self._build_editor()
                    msg = f"Importados {len(profile.buttons)} botones y {len(profile.axes)} ejes."
                    if unsupported:
                        msg += "\nIgnorados: " + ", ".join(unsupported)
                    self._info(msg)
            except GLib.Error:
                pass

        file_dialog.open(self, None, on_file_selected)

    def on_auto_switch_toggled(self, sw, _pspec):
        self._auto_switch_enabled = sw.get_active()
        if self.engine is not None:
            if self._auto_switch_enabled:
                self._start_switcher()
            else:
                self._stop_switcher()

    def _start_switcher(self):
        self._stop_switcher()
        rules = config.load_rules()
        if not rules:
            return
        self.switcher = windowwatch.ProfileSwitcher(
            self.engine,
            rules,
            config.load_profile_by_name,
            default_profile_name=self.profile.name,
            on_switch=self._on_profile_auto_switched,
        )
        self.switcher.start()

    def _stop_switcher(self):
        if hasattr(self, "switcher") and self.switcher is not None:
            self.switcher.stop()
            self.switcher = None

    def _on_profile_auto_switched(self, name, profile):
        GLib.idle_add(self._apply_auto_switched_profile, name, profile)

    def _apply_auto_switched_profile(self, name, profile):
        self.profile = profile
        self._refresh_profiles_list(select_name=name)
        self._populate()
        self._build_editor()
        self._update_status_active(f"Auto-perfil activado: {name}")
        return False

    def _update_status_active(self, auto_info=None):
        self.status_pill.set_label("ACTIVO")
        self.status_pill.remove_css_class("joymap-status-inactive")
        self.status_pill.add_css_class("joymap-status-active")
        sub = auto_info or f"Mapeo activo — Perfil: {self.profile.name}"
        self.window_title.set_subtitle(sub)

    def _update_status_inactive(self):
        self.status_pill.set_label("INACTIVO")
        self.status_pill.remove_css_class("joymap-status-active")
        self.status_pill.add_css_class("joymap-status-inactive")
        self.window_title.set_subtitle(self._device_subtitle())

    def _start_monitor(self):
        if self.current_controller is None:
            return
        self.reader_stop = threading.Event()
        open_devices = self.current_controller.open_all()
        for dev in open_devices:
            threading.Thread(target=self._reader, args=(dev,), daemon=True).start()

    def _stop_monitor(self):
        if self.reader_stop is not None:
            self.reader_stop.set()
            self.reader_stop = None
        if self.current_controller is not None:
            for dev in getattr(self.current_controller, "_devices", []):
                try:
                    dev.close()
                except Exception:
                    pass
            self.current_controller._devices = []

    def on_refresh_controllers(self, _btn=None):
        was_active = self.mapping_switch.get_active()
        if was_active:
            self._stop_listen()
        self._stop_monitor()

        self.controllers = devices.list_controllers()
        if self.controllers:
            found = None
            if self.current_controller:
                for c in self.controllers:
                    if c.path == self.current_controller.path or (c.uniq and c.uniq == self.current_controller.uniq):
                        found = c
                        break
            self.current_controller = found or self.controllers[0]
        else:
            self.current_controller = None

        self.current_target = None
        self.window_title.set_subtitle(self._device_subtitle())
        self._populate()
        self._build_editor()

        if self.current_controller is not None:
            self._start_monitor()
            if was_active:
                self._start_listen()
            self.toast_overlay.add_toast(
                Adw.Toast(title=f"Mando detectado: {self.current_controller.name}")
            )
        else:
            if was_active:
                self.mapping_switch.set_active(False)
            self.toast_overlay.add_toast(
                Adw.Toast(title="No se detectaron mandos conectados")
            )

    def on_switch_toggled(self, switch, _pspec):
        if switch.get_active():
            self._start_listen()
        else:
            self._stop_listen()

    def _grab_devices(self):
        if not self.current_controller:
            return
        for dev in self.current_controller._devices:
            if dev in self._grabbed_devices:
                continue
            is_tp = self.current_controller.is_touchpad_device(dev)
            if self._isolate_touchpad_enabled and is_tp:
                try:
                    dev.grab()
                    self._grabbed_devices.append(dev)
                except OSError as ex:
                    print(f"No se pudo aislar {dev.path}: {ex}")

    def _ungrab_devices(self):
        for dev in list(self._grabbed_devices):
            try:
                dev.ungrab()
            except OSError:
                pass
        self._grabbed_devices.clear()

    def on_isolate_touchpad_toggled(self, sw, _pspec):
        self._isolate_touchpad_enabled = sw.get_active()
        if self.mapping_switch.get_active():
            if self._isolate_touchpad_enabled:
                self._grab_devices()
            else:
                self._ungrab_devices()

    def _start_listen(self):
        if self.current_controller is None:
            self.mapping_switch.set_active(False)
            self._info("No hay mando conectado.")
            return
        try:
            self.output = VirtualOutput()
        except PermissionError:
            self.mapping_switch.set_active(False)
            self._info("Permiso denegado en /dev/uinput. Revisa el grupo 'input' y la regla udev.")
            return

        self.engine = MappingEngine(
            self.output,
            axis_info=self.current_controller.axis_info,
            axis_types=self.current_controller.axis_types,
        )
        self.engine.set_profile(self.profile)
        self._grab_devices()
        self._update_status_active()

        if self._auto_switch_enabled:
            self._start_switcher()

    def _stop_listen(self):
        self._ungrab_devices()
        self._stop_switcher()
        if self.output is not None:
            self.output.release_all()
            self.output.close()
            self.output = None
        self.engine = None
        self._clear_highlights()
        self._update_status_inactive()

    def _reader(self, dev):
        is_touchpad = (
            self.current_controller.is_touchpad_device(dev)
            if self.current_controller
            else False
        )
        try:
            for event in dev.read_loop():
                if self.reader_stop is not None and self.reader_stop.is_set():
                    break
                if is_touchpad and event.type != e.EV_KEY:
                    continue
                if self.engine is not None:
                    self.engine.handle_event(event)
                GLib.idle_add(self._apply_event, event)
        except (OSError, ValueError):
            pass

    def _apply_event(self, event):
        if event.type == e.EV_KEY:
            row = self._row_by_button.get(event.code)
            if row is not None:
                self._set_row_active(row, event.value == 1)
        elif event.type == e.EV_ABS:
            self._apply_axis(event.code, event.value)
        return False

    def _apply_axis(self, code, value):
        mapping = self.profile.axes.get(code)
        deadzone = mapping.deadzone if mapping else DEFAULT_DEADZONE
        ctrl = self.current_controller
        info = ctrl.axis_info if ctrl else {}
        available = ctrl.axes if ctrl else None
        axis_type = ctrl.axis_types.get(code) if ctrl else None
        direction = axis_direction(
            code, value, info, deadzone, axis_type=axis_type, available_axes=available
        )
        if axis_type == "trigger":
            row = self._row_by_axis.get((code, 1))
            if row is not None:
                self._set_row_active(row, direction == 1)
        else:
            for d in (-1, 1):
                row = self._row_by_axis.get((code, d))
                if row is not None:
                    self._set_row_active(row, direction == d)

    def _set_row_active(self, row, active):
        if active:
            row.add_css_class("joymap-pressed")
        else:
            row.remove_css_class("joymap-pressed")

    def _clear_highlights(self):
        for row in list(self._row_by_button.values()) + list(self._row_by_axis.values()):
            self._set_row_active(row, False)

    def _info(self, message):
        dialog = Adw.AlertDialog(heading="Información", body=message)
        dialog.add_response("ok", "Entendido")
        dialog.set_default_response("ok")
        dialog.present(self)

    def on_about(self, _btn):
        about = Adw.AboutDialog(
            application_name="Joymap",
            application_icon="joymap",
            version="0.1.0",
            developer_name="UsuallyDanft",
            comments="Mapeador de mando a teclado para Linux moderno inspirado en JoyToKey",
            website="https://github.com/UsuallyDanft/joymap",
        )
        about.present(self)


class JoymapApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="org.joymap.Joymap",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(application=self)
        win.present()


def main():
    app = JoymapApplication()
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
