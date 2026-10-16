from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def install_current_executable(
    executable: Path | None = None,
    *,
    platform: str | None = None,
    environ: dict[str, str] | None = None,
) -> Path | None:
    """Copy the frozen app to a stable per-user installation location."""
    if (platform or sys.platform) != "win32":
        return None
    environment = os.environ if environ is None else environ
    local_appdata = environment.get("LOCALAPPDATA")
    if not local_appdata:
        raise RuntimeError("LOCALAPPDATA is not set; cannot install the updater.")

    source = (executable or Path(sys.executable)).resolve()
    if not source.is_file():
        raise RuntimeError(f"Cannot install missing executable: {source}")
    destination = (
        Path(local_appdata)
        / "Programs"
        / "Spicetify AutoUpdater"
        / "SpicetifyAutoUpdater.exe"
    )
    if os.path.normcase(str(source)) == os.path.normcase(str(destination)):
        return destination

    temporary = destination.with_name(f"{destination.name}.new")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(
            f"Could not install updater to {destination}: {exc}"
        ) from exc
    return destination


def register_startup(
    executable: Path | None = None,
    *,
    platform: str | None = None,
    environ: dict[str, str] | None = None,
) -> Path | None:
    """Register this executable in the current user's Windows Startup folder."""
    if (platform or sys.platform) != "win32":
        return None
    environment = os.environ if environ is None else environ
    appdata = environment.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is not set; cannot register sign-in startup.")

    target = (executable or Path(sys.executable)).resolve()
    if not target.is_file():
        raise RuntimeError(f"Cannot register missing executable for startup: {target}")
    startup_dir = (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )
    shortcut = startup_dir / "Spicetify AutoUpdater.lnk"
    escaped_target = str(target).replace("'", "''")
    escaped_working_dir = str(target.parent).replace("'", "''")
    escaped_shortcut = str(shortcut).replace("'", "''")
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut('{escaped_shortcut}'); "
        f"$shortcut.TargetPath = '{escaped_target}'; "
        f"$shortcut.WorkingDirectory = '{escaped_working_dir}'; "
        "$shortcut.Description = 'Check for Spicetify updates at Windows sign-in'; "
        "$shortcut.Save()"
    )
    try:
        startup_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Could not register automatic startup: {exc}") from exc
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "Unknown PowerShell error."
        raise RuntimeError(f"Could not register automatic startup: {details}")
    if not shortcut.is_file():
        raise RuntimeError(f"Windows did not create the Startup shortcut: {shortcut}")
    return shortcut
