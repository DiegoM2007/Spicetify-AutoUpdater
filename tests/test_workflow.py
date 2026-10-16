from collections.abc import Mapping, Sequence
from pathlib import Path
import unittest
from unittest.mock import patch

from spicetify_autoupdater import workflow
from spicetify_autoupdater.workflow import SpicetifyManager


class RecordingRunner:
    def __init__(self) -> None:
        self.shell_scripts: list[tuple[str, dict[str, str] | None, bool]] = []
        self.commands: list[list[str]] = []

    def run_shell_script(
        self,
        script_url: str,
        *,
        env: Mapping[str, str] | None = None,
        preserve_theme: bool = False,
    ) -> None:
        self.shell_scripts.append(
            (script_url, dict(env) if env is not None else None, preserve_theme)
        )

    def run(self, command: Sequence[str]) -> None:
        self.commands.append(list(command))


class WorkflowTests(unittest.TestCase):
    def test_is_configured_requires_binary_extension_and_registration(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary_directory:
            config_dir = Path(temporary_directory) / "spicetify"
            extension = config_dir / "Extensions" / "adblock.js"
            extension.parent.mkdir(parents=True)
            extension.write_text("// extension", encoding="utf-8")
            (config_dir / "config-xpui.ini").write_text(
                "[AdditionalOptions]\nextensions = adblock.js\n", encoding="utf-8"
            )
            manager = SpicetifyManager(
                lambda _message: None,
                platform="linux",
                environ={"XDG_CONFIG_HOME": temporary_directory},
            )
            with patch.object(
                workflow, "spicetify_binary", return_value=Path("/usr/bin/spicetify")
            ):
                self.assertTrue(manager.is_configured())
            with patch.object(workflow, "spicetify_binary", return_value=None):
                self.assertFalse(manager.is_configured())
            extension.unlink()
            with patch.object(
                workflow, "spicetify_binary", return_value=Path("/usr/bin/spicetify")
            ):
                self.assertFalse(manager.is_configured())

    def test_install_runs_cli_marketplace_extension_and_apply(self) -> None:
        runner = RecordingRunner()
        binary = Path(r"C:\Users\test\AppData\Local\spicetify\spicetify.exe")
        manager = SpicetifyManager(
            lambda _message: None,
            platform="win32",
            environ={
                "LOCALAPPDATA": r"C:\Users\test\AppData\Local",
                "PATH": r"C:\Windows\System32",
            },
            runner=runner,
        )
        with (
            patch.object(workflow, "spicetify_binary", side_effect=[None, binary]),
            patch.object(manager, "_ensure_extension"),
            patch.object(manager, "_configured_extensions", return_value=["old.js"]),
        ):
            manager.install_or_update()

        self.assertEqual(
            [url for url, _, _ in runner.shell_scripts],
            [workflow.SPICETIFY_INSTALLER, workflow.MARKETPLACE_INSTALLER],
        )
        self.assertEqual(
            runner.shell_scripts[1][1]["PATH"],
            f"{binary.parent};C:\\Windows\\System32",
        )
        self.assertTrue(runner.shell_scripts[1][2])
        self.assertEqual(
            runner.commands,
            [
                [str(binary), "config", "extensions", "old.js|adblock.js"],
                [str(binary), "update"],
                [str(binary), "apply"],
            ],
        )

    def test_extensions_are_preserved_and_deduplicated(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary_directory:
            config_dir = Path(temporary_directory) / "spicetify"
            config_dir.mkdir()
            (config_dir / "config-xpui.ini").write_text(
                "[AdditionalOptions]\nextensions = old.js|adblock.js|old.js\n",
                encoding="utf-8",
            )
            manager = SpicetifyManager(
                lambda _message: None,
                platform="win32",
                environ={"APPDATA": temporary_directory},
            )
            self.assertEqual(manager._configured_extensions(), ["old.js", "adblock.js"])

    def test_missing_extension_downloads_to_extension_directory(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary_directory:
            manager = SpicetifyManager(
                lambda _message: None,
                platform="linux",
                environ={"XDG_CONFIG_HOME": temporary_directory},
            )
            with patch.object(workflow.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = b"extension source"
                manager._ensure_extension()
            extension = (
                Path(temporary_directory)
                / "spicetify"
                / "Extensions"
                / "adblock.js"
            )
            self.assertEqual(extension.read_bytes(), b"extension source")
            self.assertEqual(urlopen.call_args.args[0].full_url, workflow.ADBLOCK_URL)

    def test_launch_update_runs_update_before_apply(self) -> None:
        runner = RecordingRunner()
        binary = Path("/home/test/.spicetify/spicetify")
        manager = SpicetifyManager(
            lambda _message: None,
            platform="linux",
            runner=runner,
        )
        with patch.object(workflow, "spicetify_binary", return_value=binary):
            manager.update()
        self.assertEqual(
            runner.commands,
            [[str(binary), "update"], [str(binary), "apply"]],
        )


if __name__ == "__main__":
    unittest.main()
