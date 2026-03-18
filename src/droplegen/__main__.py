"""Entry point for python -m droplegen."""
import signal
import sys

from droplegen.app import DroplegenApp


def main():
    app = DroplegenApp()

    def _sigint_handler(sig, frame):
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    signal.signal(signal.SIGINT, _sigint_handler)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
