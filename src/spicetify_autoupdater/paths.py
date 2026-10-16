from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path


def spicetify_config_dir(
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    current_platform = platform or sys.platform
    environment = os.environ if environ is None else environ
    configured = environment.get("SPICETIFY_CONFIG")
    if configured:
        return Path(configured).expanduser()
    if current_platform == "win32":
        appdata = environment.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA is not set; cannot locate Spicetify configuration.")
        return Path(appdata) / "spicetify"
    config_home = environment.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home).expanduser() / "spicetify"
    return (home or Path.home()) / ".config" / "spicetify"


def spicetify_binary(
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path | None:
    current_platform = platform or sys.platform
    environment = os.environ if environ is None else environ
    executable = shutil.which("spicetify", path=environment.get("PATH"))
    if executable:
        return Path(executable)
    if current_platform == "win32":
        local_appdata = environment.get("LOCALAPPDATA")
        if not local_appdata:
            return None
        candidate = Path(local_appdata) / "spicetify" / "spicetify.exe"
    else:
        candidate = (home or Path.home()) / ".spicetify" / "spicetify"
    return candidate if candidate.is_file() else None
