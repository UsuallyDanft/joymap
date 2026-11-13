# Empaquetado de Joymap

Este directorio contiene las configuraciones para compilar e instalar Joymap de forma nativa en distribuciones basadas en **Debian** (Ubuntu, Linux Mint, etc.) y **Arch Linux** (Manjaro, EndeavourOS, CachyOS, etc.).

---

## 1. Debian / Ubuntu / Linux Mint (`.deb`)

### Generar el paquete `.deb`:
Ejecuta el script de construcción (funciona en cualquier distro Linux sin necesidad de tener Debian instalado):

```bash
python packaging/deb/build_deb.py
```

El paquete generado quedará en:
```text
dist/joymap_0.1.0_all.deb
```

### Instalar en Debian/Ubuntu:
```bash
sudo apt install ./dist/joymap_0.1.0_all.deb
```
*(O haciendo doble clic en el archivo desde el gestor de archivos).*

---

## 2. Arch Linux / Manjaro / EndeavourOS (`PKGBUILD`)

### Compilar e instalar localmente:
Desde el directorio `packaging/arch/`:

```bash
cd packaging/arch
makepkg -si
```

Esto compila el paquete `joymap-0.1.0-1-any.pkg.tar.zst` e instala todas las dependencias oficiales automáticamente.

### Publicar en AUR:
Los archivos en `packaging/arch/` (`PKGBUILD` y `joymap.install`) están listos para subirse a un repositorio AUR.

---

## Permisos automáticos incluidos en ambos paquetes:
Ambos paquetes instalan automáticamente:
- La regla udev `/lib/udev/rules.d/85-joymap-uinput.rules` para dar acceso a `/dev/uinput` y mandos.
- La carga automática del módulo `uinput` al inicio (`/etc/modules-load.d/joymap-uinput.conf`).
- El acceso directo de escritorio y su icono oficial en el menú de aplicaciones.

> [!NOTE]
> Lo único que debe hacer el usuario tras instalar (si no lo ha hecho antes) es pertenecer al grupo `input`:
> ```bash
> sudo usermod -aG input $USER
> ```
> Y cerrar sesión una vez para aplicar los cambios de grupo.
