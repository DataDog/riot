import dataclasses
import functools
import logging
from pathlib import Path
import shutil
import subprocess
import typing as t

from riot.config import config
from riot.utils import site_pkgs


logger = logging.getLogger(__name__)


@dataclasses.dataclass(unsafe_hash=True, eq=True)
class Interpreter:
    _T_hint = t.Union[float, int, str]

    hint: dataclasses.InitVar[_T_hint]
    _hint: str = dataclasses.field(init=False)

    def __post_init__(self, hint: _T_hint) -> None:
        """Normalize the data."""
        self._hint = str(hint)

    def __str__(self) -> str:
        """Return the path of the interpreter executable."""
        return repr(self)

    @functools.lru_cache()
    def version(self) -> str:
        return self.run("-V").rpartition(" ")[-1]

    def version_info(self) -> t.Tuple[int, int, int]:
        return t.cast(
            t.Tuple[int, int, int], tuple(map(int, self.version().split(".")))
        )

    @property
    def bin_path(self) -> t.Optional[Path]:
        return self.base_venv_path / "bin"

    @property
    def base_venv_site_packages_path(self) -> Path:
        return site_pkgs(self.base_venv_path, self.version_info())

    @functools.lru_cache()
    def executable(self) -> Path:
        """Return the Python interpreter path or raise.

        This defers the error until the interpeter is actually required. This is
        desirable for cases where a user might not require all the mentioned
        interpreters to be installed for their usage.
        """
        for cmd in (self._hint, f"python{self._hint}"):
            py_ex = shutil.which(cmd)
            if py_ex:
                return Path(
                    subprocess.check_output(
                        [py_ex, "-c", "import sys;print(sys.executable)"]
                    )
                    .decode()
                    .strip()
                ).resolve()

        raise FileNotFoundError(f"Python interpreter {self._hint} not found")

    @property
    def base_venv_path(self) -> Path:
        """Return the path to the virtual environment for this interpreter."""
        version = self.version().replace(".", "")

        return (
            t.cast(Path, config.riot_folder) / f"{config.venv_prefix}{version}"
        ).resolve()

    def base_venv_exists(self) -> bool:
        """Return whether the virtual environment for this interpreter exists."""
        return self.base_venv_path.exists()

    def run(self, *args: str) -> str:
        return (
            subprocess.check_output([self.executable(), *args]).decode("utf-8").strip()
        )
