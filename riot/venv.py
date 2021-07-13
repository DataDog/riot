import dataclasses
import logging
import os.path
import subprocess
import typing as t

from riot.interpreter import Interpreter
from riot.utils import (
    CmdFailure,
    expand_specs,
    get_pep_dep,
    rm_singletons,
    rmchars,
    run_cmd,
    run_cmd_venv,
    to_list,
)

logger = logging.getLogger(__name__)


class VenvError(Exception):
    pass


@dataclasses.dataclass
class Venv:
    pkgs: t.Tuple[t.Tuple[str, str]]
    py: t.Optional[Interpreter]
    parent: t.Optional["Venv"] = None

    @property
    def venv_path(self) -> t.Optional[str]:
        """Return path to directory of the venv this instance should use.

        This will return a python version + package specific venv path name.

        If no packages are defined it will return the ``Interpreter.venv_path``.
        """
        if self.py is None:
            return None

        venv_path = self.py.venv_path
        if self.needs_venv:
            venv_path = "_".join(
                [venv_path] + [f"{n}{rmchars('<=>.,', v)}" for n, v in self.pkgs]
            )
        return venv_path

    @property
    def target(self) -> t.Optional[str]:
        if self.venv_path is None:
            return None
        return os.path.join(self.venv_path, "target")

    @property
    def needs_venv(self) -> bool:
        """Whether this ``VenvInstance`` needs its own venv or not."""
        return bool(self.pkg_str)

    @property
    def pkg_str(self) -> str:
        """Return pip friendly install string from defined packages."""
        return " ".join(
            [
                f"'{get_pep_dep(lib, version)}'"
                for lib, version in self.pkgs
                if version is not None
            ]
        )

    @property
    def scriptpath(self):
        paths = []
        current = self
        while current is not None:
            if current.needs_venv:
                assert current.target is not None, current
                paths.append(os.path.join(current.target, "bin"))
            current = current.parent
        return ":".join(paths)

    @property
    def pythonpath(self):
        paths = []
        current = self
        while current is not None:
            if current.needs_venv:
                assert current.target is not None, current
                version = ".".join((str(_) for _ in self.py.version_info()[:2]))
                paths.append(
                    os.path.join(
                        current.target, "lib", f"python{version}", "site-packages"
                    )
                )
            current = current.parent
        return ":".join(paths)

    def prepare(
        self, env: t.Dict[str, str], py: t.Optional[Interpreter] = None
    ) -> None:
        # Propagate the interpreter down the parenting relation
        self.py = py = py or self.py

        if py is not None:
            venv_path = self.venv_path
            if venv_path is None:
                return

            if self.needs_venv:

                py_ex = py.path()
                logger.info(
                    "Creating virtualenv '%s' with interpreter '%s'.",
                    self.venv_path,
                    py_ex,
                )

                try:
                    run_cmd(
                        ["virtualenv", f"--python={py_ex}", venv_path],
                        stdout=subprocess.PIPE,
                    )
                except FileNotFoundError:
                    raise VenvError("Base virtualenv '%s' does not exist", venv_path)

                except FileExistsError:
                    # Assume the venv already exists and works fine
                    logger.info(
                        "Virtualenv '%s' already exists and assumed to be OK",
                        self.venv_path,
                    )
                else:
                    if self.pkg_str:
                        logger.info("Installing venv dependencies %s.", self.pkg_str)
                        try:
                            run_cmd_venv(
                                venv_path,
                                f"pip --disable-pip-version-check install --prefix {self.target} --no-warn-script-location {self.pkg_str}",
                                env=env,
                            )
                        except CmdFailure as e:
                            raise CmdFailure(
                                f"Failed to install venv dependencies {self.pkg_str}\n{e.proc.stdout}",
                                e.proc,
                            )
        if self.parent is not None:
            self.parent.prepare(env, py)


@dataclasses.dataclass
class VenvSpec:
    """Specifies how to build and run a virtual environment.

    Venvs can be nested to benefit from inheriting from a parent Venv. All
    attributes are passed down to child Venvs. The child Venvs can override
    parent attributes with the semantics defined below.

    Example::

        Venv(
          pys=[3.9],
          venvs=[
              Venv(
                  name="mypy",
                  command="mypy",
                  pkgs={
                      "mypy": "==0.790",
                  },
              ),
              Venv(
                  name="test",
                  pys=["3.7", "3.8", "3.9"],
                  command="pytest",
                  pkgs={
                      "pytest": "==6.1.2",
                  },
              ),
          ])

    Args:
        name (str): Name of the instance. Overrides parent value.
        command (str): Command to run in the virtual environment. Overrides parent value.
        pys  (List[float]): Python versions. Overrides parent value.
        pkgs (Dict[str, Union[str, List[str]]]): Packages and version(s) to install into the virtual env. Merges and overrides parent values.
        env  (Dict[str, Union[str, List[str]]]): Environment variables to define in the virtual env. Merges and overrides parent values.
        venvs (List[Venv]): List of Venvs that inherit the properties of this Venv (unless they are overridden).
    """

    pys: dataclasses.InitVar[
        t.Union[Interpreter._T_hint, t.List[Interpreter._T_hint]]
    ] = None
    pkgs: dataclasses.InitVar[t.Dict[str, t.Union[str, t.List[str]]]] = None
    venvs: t.List["VenvSpec"] = dataclasses.field(default_factory=list)

    def __post_init__(self, pys, pkgs):
        """Normalize the data."""
        self.pys = [Interpreter(py) for py in to_list(pys)] if pys is not None else []
        self.pkgs = rm_singletons(pkgs) if pkgs else {}

    def instances(
        self,
        pys: t.List[Interpreter] = [],
        parent_venv: t.Optional[Venv] = None,
    ) -> t.Generator[Venv, None, None]:
        pys = pys or self.pys or [None]
        for py in pys:
            for ps in expand_specs(self.pkgs):
                venv = Venv(
                    py=py,
                    pkgs=ps,
                    parent=parent_venv,
                )
                if not self.venvs:
                    yield venv
                else:
                    for spec in self.venvs:
                        for child_venv in spec.instances(
                            pys if pys != [None] else [], venv  # type: ignore[arg-type]
                        ):
                            if child_venv is not None:
                                yield child_venv
