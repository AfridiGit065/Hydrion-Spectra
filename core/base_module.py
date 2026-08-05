import logging


class BaseModule:
    """
    Base class for all ROV modules.
    Every module should inherit from this class.
    """

    def __init__(self, name):
        self.name = name
        self.running = False
        self.logger = logging.getLogger(name)

    def initialize(self):
        self.logger.info("Initialized")

    def start(self):
        self.running = True
        self.logger.info("Started")

    def update(self):
        if self.running:
            self.logger.debug("Updating...")

    def stop(self):
        self.running = False
        self.logger.info("Stopped")

    def health_check(self):
        self.logger.info("Health: OK")
