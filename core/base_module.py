class BaseModule:
    """
    Base class for all ROV modules.
    Every module should inherit from this class.
    """

    def __init__(self, name):
        self.name = name
        self.running = False

    def initialize(self):
        print(f"[{self.name}] Initialized")

    def start(self):
        self.running = True
        print(f"[{self.name}] Started")

    def update(self):
        if self.running:
            print(f"[{self.name}] Updating...")

    def stop(self):
        self.running = False
        print(f"[{self.name}] Stopped")

    def health_check(self):
        print(f"[{self.name}] Health: OK")
