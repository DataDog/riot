from pathlib import Path

from envier import En


class RiotConfig(En):
    __prefix__ = "riot"

    riot_folder = En.v(Path, "env.base_path", default=Path(".riot"))
    venv_prefix = En.v(str, "env.prefix", default="venv_py")


config = RiotConfig()
