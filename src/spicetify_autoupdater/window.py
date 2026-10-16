from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spicetify_autoupdater.workflow import SpicetifyManager


class OperationThread(QThread):
    log_message = pyqtSignal(str)
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, operation: Callable[[], None]) -> None:
        super().__init__()
        self._operation = operation

    def run(self) -> None:
        try:
            self._operation()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit()


class MainWindow(QMainWindow):
    def __init__(self, automatic_update: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("Spicetify AutoUpdater")
        self.setMinimumSize(620, 420)
        self._worker: OperationThread | None = None
        self._automatic_update = automatic_update

        heading = QLabel("Spicetify AutoUpdater")
        heading.setObjectName("heading")
        subtitle = QLabel("Install Spicetify and keep Adblockify enabled.")
        self._status = QLabel("Ready")
        self._install_button = QPushButton("Install / Update")
        self._install_button.setObjectName("installButton")
        self._install_button.clicked.connect(self._start_install)
        self._logs = QPlainTextEdit()
        self._logs.setReadOnly(True)
        self._logs.setPlaceholderText("Installation output will appear here.")

        layout = QVBoxLayout()
        layout.addWidget(heading)
        layout.addWidget(subtitle)
        layout.addWidget(self._status)
        layout.addWidget(self._install_button)
        layout.addWidget(self._logs, 1)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #17191f; color: #e7e9ee; }
            QLabel { color: #aeb4c0; }
            QLabel#heading { color: #fff; font-size: 23px; font-weight: 600; }
            QPushButton { background: #1ed760; color: #101510; border: 0; border-radius: 8px; padding: 10px; font-weight: 700; }
            QPlainTextEdit { background: #101216; border: 1px solid #30343e; border-radius: 8px; color: #d0d5df; }
            """
        )
        if automatic_update:
            QTimer.singleShot(0, self._start_launch_update)

    def _start_install(self) -> None:
        self._start_operation(
            "Installing / updating Spicetify...",
            lambda log: SpicetifyManager(log).install_or_update(),
        )

    def _start_launch_update(self) -> None:
        self._start_operation(
            "Checking for Spicetify updates...",
            lambda log: SpicetifyManager(log).update(),
        )

    def _start_operation(
        self,
        description: str,
        operation: Callable[[Callable[[str], None]], None],
    ) -> None:
        if self._worker is not None:
            return
        self._status.setText(description)
        self._logs.appendPlainText(description)
        self._install_button.setEnabled(False)
        worker: OperationThread
        worker = OperationThread(lambda: operation(worker.log_message.emit))
        worker.log_message.connect(self._logs.appendPlainText)
        worker.succeeded.connect(self._operation_succeeded)
        worker.failed.connect(self._operation_failed)
        worker.finished.connect(self._operation_finished)
        self._worker = worker
        worker.start()

    def _operation_succeeded(self) -> None:
        self._logs.appendPlainText("Operation completed successfully.")
        self._status.setText("Up to date")
        if self._automatic_update:
            QApplication.instance().quit()
        else:
            QTimer.singleShot(1500, QApplication.instance().quit)

    def _operation_failed(self, error: str) -> None:
        self._logs.appendPlainText(f"ERROR: {error}")
        self._status.setText("Operation failed")
        title = (
            "Spicetify update failed"
            if self._automatic_update
            else "Spicetify setup failed"
        )
        QMessageBox.critical(self, title, error)
        if self._automatic_update:
            QTimer.singleShot(0, QApplication.instance().quit)

    def _operation_finished(self) -> None:
        self._install_button.setEnabled(True)
        self._worker = None
