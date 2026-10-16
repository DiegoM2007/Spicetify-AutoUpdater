import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from spicetify_autoupdater.startup import install_current_executable, register_startup


class StartupTests(unittest.TestCase):
    def test_installs_executable_under_local_appdata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "Downloads" / "Updater.exe"
            source.parent.mkdir()
            source.write_bytes(b"packaged app")
            local_appdata = root / "Local"

            installed = install_current_executable(
                source,
                platform="win32",
                environ={"LOCALAPPDATA": str(local_appdata)},
            )

            self.assertEqual(
                installed,
                local_appdata
                / "Programs"
                / "Spicetify AutoUpdater"
                / "SpicetifyAutoUpdater.exe",
            )
            self.assertEqual(installed.read_bytes(), b"packaged app")
            self.assertFalse(installed.with_name(f"{installed.name}.new").exists())

    def test_does_not_recopy_when_running_from_install_location(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            installed = (
                Path(temporary_directory)
                / "Programs"
                / "Spicetify AutoUpdater"
                / "SpicetifyAutoUpdater.exe"
            )
            installed.parent.mkdir(parents=True)
            installed.write_bytes(b"already installed")

            result = install_current_executable(
                installed,
                platform="win32",
                environ={"LOCALAPPDATA": temporary_directory},
            )

            self.assertEqual(result, installed)
            self.assertEqual(installed.read_bytes(), b"already installed")

    def test_non_windows_does_not_register_shortcut(self) -> None:
        self.assertIsNone(register_startup(platform="linux", environ={}))

    def test_missing_appdata_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "APPDATA is not set"):
            register_startup(platform="win32", environ={})

    def test_registers_executable_for_user_sign_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            executable = root / "Updater.exe"
            executable.touch()
            startup = (
                root
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
                / "Startup"
            )

            def create_shortcut(*args: object, **kwargs: object):
                shortcut = startup / "Spicetify AutoUpdater.lnk"
                shortcut.parent.mkdir(parents=True, exist_ok=True)
                shortcut.touch()

                class Result:
                    returncode = 0
                    stdout = ""
                    stderr = ""

                return Result()

            with patch(
                "spicetify_autoupdater.startup.subprocess.run",
                side_effect=create_shortcut,
            ) as run:
                result = register_startup(
                    executable,
                    platform="win32",
                    environ={"APPDATA": str(root)},
                )

            self.assertEqual(result, startup / "Spicetify AutoUpdater.lnk")
            command = run.call_args.args[0]
            self.assertEqual(command[0], "powershell.exe")
            self.assertIn(
                os.path.normcase(str(executable.resolve())),
                os.path.normcase(command[-1]),
            )
            self.assertIn(str(result), command[-1])


if __name__ == "__main__":
    unittest.main()
