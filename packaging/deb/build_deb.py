#!/usr/bin/env python3
"""Script para construir el paquete .deb de Joymap.

Funciona tanto en Debian/Ubuntu (usando dpkg-deb si está disponible)
como en Arch, Fedora u otros sistemas (usando el formato ar estándar).
"""

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

VERSION = "0.1.0"
PACKAGE_NAME = f"joymap_{VERSION}_all.deb"


def build_deb():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dist_dir = os.path.join(root_dir, "dist")
    os.makedirs(dist_dir, exist_ok=True)
    out_deb = os.path.join(dist_dir, PACKAGE_NAME)

    with tempfile.TemporaryDirectory(prefix="joymap_deb_") as tmpdir:
        debian_dir = os.path.join(tmpdir, "DEBIAN")
        bin_dir = os.path.join(tmpdir, "usr", "bin")
        py_dir = os.path.join(tmpdir, "usr", "lib", "python3", "dist-packages", "joymap")
        udev_dir = os.path.join(tmpdir, "lib", "udev", "rules.d")
        modload_dir = os.path.join(tmpdir, "etc", "modules-load.d")
        desktop_dir = os.path.join(tmpdir, "usr", "share", "applications")
        app_icon_dir = os.path.join(tmpdir, "usr", "share", "icons", "hicolor", "scalable", "apps")
        ctrl_icon_dir = os.path.join(tmpdir, "usr", "share", "joymap", "icons")

        for d in (debian_dir, bin_dir, py_dir, udev_dir, modload_dir, desktop_dir, app_icon_dir, ctrl_icon_dir):
            os.makedirs(d, exist_ok=True)

        # 1. DEBIAN/
        shutil.copy(os.path.join(root_dir, "packaging", "deb", "control"), debian_dir)
        postinst = os.path.join(debian_dir, "postinst")
        postrm = os.path.join(debian_dir, "postrm")
        shutil.copy(os.path.join(root_dir, "packaging", "deb", "postinst"), postinst)
        shutil.copy(os.path.join(root_dir, "packaging", "deb", "postrm"), postrm)
        os.chmod(postinst, 0o755)
        os.chmod(postrm, 0o755)

        # 2. usr/bin/joymap
        joymap_bin = os.path.join(bin_dir, "joymap")
        with open(joymap_bin, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/python3\nimport sys\nfrom joymap.app import main\nif __name__ == '__main__':\n    sys.exit(main())\n")
        os.chmod(joymap_bin, 0o755)

        # 3. usr/lib/python3/dist-packages/joymap/
        src_joymap = os.path.join(root_dir, "src", "joymap")
        for item in os.listdir(src_joymap):
            if item == "__pycache__":
                continue
            s = os.path.join(src_joymap, item)
            d = os.path.join(py_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

        # 4. Reglas udev y modprobe
        shutil.copy(os.path.join(root_dir, "packaging", "85-joymap-uinput.rules"), udev_dir)
        with open(os.path.join(modload_dir, "joymap-uinput.conf"), "w") as f:
            f.write("uinput\n")

        # 5. Desktop y app icon
        shutil.copy(os.path.join(root_dir, "packaging", "joymap.desktop"), desktop_dir)
        shutil.copy(os.path.join(root_dir, "packaging", "joymap.svg"), app_icon_dir)

        # 6. Iconos de botones/cruceta/sticks
        icons_src = os.path.join(root_dir, "icons")
        for f in os.listdir(icons_src):
            if f.endswith(".svg"):
                shutil.copy2(os.path.join(icons_src, f), ctrl_icon_dir)

        # 7. Empaquetar
        if shutil.which("dpkg-deb"):
            subprocess.run(["dpkg-deb", "-b", "--root-owner-group", tmpdir, out_deb], check=True)
        else:
            # Construcción manual en formato ar/tar.gz compatible con dpkg/apt
            _build_deb_manually(tmpdir, out_deb)

    print(f"Paquete .deb generado exitosamente:\n  {out_deb}")
    print(f"Tamaño: {os.path.getsize(out_deb):,} bytes")


def _build_deb_manually(root_path, out_deb):
    temp_dir = tempfile.mkdtemp()
    try:
        # 1. debian-binary
        deb_binary_path = os.path.join(temp_dir, "debian-binary")
        with open(deb_binary_path, "w") as f:
            f.write("2.0\n")

        # 2. control.tar.gz
        control_tar_path = os.path.join(temp_dir, "control.tar.gz")
        with tarfile.open(control_tar_path, "w:gz") as tar:
            deb_dir = os.path.join(root_path, "DEBIAN")
            for item in sorted(os.listdir(deb_dir)):
                full = os.path.join(deb_dir, item)
                arcname = f"./{item}"
                ti = tar.gettarinfo(full, arcname=arcname)
                ti.uid = 0
                ti.gid = 0
                ti.uname = "root"
                ti.gname = "root"
                if os.path.islink(full):
                    ti.type = tarfile.SYMTYPE
                    tar.addfile(ti)
                elif os.path.isdir(full):
                    ti.type = tarfile.DIRTYPE
                    tar.addfile(ti)
                else:
                    with open(full, "rb") as fh:
                        tar.addfile(ti, fh)

        # 3. data.tar.gz
        data_tar_path = os.path.join(temp_dir, "data.tar.gz")
        with tarfile.open(data_tar_path, "w:gz") as tar:
            for dirpath, dirnames, filenames in os.walk(root_path):
                rel = os.path.relpath(dirpath, root_path)
                if rel == "DEBIAN" or rel.startswith("DEBIAN" + os.sep):
                    continue
                dirnames.sort()
                filenames.sort()
                if rel == ".":
                    arc_dir = "."
                else:
                    arc_dir = f"./{rel}"
                ti = tar.gettarinfo(dirpath, arcname=arc_dir)
                ti.uid = 0
                ti.gid = 0
                ti.uname = "root"
                ti.gname = "root"
                tar.addfile(ti)
                for f in filenames:
                    fpath = os.path.join(dirpath, f)
                    arc_file = f"{arc_dir}/{f}" if arc_dir != "." else f"./{f}"
                    ti_f = tar.gettarinfo(fpath, arcname=arc_file)
                    ti_f.uid = 0
                    ti_f.gid = 0
                    ti_f.uname = "root"
                    ti_f.gname = "root"
                    if os.path.islink(fpath):
                        ti_f.type = tarfile.SYMTYPE
                        tar.addfile(ti_f)
                    else:
                        with open(fpath, "rb") as fh:
                            tar.addfile(ti_f, fh)

        # 4. Archivo ar estándar
        if shutil.which("ar"):
            subprocess.run(
                ["ar", "-qc", out_deb, deb_binary_path, control_tar_path, data_tar_path],
                check=True,
            )
        else:
            _write_ar(out_deb, [
                ("debian-binary", deb_binary_path),
                ("control.tar.gz", control_tar_path),
                ("data.tar.gz", data_tar_path),
            ])
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _write_ar(out_file, entries):
    with open(out_file, "wb") as out:
        out.write(b"!<arch>\n")
        for name, path in entries:
            size = os.path.getsize(path)
            stat = os.stat(path)
            # Ar header: 60 bytes
            hdr = (
                f"{name:<16}"
                f"{int(stat.st_mtime):<12}"
                f"{'0':<6}"
                f"{'0':<6}"
                f"{'100644':<8}"
                f"{size:<10}`\n"
            ).encode("ascii")
            out.write(hdr)
            with open(path, "rb") as fh:
                shutil.copyfileobj(fh, out)
            if size % 2 != 0:
                out.write(b"\n")


if __name__ == "__main__":
    build_deb()
