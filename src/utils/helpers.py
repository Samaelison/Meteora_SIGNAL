

import yaml
from pathlib import Path
from .project_settings import PROJECT_ROOT

def load_config() -> dict:
    """
    Считывает config.yaml и возвращает словарь с настройками.
    """
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data
