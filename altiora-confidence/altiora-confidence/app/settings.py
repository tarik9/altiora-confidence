"""User settings saved between sessions (always-hide / never-hide lists, last choices)."""

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .patterns import DEFAULT_CATEGORIES

APP_NAME = "Altiora Confidence"


def settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME / "settings.json"


@dataclass
class Settings:
    always_hide: list = field(default_factory=list)
    never_hide: list = field(default_factory=list)
    categories: list = field(default_factory=lambda: list(DEFAULT_CATEGORIES))
    style: str = "black"              # black | label | white
    report: bool = False
    remove_all_images: bool = False
    output_mode: str = "beside"       # beside | folder
    output_folder: str = ""

    @classmethod
    def load(cls):
        p = settings_path()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**known)
        except Exception:
            return cls()

    def save(self):
        p = settings_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add_always(self, text):
        text = " ".join(text.split())
        if text and text.lower() not in {x.lower() for x in self.always_hide}:
            self.always_hide.append(text)
        self.never_hide = [x for x in self.never_hide if x.lower() != text.lower()]

    def add_never(self, text):
        text = " ".join(text.split())
        if text and text.lower() not in {x.lower() for x in self.never_hide}:
            self.never_hide.append(text)
        self.always_hide = [x for x in self.always_hide if x.lower() != text.lower()]
