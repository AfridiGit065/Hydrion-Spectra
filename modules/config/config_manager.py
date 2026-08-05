import os
import yaml

from core.base_module import BaseModule


class ConfigManager(BaseModule):
    """Loads and serves all YAML configs from the configs/ directory."""

    def __init__(self, configs_dir=None):
        super().__init__("Config")
        self.configs_dir = configs_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "configs",
        )
        self.config = {}

    def initialize(self):
        if not os.path.isdir(self.configs_dir):
            raise FileNotFoundError(f"Config directory not found: {self.configs_dir}")
        for name in sorted(os.listdir(self.configs_dir)):
            if not name.endswith(".yaml"):
                continue
            section = name[:-5]
            path = os.path.join(self.configs_dir, name)
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            if list(data.keys()) == [section]:
                data = data[section]
            self.config[section] = data
        self._loaded = True
        return True

    def get_section(self, section):
        return self.config.get(section, {})

    def get(self, section, key=None, default=None):
        section_cfg = self.config.get(section, {})
        if key is None:
            return section_cfg
        return section_cfg.get(key, default)

    def sections(self):
        return list(self.config.keys())

    def health_check(self):
        return len(self.config) > 0
