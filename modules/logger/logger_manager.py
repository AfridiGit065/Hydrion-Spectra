import logging
import os

from core.base_module import BaseModule


class LoggerManager(BaseModule):
    """Configures console + file logging for the whole application."""

    def __init__(self, log_dir=None, level="INFO"):
        super().__init__("Logger")
        self.log_dir = log_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "logs",
        )
        self.level = getattr(logging, str(level).upper(), logging.INFO)

    def initialize(self):
        os.makedirs(self.log_dir, exist_ok=True)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        root = logging.getLogger()
        root.setLevel(self.level)

        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

        system_path = os.path.join(self.log_dir, "system.log")
        system_handler = logging.FileHandler(system_path)
        system_handler.setFormatter(formatter)
        root.addHandler(system_handler)

        errors_path = os.path.join(self.log_dir, "errors.log")
        errors_handler = logging.FileHandler(errors_path)
        errors_handler.setLevel(logging.ERROR)
        errors_handler.setFormatter(formatter)
        root.addHandler(errors_handler)

        self._initialized = True
        return True

    def get_logger(self, name):
        return logging.getLogger(name)
