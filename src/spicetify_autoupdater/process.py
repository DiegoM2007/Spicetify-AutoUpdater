from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence

LogCallback = Callable[[str], None]


class ProcessExecutionError(RuntimeError):
    """Raised when a subprocess cannot start or exits unsuccessfully."""


class ProcessRunner:
    def __init__(
        self,
        log: LogCallback,
        platform: str | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._log = log
        self._platform = platform or sys.platform
        self._environ = dict(os.environ if environ is None else environ)

    def run(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._log(f"> {' '.join(command)}")
        child_environment = dict(self._environ)
        if env:
            child_environment.update(env)
        try:
            process = subprocess.Popen(
                list(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=child_environment,
            )
        except OSError as exc:
            raise RuntimeError(f"Could not start {command[0]}: {exc}") from exc
        assert process.stdout is not None
        for line in process.stdout:
            self._log(line.rstrip())
        return_code = process.wait()
        if return_code:
            raise RuntimeError(
                f"Command failed with exit code {return_code}: {' '.join(command)}"
            )

    def run_shell_script(
        self,
        script_url: str,
        *,
        env: Mapping[str, str] | None = None,
        preserve_theme: bool = False,
    ) -> None:
        if self._platform == "win32":
            if preserve_theme:
                script = (
                    "$ErrorActionPreference = 'Stop'; "
                    f"$installer = (Invoke-WebRequest -UseBasicParsing -Uri '{script_url}').Content; "
                    "$promptPattern = '(?ms)\\$choice\\s*=\\s*\\$Host\\.UI\\.PromptForChoice\\(\\r?\\n.*?^\\s*\\)'; "
                    "$promptMatches = [regex]::Matches($installer, $promptPattern); "
                    "if ($promptMatches.Count -ne 1) { "
                    "throw 'Marketplace theme prompt was not found uniquely; refusing an unsafe unattended install.' "
                    "}; "
                    "$prompt = $promptMatches[0]; "
                    "$installer = $installer.Remove($prompt.Index, $prompt.Length).Insert($prompt.Index, '$choice = 1'); "
                    "Invoke-Expression $installer; "
                    "if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
                )
            else:
                script = (
                    "$ErrorActionPreference = 'Stop'; "
                    f"Invoke-WebRequest -UseBasicParsing -Uri '{script_url}' | "
                    "Invoke-Expression; "
                    "if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
                )
            self.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                env=env,
            )
            return
        self.run(
            ["bash", "-o", "pipefail", "-c", f"curl -fsSL '{script_url}' | sh"],
            env=env,
        )
