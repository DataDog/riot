import dataclasses
import functools
import logging
import os.path
import shutil
import subprocess
import typing as t

from riot.utils import run_cmd

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
            return py_ex

        raise FileNotFoundError(f"Python interpreter {self._hint} not found")

    @property
    def venv_path(self) -> str:
        """Return the path to the virtual environment for this interpreter."""
        version = self.version().replace(".", "")
        return os.path.abspath(f".riot/venv_py{version}")

    def create_venv(self, recreate: bool) -> str:
        """Attempt to create a virtual environment for this intepreter."""
        path: str = self.venv_path

        if os.path.isdir(path) and not recreate:
            logger.info(
                "Skipping creation of virtualenv '%s' as it already exists.", path
            )
            return path

        py_ex = self.path()
        logger.info("Creating virtualenv '%s' with interpreter '%s'.", path, py_ex)
        run_cmd(["virtualenv", f"--python={py_ex}", path], stdout=subprocess.PIPE)
        return path
