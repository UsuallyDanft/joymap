import re
from dataclasses import dataclass, field

from .keymap import vk_to_key, key_to_vk, MOUSE_VK_TO_KEY

TYPE_NONE = 0
TYPE_KEY = 1
TYPE_MOUSE = 2
TYPE_COMMAND = 5
TYPE_SEQUENCE = 7
TYPE_LAUNCH = 9


@dataclass
class Entry:
    target: str
    action: int
    keys: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    payload: str = ""
    raw: list = field(default_factory=list)
    comment: str = ""

    def is_empty(self):
        if self.action == TYPE_NONE:
            return True
        if self.action == TYPE_KEY and not self.keys:
            return True
        return False


@dataclass
class Joystick:
    index: int
    entries: dict = field(default_factory=dict)


@dataclass
class JoyToKeyConfig:
    version: int = 0
    general: dict = field(default_factory=dict)
    joysticks: dict = field(default_factory=dict)
    source: str = ""


_SECTION = re.compile(r"^\[(.+)\]$")


def _split_fields(value):
    out = []
    buf = []
    in_quotes = False
    for ch in value:
        if ch == '"':
            in_quotes = not in_quotes
            buf.append(ch)
        elif ch == "," and not in_quotes:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf).strip())
    return out


def _parse_key_group(text):
    keys = []
    for tok in text.split(":"):
        tok = tok.strip()
        if not tok:
            continue
        try:
            vk = int(tok, 16)
        except ValueError:
            continue
        if vk == 0:
            continue
        key = vk_to_key(vk)
        if key is not None:
            keys.append(key)
    return keys


def _parse_entry(target, value, comment):
    fields = _split_fields(value)
    try:
        action = int(fields[0])
    except (ValueError, IndexError):
        return Entry(target=target, action=TYPE_NONE, raw=fields, comment=comment)

    entry = Entry(target=target, action=action, raw=fields, comment=comment)

    if action == TYPE_KEY:
        if len(fields) >= 2:
            entry.keys = _parse_key_group(fields[1])
    elif action == TYPE_SEQUENCE:
        for grp in fields[3:7]:
            entry.steps.append(_parse_key_group(grp))
    elif action in (TYPE_LAUNCH,):
        if len(fields) >= 2:
            entry.payload = fields[1].strip('"')
    elif action == TYPE_COMMAND:
        entry.payload = value
    return entry


def parse(text, source=""):
    cfg = JoyToKeyConfig(source=source)
    section = None
    current_jidx = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n\r")
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        comment = ""
        if "##" in line:
            line, comment = line.split("##", 1)
            comment = comment.strip()
        line = line.rstrip()
        m = _SECTION.match(line.strip())
        if m:
            name = m.group(1).strip()
            section = name
            if name.startswith("Joystick"):
                try:
                    current_jidx = int(name.split()[1])
                except (IndexError, ValueError):
                    current_jidx = 0
                cfg.joysticks.setdefault(current_jidx, Joystick(index=current_jidx))
            else:
                current_jidx = None
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if section == "General":
            cfg.general[key] = value
        elif section and section.startswith("Joystick"):
            jidx = current_jidx if current_jidx is not None else 0
            joystick = cfg.joysticks.setdefault(jidx, Joystick(index=jidx))
            joystick.entries[key] = _parse_entry(key, value, comment)

    if "FileVersion" in cfg.general:
        try:
            cfg.version = int(cfg.general["FileVersion"])
        except ValueError:
            pass
    return cfg


def parse_file(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        return parse(fh.read(), source=path)


def _emit_key_group(keys):
    parts = []
    for k in keys[:4]:
        vk = key_to_vk(k)
        if vk is None:
            continue
        parts.append(f"{vk:02X}")
    while len(parts) < 4:
        parts.append("00")
    return ":".join(parts)


def dump(cfg):
    lines = ["[General]"]
    for key, value in cfg.general.items():
        lines.append(f"{key}={value}")
    for idx in sorted(cfg.joysticks):
        lines.append("")
        lines.append(f"[Joystick {idx}]")
        for name, entry in cfg.joysticks[idx].entries.items():
            if entry.action == TYPE_KEY:
                kg = _emit_key_group(entry.keys)
                line = f"{name}=1, {kg}, 0.000, 0, 0"
            else:
                line = f"{name}=" + ",".join(str(x) for x in entry.raw)
            if entry.comment:
                line += f"  ##{entry.comment}"
            lines.append(line)
    return "\n".join(lines) + "\n"
