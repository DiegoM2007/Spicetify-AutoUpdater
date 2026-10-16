from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from spicetify_autoupdater.startup import (
    install_current_executable,
    register_startup,
)
from spicetify_autoupdater.window import MainWindow
from spicetify_autoupdater.workflow import SpicetifyManager


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Spicetify AutoUpdater")
    app.setQuitOnLastWindowClosed(False)

    if getattr(sys, "frozen", False) and sys.platform == "win32":
        try:
            installed_executable = install_current_executable()
            if installed_executable is None:
                raise RuntimeError("Could not determine the installed executable path.")
            register_startup(installed_executable)
        except RuntimeError as exc:
            QMessageBox.warning(
                None,
                "Automatic startup could not be enabled",
                "The updater will run now, but could not be added to Windows "
                f"startup:\n\n{exc}",
            )

    configured = SpicetifyManager(lambda _message: None).is_configured()
    window = MainWindow(automatic_update=configured)
    if configured:
        window.hide()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
