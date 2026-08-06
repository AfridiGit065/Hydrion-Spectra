import logging

from core.base_module import BaseModule


class ServiceManager:
    """Conductor that owns every module: boots, ticks, and shuts them down in order."""

    def __init__(self):
        self._modules = {}
        self.logger = logging.getLogger("Service")

    def register(self, module):
        if not isinstance(module, BaseModule):
            raise TypeError(f"{module!r} is not a BaseModule")
        if module.name in self._modules:
            raise ValueError(f"Module already registered: {module.name}")
        self._modules[module.name] = module
        self.logger.info("Registered %s", module.name)

    def get(self, name, default=None):
        return self._modules.get(name, default)

    def modules(self):
        return list(self._modules.values())

    def initialize_all(self):
        for module in self._modules.values():
            try:
                module.initialize()
            except Exception:
                self.logger.exception("Failed to initialize %s", module.name)

    def start_all(self):
        for module in self._modules.values():
            try:
                module.start()
            except Exception:
                self.logger.exception("Failed to start %s", module.name)

    def update_all(self):
        for module in self._modules.values():
            try:
                module.update()
            except Exception:
                self.logger.exception("Update error in %s", module.name)

    def stop_all(self):
        for module in reversed(list(self._modules.values())):
            try:
                module.stop()
            except Exception:
                self.logger.exception("Failed to stop %s", module.name)

    def health_check(self):
        results = {}
        for module in self._modules.values():
            try:
                result = module.health_check()
                results[module.name] = True if result is None else bool(result)
            except Exception:
                self.logger.exception("Health check failed for %s", module.name)
                results[module.name] = False
        return results
