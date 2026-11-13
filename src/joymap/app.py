import argparse
import selectors
import sys

from evdev import ecodes as e

from . import config, devices
from .mapping import MappingEngine, Profile, axis_direction
from .output import VirtualOutput


def cmd_list(args):
    controllers = devices.list_controllers(include_all=args.all)
    if not controllers:
        print("No se detectaron mandos. (Necesitas estar en el grupo 'input' y tener un mando conectado.)")
        return 1
    for ctrl in controllers:
        print(f"{ctrl.name}  ({', '.join(ctrl.paths)})")
        for code in ctrl.buttons:
            print(f"    boton  {code:>3}  {devices.button_label(code)}")
        for axis in ctrl.axes:
            lo, hi = ctrl.axis_info.get(axis, ("?", "?"))
            name = e.ABS.get(axis, f"ABS_{axis}")
            t = ctrl.axis_types.get(axis, "stick")
            if t == "trigger":
                lbl = devices.axis_label(axis, 1, ctrl.axes)
            else:
                lbl = f"{devices.axis_label(axis, -1, ctrl.axes)} / {devices.axis_label(axis, 1, ctrl.axes)}"
            print(f"    eje    {axis:>3}  {name:<10} [{lbl}] rango {lo}..{hi}")
        if ctrl.unreadable_nodes:
            print("    [!] Nodos asociados sin permisos de lectura:")
            for node in ctrl.unreadable_nodes:
                print(f"        - {node}")
            print("        Para habilitar el 'Clic Touchpad', ejecuta:")
            print("        echo 'KERNEL==\"event*\", ATTRS{name}==\"*Touchpad*\", TAG+=\"uaccess\"' | sudo tee /etc/udev/rules.d/71-gamepad-touchpad.rules && sudo udevadm trigger")
            print("        (o añade tu usuario al grupo: sudo usermod -aG input $USER)")
    return 0


def run(controller, profile, verbose=False, auto=False, grab_touchpad=True):
    out = VirtualOutput()
    engine = MappingEngine(out, axis_info=controller.axis_info, axis_types=controller.axis_types)
    engine.set_profile(profile)
    switcher = None
    if auto:
        from .windowwatch import ProfileSwitcher
        rules = config.load_rules()
        if rules:
            def on_sw(name, p):
                if verbose:
                    print(f"[Auto-cambio] Perfil activado: '{name}'")
            switcher = ProfileSwitcher(
                engine,
                rules,
                config.load_profile_by_name,
                default_profile_name=profile.name,
                on_switch=on_sw,
            )
            switcher.start()
            if verbose:
                print(f"Cambio automatico por ventana activa activado ({len(rules)} reglas).")
        elif verbose:
            print("No hay reglas en rules.json; el cambio automatico queda inactivo.")
    open_devices = controller.open_all()
    if not open_devices:
        print(f"No se pudo abrir ningun nodo de {controller.name}.")
        out.close()
        return 1
    grabbed = []
    if grab_touchpad:
        for dev in open_devices:
            if controller.is_touchpad_device(dev):
                try:
                    dev.grab()
                    grabbed.append(dev)
                    if verbose:
                        print(f"[Aislamiento] Touchpad capturado en exclusiva ({dev.path})")
                except OSError as ex:
                    if verbose:
                        print(f"[Aviso] No se pudo aislar {dev.path}: {ex}")
    if verbose:
        print(f"Escuchando {controller.name} con perfil '{profile.name}' ({len(open_devices)} nodos)")
    selector = selectors.DefaultSelector()
    for dev in open_devices:
        selector.register(dev.fd, selectors.EVENT_READ, dev)
    axis_prev = {}
    try:
        while True:
            for key, _ in selector.select():
                dev = key.data
                is_touchpad = controller.is_touchpad_device(dev)
                for event in dev.read():
                    if is_touchpad and event.type != e.EV_KEY:
                        continue
                    if verbose:
                        if event.type == e.EV_KEY:
                            label = devices.button_label(event.code)
                            print(f"[Boton] {label:<24} {'pulsado' if event.value else 'soltado'}")
                        elif event.type == e.EV_ABS:
                            d = axis_direction(
                                event.code,
                                event.value,
                                controller.axis_info,
                                axis_type=controller.axis_types.get(event.code),
                                available_axes=controller.axes,
                            )
                            prev = axis_prev.get(event.code, 0)
                            if d != prev:
                                axis_prev[event.code] = d
                                if d != 0:
                                    lbl = devices.axis_label(event.code, d, controller.axes)
                                    print(f"[Eje]   {lbl:<24} activo (valor={event.value})")
                                else:
                                    lbl = devices.axis_label(event.code, prev, controller.axes)
                                    print(f"[Eje]   {lbl:<24} reposo (valor={event.value})")
                    engine.handle_event(event)
    except KeyboardInterrupt:
        pass
    finally:
        for dev in grabbed:
            try:
                dev.ungrab()
            except OSError:
                pass
        selector.close()
        if switcher is not None:
            switcher.stop()
        out.close()
    return 0


