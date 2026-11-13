# 📖 Guía de Instalación y Configuración de Joymap

Esta guía detalla los métodos disponibles para instalar **Joymap** en las diferentes distribuciones de Linux, así como la configuración necesaria de permisos del sistema para el correcto funcionamiento del mando y la emulación de teclado/ratón.

---

## 📋 Índice
1. [Requisitos Previos y Permisos del Sistema](#-requisitos-previos-y-permisos-del-sistema)
2. [Instalación en Debian / Ubuntu / Linux Mint (`.deb`)](#-instalación-en-debian--ubuntu--linux-mint-deb)
3. [Instalación en Arch Linux / Manjaro / EndeavourOS (`PKGBUILD`)](#-instalación-en-arch-linux--manjaro--endeavouros-pkgbuild)
4. [Instalación desde Código Fuente (Cualquier distribución)](#-instalación-desde-código-fuente-cualquier-distribución)
5. [Desinstalación](#-desinstalación)
6. [Resolución de Problemas Frecuentes](#-resolución-de-problemas-frecuentes)

---

## ⚙️ Requisitos Previos y Permisos del Sistema

Joymap necesita interactuar directamente con el kernel de Linux para:
- Leer eventos de los mandos en `/dev/input/event*`.
- Emular teclado y ratón virtuales a través de `/dev/uinput`.

> [!IMPORTANT]
> **No ejecutes Joymap con `sudo`.** El acceso se gestiona a nivel de usuario añadiéndote al grupo `input`.

### 1. Añadir tu usuario al grupo `input`
Abre una terminal y ejecuta:
```bash
sudo usermod -aG input $USER
```

### 2. Reiniciar la sesión
Para que Linux reconozca el nuevo grupo en tu sesión gráfica, **debes cerrar sesión y volver a entrar** (o reiniciar el ordenador).

Para verificar que perteneces al grupo `input`, ejecuta:
```bash
groups | grep input
```
Si ves `input` en la lista, los permisos están correctamente asignados.

---

## 🐧 Instalación en Debian / Ubuntu / Linux Mint (`.deb`)

El paquete `.deb` es el método recomendado para Debian 12 (Bookworm) o superior, Ubuntu 22.04 LTS o superior, Linux Mint, Pop!_OS y derivadas.

### Paso 1: Descargar el paquete
Descarga el archivo `joymap_X.Y.Z_all.deb` desde la sección oficial de [**GitHub Releases**](https://github.com/UsuallyDanft/joymap/releases/latest).

O descárgalo directamente desde la terminal:
```bash
wget https://github.com/UsuallyDanft/joymap/releases/latest/download/joymap_0.1.0_all.deb
```

### Paso 2: Instalar con APT
```bash
sudo apt install ./joymap_0.1.0_all.deb
```
> *Nota: Usar `apt install ./archivo.deb` (con `./`) en lugar de `dpkg -i` garantiza que el gestor descargue e instale automáticamente cualquier librería necesaria (`python3-gi`, `gir1.2-adw-1`, `python3-evdev`).*

---

## 🏹 Instalación en Arch Linux / Manjaro / EndeavourOS (`PKGBUILD`)

Para sistemas basados en Arch Linux, puedes compilar e instalar el paquete nativo `pkg.tar.zst`:

### Opción 1: Usando el repositorio Git
```bash
# 1. Clonar el repositorio
git clone https://github.com/UsuallyDanft/joymap.git
cd joymap/packaging/arch

# 2. Compilar e instalar resolviendo dependencias
makepkg -si
```

### Opción 2: Descargando solo los archivos de empaquetado
Si no quieres clonar todo el repositorio:
```bash
mkdir -p /tmp/joymap-build && cd /tmp/joymap-build
wget https://github.com/UsuallyDanft/joymap/releases/latest/download/PKGBUILD
wget https://github.com/UsuallyDanft/joymap/releases/latest/download/joymap.install
makepkg -si
```

---

## 🐍 Instalación desde Código Fuente (Cualquier distribución)

Si usas Fedora, openSUSE, o prefieres ejecutar Joymap en desarrollo sin instalar paquetes del sistema:

### 1. Instalar dependencias del sistema

- **Debian / Ubuntu / Mint:**
  ```bash
  sudo apt install python3 python3-pip python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-evdev
  ```

- **Arch Linux / Manjaro:**
  ```bash
  sudo pacman -S python python-pip python-gobject gtk4 libadwaita python-evdev
  ```

- **Fedora:**
  ```bash
  sudo dnf install python3 python3-pip python3-gobject gtk4 libadwaita python3-evdev
  ```

### 2. Configurar la regla udev manual (Solo si no instalaste el paquete .deb o PKGBUILD)
```bash
echo 'KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="input", MODE="0660", TAG+="uaccess", OPTIONS+="static_node=uinput"' | sudo tee /etc/udev/rules.d/85-joymap-uinput.rules
sudo modprobe uinput
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### 3. Clonar y ejecutar
```bash
git clone https://github.com/UsuallyDanft/joymap.git
cd joymap
python3 -m joymap.gui
```

---

## 🗑️ Desinstalación

### En Debian / Ubuntu / Mint:
```bash
sudo apt remove joymap
```

### En Arch Linux / Manjaro:
```bash
sudo pacman -R joymap
```

---

## 🔧 Resolución de Problemas Frecuentes

### 1. «Permiso denegado en /dev/uinput»
- Asegúrate de haber ejecutado `sudo usermod -aG input $USER` y de haber **reiniciado tu sesión de usuario**.
- Comprueba que el módulo `uinput` está cargado:
  ```bash
  sudo modprobe uinput
  ```

### 2. «Sin mandos detectados» o la lista aparece vacía
- Conecta el mando por USB o Bluetooth y pulsa el botón **«Detectar mando»** en la barra superior.
- Verifica en la terminal si tu sistema reconoce el mando:
  ```bash
  joymap list
  ```
  Si `joymap list` no muestra nada, revisa si el dispositivo aparece en `/dev/input/by-id/`.

### 3. El auto-cambio de perfil por ventana no cambia
Joymap necesita una utilidad de detección según tu entorno:
- **En KDE Plasma (Wayland):** Instala `kdotool` (`sudo pacman -S kdotool` o desde el gestor de paquetes correspondiente).
- **En entornos X11 (GNOME X11, XFCE, Cinnamon):** Instala `xdotool` (`sudo apt install xdotool` / `sudo pacman -S xdotool`).
