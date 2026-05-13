"""App class: wires everything together and starts the UI."""
import logging
import sys

from PySide6.QtCore import QTimer

import dropletui as ui

from droplegen.controller import Controller
from droplegen.ui.main_window import MainWindow


class DroplegenApp:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        self._qapp = ui.create_app("Droplegen", sys.argv)

        self.controller = Controller()
        self.window = MainWindow(self.controller)

        # Timer so Python signal handlers can fire
        self._keep_alive = QTimer()
        self._keep_alive.timeout.connect(lambda: None)
        self._keep_alive.start(500)

    def run(self) -> int:
        self.window.show()
        return self._qapp.exec()
