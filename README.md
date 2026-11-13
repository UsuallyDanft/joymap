<div align="center">

# 🎮 Joymap

**Mapeador moderno de mando a teclado y ratón para Linux, inspirado en JoyToKey.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![GTK4](https://img.shields.io/badge/GUI-GTK4%20%2F%20Libadwaita-blue?logo=gnome)](https://gnome.pages.gitlab.gnome.org/libadwaita/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Linux%20(evdev%20%2B%20uinput)-orange?logo=linux)](https://kernel.org)

Joymap permite transformar las entradas de cualquier mando de juego (PlayStation, Xbox, Nintendo o genéricos) en pulsaciones de teclado, clics y atajos en entornos Linux modernos. Diseñado con una interfaz visual limpia y adaptativa siguiendo las directrices de **GNOME / Libadwaita**.

</div>

---

## ✨ Características Principales

- 🎨 **Interfaz Moderna en Libadwaita:** Integración nativa con temas claros y oscuros de GNOME / KDE.
- 🔄 **Detección y Reconexión en Caliente:** Conecta o desconecta tu mando en cualquier momento y actualiza con un solo clic («Detectar mando»).
- 🕹️ **Mapeo Completo:**
  - Botones frontales (`X`, `○`, `□`, `△` / `A`, `B`, `X`, `Y`).
  - Cruceta direccional (D-Pad / Hats analógicos o digitales).
  - Sticks analógicos izquierdo y derecho con ajuste fino de **Zona Muerta**.
  - Gatillos analógicos (`L2`/`R2` / `LT`/`RT`) y botones de hombro (`L1`/`R1`).
  - Botones especiales: `Share`, `Options`, `Home / Guía`, clics de stick (`L3`/`R3`) y clic en el touchpad.
- ⚡ **Modos de Asignación Avanzados:**
  - **Normal:** Envío estándar de teclas simples o combinaciones (ej. `Ctrl + Alt + T`).
  - **Turbo / Repetición Automática:** Disparo continuo configurable (desde 1 pulsación/seg hasta más de 50/s).
  - **Rotación Cíclica de Teclas:** Permite alternar diferentes teclas en cada pulsación sucesiva del mismo botón.
- 🪟 **Cambio Automático de Perfil por Ventana:** Conmuta automáticamente de perfil según el juego o aplicación en primer plano (mediante `kdotool` en KDE Wayland o `xdotool` en X11).
- 📂 **Importador de JoyToKey:** Importa directamente tus archivos `.cfg` existentes de JoyToKey.
- 🛡️ **Aislamiento de Touchpad:** Previene clics accidentales en el escritorio mientras juegas.

---

## 📦 Instalación

### Opción A: Debian / Ubuntu / Linux Mint (`.deb`)

Descarga el paquete `.deb` más reciente desde la sección de [**Releases**](https://github.com/danft/joymap/releases) y ejecuta:

```bash
sudo apt install ./joymap_0.1.0_all.deb
```
*(O haz doble clic sobre el archivo descargado para instalarlo desde tu tienda de software).*

### Opción B: Arch Linux / Manjaro / EndeavourOS (`PKGBUILD`)

Clona el repositorio y compila con `makepkg`:

```bash
git clone https://github.com/danft/joymap.git
cd joymap/packaging/arch
makepkg -si
```

---

## ⚙️ Permisos y Configuración Inicial

Joymap emula teclados virtuales a través del módulo del kernel `/dev/uinput` y lee mandos a través de `/dev/input/event*`.

> [!IMPORTANT]
> **No ejecutes Joymap con `sudo`.** Solo necesitas asegurarte de que tu usuario pertenece al grupo `input`:

1. Añade tu usuario al grupo `input`:
   ```bash
   sudo usermod -aG input $USER
   ```
2. **Cierra sesión y vuelve a iniciarla** (o reinicia tu equipo) para que los permisos se apliquen.

*(Nota: Los paquetes `.deb` y `PKGBUILD` ya instalan automáticamente la regla udev necesaria en `/lib/udev/rules.d/85-joymap-uinput.rules`).*

---

## 🚀 Uso

### Interfaz Gráfica
Abre la aplicación buscando **Joymap** en el menú de aplicaciones de tu sistema, o ejecuta en la terminal:

```bash
joymap
# o bien:
joymap gui
```

### Línea de Comandos (CLI)
Joymap también incluye herramientas por consola para scripts o servidores:

```bash
# Listar mandos y botones detectados
joymap list

# Probar botones y ejes en tiempo real
joymap test

# Ejecutar un perfil en segundo plano sin interfaz
joymap run --profile "MiJuego"

# Importar un archivo de JoyToKey
joymap import ruta/al/perfil.cfg
```

---

## 🛠️ Desarrollo y Ejecución desde Fuentes

Si deseas colaborar o ejecutar Joymap desde el código fuente:

```bash
# 1. Clonar el repositorio
git clone https://github.com/danft/joymap.git
cd joymap

# 2. Instalar dependencias del sistema (Debian/Ubuntu)
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-evdev

# 2. Alternativa: dependencias del sistema (Arch Linux)
sudo pacman -S python-gobject gtk4 libadwaita python-evdev

# 3. Ejecutar la aplicación
python3 -m joymap.gui
```

---

## 📜 Licencia

Distribuido bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más información.
