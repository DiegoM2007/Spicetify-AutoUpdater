from pathlib import Path
import unittest
from unittest.mock import patch

from spicetify_autoupdater.paths import spicetify_binary, spicetify_config_dir


class PathResolutionTests(unittest.TestCase):
    def test_windows_config_directory(self) -> None:
        result = spicetify_config_dir(
            "win32", {"APPDATA": r"C:\Users\test\AppData\Roaming"}
        )
        self.assertEqual(result, Path(r"C:\Users\test\AppData\Roaming\spicetify"))

    def test_xdg_config_directory(self) -> None:
        result = spicetify_config_dir(
            "linux", {"XDG_CONFIG_HOME": "/tmp/config"}, Path("/home/test")
        )
        self.assertEqual(result, Path("/tmp/config/spicetify"))

    def test_spicetify_config_override(self) -> None:
        result = spicetify_config_dir(
            "linux",
            {"SPICETIFY_CONFIG": "/tmp/custom", "XDG_CONFIG_HOME": "/tmp/config"},
        )
        self.assertEqual(result, Path("/tmp/custom"))

    def test_missing_appdata_is_explicit(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "APPDATA is not set"):
            spicetify_config_dir("win32", {})

    def test_installed_binary_in_windows_installer_directory(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary_directory:
            expected = Path(temporary_directory) / "spicetify" / "spicetify.exe"
            expected.parent.mkdir()
            expected.touch()
            with patch("spicetify_autoupdater.paths.shutil.which", return_value=None):
                self.assertEqual(
                    spicetify_binary(
                        "win32", {"LOCALAPPDATA": temporary_directory}, Path(temporary_directory)
                    ),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