def cmd_test(args):
    controllers = devices.list_controllers()
    if not controllers:
        print("No se detectaron mandos.")
        return 1
    if args.device:
        controller = next((c for c in controllers if args.device in c.paths), None)
        if controller is None:
            print(f"No existe el dispositivo {args.device}")
            return 1
    else:
        controller = controllers[0]

    open_devices = controller.open_all()
    if not open_devices:
        print(f"No se pudo abrir ningun nodo de {controller.name}.")
        return 1

    print(f"Probando {controller.name} ({len(open_devices)} nodos). Mueve los sticks o pulsa botones (Ctrl+C para salir):")
    selector = selectors.DefaultSelector()
    for dev in open_devices:
        selector.register(dev.fd, selectors.EVENT_READ, dev)
    axis_prev = {}
    try:
        while True:
            for key, _ in selector.select():
                dev = key.data
                is_touchpad = controller.is_touchpad_device(dev)
                for event in dev.read():
                    if is_touchpad and event.type != e.EV_KEY:
                        continue
                    if event.type == e.EV_KEY:
                        label = devices.button_label(event.code)
                        print(f"[Boton] {label:<26} {'pulsado' if event.value else 'soltado'}")
                    elif event.type == e.EV_ABS:
                        d = axis_direction(
                            event.code,
                            event.value,
                            controller.axis_info,
                            axis_type=controller.axis_types.get(event.code),
                            available_axes=controller.axes,
                        )
                        prev = axis_prev.get(event.code, 0)
                        if d != prev:
                            axis_prev[event.code] = d
                            if d != 0:
                                lbl = devices.axis_label(event.code, d, controller.axes)
                                print(f"[Eje]   {lbl:<26} activo (valor={event.value})")
                            else:
                                lbl = devices.axis_label(event.code, prev, controller.axes)
                                print(f"[Eje]   {lbl:<26} reposo / centro (valor={event.value})")
    except KeyboardInterrupt:
        pass
    finally:
        selector.close()
    return 0


def cmd_run(args):
    controllers = devices.list_controllers()
    if not controllers:
        print("No se detectaron mandos.")
        return 1
    if args.device:
        controller = next((c for c in controllers if args.device in c.paths), None)
        if controller is None:
            print(f"No existe el dispositivo {args.device}")
            return 1
    else:
        controller = controllers[0]

    if args.profile:
        import os
        if os.path.exists(args.profile):
            profile = config.load_profile(args.profile)
        else:
            profile = config.load_profile_by_name(args.profile)
    else:
        names = config.get_profile_names()
        if "default" in names:
            profile = config.load_profile_by_name("default")
        elif names:
            profile = config.load_profile_by_name(names[0])
        else:
            profile = Profile(name="default")

    try:
        return run(
            controller,
            profile,
            verbose=args.verbose,
            auto=args.auto,
            grab_touchpad=getattr(args, "grab_touchpad", True),
        )
    except PermissionError:
        print("Permiso denegado. Agrega tu usuario al grupo 'input' y vuelve a iniciar sesion.")
        return 1


def cmd_import(args):
    profile, unsupported = config.import_jtkcfg(args.cfg)
    path = config.save_profile(profile)
    print(f"Importado '{args.cfg}' -> {path}")
    print(f"  {len(profile.buttons)} botones y {len(profile.axes)} ejes con asignacion.")
    if unsupported:
        print("  No soportado aun (se ignoro): " + ", ".join(unsupported))
    return 0


def cmd_gui(args):
    from .gui import main as gui_main
    return gui_main()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="joymap")
    sub = parser.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="Lista mandos y sus botones")
    p_list.add_argument("--all", action="store_true", help="Incluye dispositivos no-mando")
    p_list.set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", help="Ejecuta el mapeo")
    p_run.add_argument("--profile")
    p_run.add_argument("--device")
    p_run.add_argument("-v", "--verbose", action="store_true")
    p_run.add_argument("--auto", action="store_true", help="Cambiar de perfil segun la ventana activa (kdotool)")
    p_run.add_argument(
        "--no-grab-touchpad",
        dest="grab_touchpad",
        action="store_false",
        default=True,
        help="No aislar el touchpad (permite que KDE siga recibiendo sus eventos)",
    )
    p_run.set_defaults(func=cmd_run)

    p_imp = sub.add_parser("import", help="Importa un .cfg de JoyToKey")
    p_imp.add_argument("cfg")
    p_imp.set_defaults(func=cmd_import)

    p_test = sub.add_parser("test", help="Prueba en tiempo real los sticks, gatillos y botones del mando")
    p_test.add_argument("--device")
    p_test.set_defaults(func=cmd_test)

    p_gui = sub.add_parser("gui", help="Abre la interfaz grafica")
    p_gui.set_defaults(func=cmd_gui)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        try:
            from .gui import main as gui_main
            return gui_main()
        except Exception:
            parser.print_help()
            return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
