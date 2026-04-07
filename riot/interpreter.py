import dataclasses
import functools
import logging
import os
import shutil
import subprocess
import sys
import typing as t

from .constants import DEFAULT_RIOT_ENV_PREFIX, DEFAULT_RIOT_PATH
from .runner import run_cmd

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
        path = self.path()

        output = subprocess.check_output(
            [
                path,
                "-c",
                'import sys; print("%s.%s.%s" % (sys.version_info.major, sys.version_info.minor, sys.version_info.micro))',
            ],
        )
        return output.decode().strip()

    @functools.lru_cache()
    def version_info(self) -> t.Tuple[int, int, int]:
        return t.cast(
            t.Tuple[int, int, int], tuple(map(int, self.version().split(".")))
        )

    @property
    def bin_path(self) -> t.Optional[str]:
        return os.path.join(self.venv_path, "bin")

    @property
    def site_packages_path(self) -> str:
        version = ".".join((str(_) for _ in self.version_info()[:2]))
        return os.path.join(self.venv_path, "lib", f"python{version}", "site-packages")

    @functools.lru_cache()
    def path(self) -> str:
        """Return the Python interpreter path or raise.

        This defers the error until the interpeter is actually required. This is
        desirable for cases where a user might not require all the mentioned
        interpreters to be installed for their usage.
        """
        py_ex = shutil.which(self._hint)

        if not py_ex:
            py_ex = shutil.which(f"python{self._hint}")

        if py_ex:
            # Ensure that we are getting the path of the actual executable,
            # rather than some wrapping shell script.
            return os.path.abspath(
                subprocess.check_output(
                    [py_ex, "-c", "import sys;print(sys.executable)"]
                )
                .decode()
                .strip()
            )

        raise FileNotFoundError(f"Python interpreter {self._hint} not found")

    @property
    def venv_path(self) -> str:
        """Return the path to the virtual environment for this interpreter."""
        version = self.version().replace(".", "")
        env_base_path = os.environ.get("RIOT_ENV_BASE_PATH", DEFAULT_RIOT_PATH)
        return os.path.abspath(
            os.path.join(env_base_path, f"{DEFAULT_RIOT_ENV_PREFIX}{version}")
        )

    def exists(self) -> bool:
        """Return whether the virtual environment for this interpreter exists."""
        return os.path.isdir(self.venv_path)

    def create_venv(self, recreate: bool, path: t.Optional[str] = None) -> None:
        """Attempt to create a virtual environment for this intepreter.

        Returns ``True`` if the virtual environment was created or ``False`` if
        it already existed.
        """
        venv_path: str = path or self.venv_path

        if os.path.isdir(venv_path):
            if not recreate:
                logger.info(
                    "Skipping creation of virtualenv '%s' as it already exists.",
                    venv_path,
                )
                return
            logger.info("Deleting virtualenv '%s'", venv_path)
            shutil.rmtree(venv_path)

        py_ex = self.path()
        logger.info("Creating virtualenv '%s' with interpreter '%s'.", venv_path, py_ex)
        run_cmd(
            [sys.executable, "-m", "virtualenv", f"--python={py_ex}", venv_path],
            stdout=subprocess.PIPE,
        )
