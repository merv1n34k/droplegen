"""App class: wires everything together and starts the UI."""
import logging
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from droplegen.controller import Controller
from droplegen.ui.main_window import MainWindow

_DARK_QSS = """
QWidget {
    background-color: #1a1a1a;
    color: #d4d4d4;
    font-size: 13px;
}
QMainWindow {
    background-color: #1a1a1a;
}
QLabel {
    background: transparent;
}
QLineEdit {
    background-color: #2b2b2b;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 3px 6px;
    color: #d4d4d4;
}
QLineEdit:focus {
    border-color: #3498db;
}
QPushButton {
    background-color: #2b2b2b;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 4px 12px;
    color: #d4d4d4;
}
QPushButton:hover {
    background-color: #353535;
    border-color: #444444;
}
QPushButton:pressed {
    background-color: #404040;
}
QPushButton:disabled {
    color: #555555;
    background-color: #222222;
    border-color: #2a2a2a;
}
QComboBox {
    background-color: #2b2b2b;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 3px 8px;
    color: #d4d4d4;
    min-width: 80px;
}
QComboBox:hover {
    border-color: #444444;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #d4d4d4;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #2b2b2b;
    border: 1px solid #444444;
    color: #d4d4d4;
    selection-background-color: #3498db;
}
QCheckBox {
    spacing: 4px;
    background: transparent;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #333333;
    border-radius: 3px;
    background: #2b2b2b;
}
QCheckBox::indicator:checked {
    background: #3498db;
    border-color: #3498db;
}
QProgressBar {
    border: 1px solid #333333;
    border-radius: 3px;
    background: #222222;
    text-align: center;
    max-height: 8px;
}
QProgressBar::chunk {
    background: #3498db;
    border-radius: 2px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: #1a1a1a;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #444444;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #555555;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QSplitter::handle {
    background: #333333;
}
QSplitter::handle:horizontal {
    width: 3px;
}
QSplitter::handle:vertical {
    height: 3px;
}
QStatusBar {
    background-color: #1a1a1a;
    color: #888888;
    font-size: 11px;
}
"""


class DroplegenApp:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        self._qapp = QApplication(sys.argv)
        self._qapp.setStyleSheet(_DARK_QSS)

        self.controller = Controller()
        self.window = MainWindow(self.controller)

        # Timer so Python signal handlers can fire
        self._keep_alive = QTimer()
        self._keep_alive.timeout.connect(lambda: None)
        self._keep_alive.start(500)

    def run(self) -> int:
        self.window.show()
        return self._qapp.exec()
