from __future__ import annotations

import configparser
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from spicetify_autoupdater.paths import spicetify_binary, spicetify_config_dir
from spicetify_autoupdater.process import ProcessRunner

LogCallback = Callable[[str], None]

SPICETIFY_INSTALLER = "https://raw.githubusercontent.com/spicetify/cli/main/install.ps1"
SPICETIFY_INSTALLER_SH = "https://raw.githubusercontent.com/spicetify/cli/main/install.sh"
MARKETPLACE_INSTALLER = (
    "https://raw.githubusercontent.com/spicetify/marketplace/main/resources/install.ps1"
)
MARKETPLACE_INSTALLER_SH = (
    "https://raw.githubusercontent.com/spicetify/marketplace/main/resources/install.sh"
)
ADBLOCK_URL = "https://raw.githubusercontent.com/rxri/spicetify-extensions/main/adblock/adblock.js"


class CommandRunner(Protocol):
    def run(self, command: Sequence[str], *, env: Mapping[str, str] | None = None) -> None: ...

    def run_shell_script(
        self,
        script_url: str,
        *,
        env: Mapping[str, str] | None = None,
        preserve_theme: bool = False,
    ) -> None: ...


class SpicetifyManager:
    def __init__(
        self,
        log: LogCallback,
        *,
        platform: str | None = None,
        environ: Mapping[str, str] | None = None,
        home: Path | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self._log = log
        self._platform = platform or sys.platform
        self._environ = dict(os.environ if environ is None else environ)
        self._home = home
        self._runner = runner or ProcessRunner(log, self._platform, self._environ)

    def is_configured(self) -> bool:
        if spicetify_binary(self._platform, self._environ, self._home) is None:
            return False
        extension = (
            spicetify_config_dir(self._platform, self._environ, self._home)
            / "Extensions"
            / "adblock.js"
        )
        return extension.is_file() and "adblock.js" in self._configured_extensions()

    def install_or_update(self) -> None:
        binary = spicetify_binary(self._platform, self._environ, self._home)
        if binary is None:
            self._log("Spicetify CLI not found. Installing the official CLI...")
            self._runner.run_shell_script(
                SPICETIFY_INSTALLER
                if self._platform == "win32"
                else SPICETIFY_INSTALLER_SH
            )
            binary = spicetify_binary(self._platform, self._environ, self._home)
            if binary is None:
                raise RuntimeError(
                    "The installer completed, but Spicetify was not found. "
                    "Check installer output and PATH."
                )
        self._log(f"Spicetify found at {binary}.")
        self._log("Installing or updating Spicetify Marketplace...")
        self._runner.run_shell_script(
            MARKETPLACE_INSTALLER
            if self._platform == "win32"
            else MARKETPLACE_INSTALLER_SH,
            env=self._installer_environment(binary),
            preserve_theme=self._platform == "win32",
        )
        self._ensure_extension()
        extensions = self._configured_extensions()
        if "adblock.js" not in extensions:
            extensions.append("adblock.js")
        self._run(binary, "config", "extensions", "|".join(extensions))
        self._apply(binary)

    def update(self) -> None:
        binary = spicetify_binary(self._platform, self._environ, self._home)
        if binary is None:
            raise RuntimeError(
                "Spicetify is no longer available on PATH or in its install folder."
            )
        self._log("Checking for Spicetify updates...")
        self._run(binary, "update")
        self._run(binary, "apply")

    def _ensure_extension(self) -> None:
        extension_dir = (
            spicetify_config_dir(self._platform, self._environ, self._home)
            / "Extensions"
        )
        extension_file = extension_dir / "adblock.js"
        if extension_file.is_file():
            self._log(f"Adblock extension already exists: {extension_file}")
            return
        self._log(f"Downloading Adblock extension from {ADBLOCK_URL}...")
        try:
            request = urllib.request.Request(
                ADBLOCK_URL, headers={"User-Agent": "Spicetify-AutoUpdater"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError(
                        f"Extension download returned HTTP {response.status}."
                    )
                contents = response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"Could not download adblock.js: {exc}") from exc
        if not contents:
            raise RuntimeError("The downloaded adblock.js file was empty.")
        try:
            extension_dir.mkdir(parents=True, exist_ok=True)
            temporary = extension_file.with_suffix(".js.tmp")
            temporary.write_bytes(contents)
            temporary.replace(extension_file)
        except OSError as exc:
            raise RuntimeError(
                f"Could not write adblock.js to {extension_dir}: {exc}"
            ) from exc
        self._log(f"Installed adblock.js to {extension_file}.")

    def _configured_extensions(self) -> list[str]:
        config_file = (
            spicetify_config_dir(self._platform, self._environ, self._home)
            / "config-xpui.ini"
        )
        if not config_file.is_file():
            return []
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            with config_file.open(encoding="utf-8") as stream:
                parser.read_file(stream)
        except (OSError, UnicodeError, configparser.Error) as exc:
            raise RuntimeError(
                f"Could not read Spicetify config at {config_file}: {exc}"
            ) from exc
        entries: list[str] = []
        for section in parser.sections():
            if parser.has_option(section, "extensions"):
                entries.extend(
                    name.strip()
                    for name in parser.get(section, "extensions").split("|")
                    if name.strip()
                )
        return list(dict.fromkeys(entries))

    def _installer_environment(self, binary: Path) -> dict[str, str]:
        env = dict(self._environ)
        env["PATH"] = f"{binary.parent}{os.pathsep}{env.get('PATH', '')}"
        return env

    def _run(self, binary: Path, *arguments: str) -> None:
        self._runner.run([str(binary), *arguments])

    def _apply(self, binary: Path) -> None:
        self._log("Applying Spicetify updates and registered extensions...")
        self._run(binary, "update")
        self._run(binary, "apply")
