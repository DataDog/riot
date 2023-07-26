from contextlib import contextmanager
import dataclasses
from hashlib import sha256
import logging
import os
from pathlib import Path
import shutil
import subprocess
import typing as t

from riot.config import config
from riot.interpreter import Interpreter
from riot.utils import CmdFailure
from riot.utils import _T_CompletedProcess
from riot.utils import _T_stdio
from riot.utils import expand_specs
from riot.utils import join_paths
from riot.utils import pip_deps
from riot.utils import rm_singletons
from riot.utils import rmchars
from riot.utils import run_cmd
from riot.utils import site_pkgs
from riot.utils import to_list


logger = logging.getLogger(__name__)


class VenvError(Exception):
    pass


ALWAYS_PASS_ENV = {
    "LANG",
    "LANGUAGE",
    "SSL_CERT_FILE",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "PIP_INDEX_URL",
    "PATH",
}


@dataclasses.dataclass
class VirtualEnv:
    py: Interpreter
    path: Path

    def create(self, force: bool = False) -> None:
        """Attempt to create a virtual environment for this intepreter."""
        if self.path is None:
            raise ValueError("No path for virtual environment instance")

        if self.path.exists():
            if not force:
                logger.info(
                    "Skipping creation of virtualenv '%s' as it already exists.",
                    self.path,
                )
                return

            logger.info("Deleting virtualenv '%'", self.path)
            shutil.rmtree(str(self.path))

        py_ex = self.py.executable()
        logger.info("Creating virtualenv '%s' with interpreter '%s'", self.path, py_ex)

        run_cmd(
            ["virtualenv", f"--python={py_ex}", str(self.path)],
            stdout=subprocess.PIPE,
        )

    def run(
        self,
        args: str,
        stdout: _T_stdio = subprocess.PIPE,
        executable: t.Optional[str] = None,
        env: t.Optional[t.Dict[str, str]] = None,
    ) -> _T_CompletedProcess:
        """Run command in the virtual environment.

        Replicate what virtualenv does to activate the virtual environment.
        """
        env = {} if env is None else env.copy()

        abs_venv = str(self.path.resolve())
        env["VIRTUAL_ENV"] = abs_venv
        env["PATH"] = join_paths((self.path / "bin").resolve(), env.get("PATH"))

        try:
            # Ensure that we have the venv site-packages in the PYTHONPATH so
            # that the installed dev package depdendencies are available.
            env["PYTHONPATH"] = join_paths(env.get("PYTHONPATH"), site_pkgs(self.path))
        except StopIteration:
            pass

        env.update(
            {
                k: os.environ[k]
                for k in ALWAYS_PASS_ENV
                if k in os.environ and k not in env
            }
        )

        env_str = " ".join(f"{k}={v}" for k, v in env.items())

        logger.debug("Executing command '%s' with environment '%s'", args, env_str)

        return run_cmd(args, stdout=stdout, executable=executable, env=env, shell=True)

    def install(self):
        if not any(Path(_).exists() for _ in {"setup.py", "pyproject.toml"}):
            logger.warning(
                "No Python setup file found. Skipping dev package installation."
            )
            return

        logger.info("Installing dev package (edit mode) in %s.", self.path)

        self.run(
            "pip --disable-pip-version-check install -e .",
            env=os.environ,
        )

    def exists(self):
        return self.path.exists()


@dataclasses.dataclass
class Venv:
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
        create (bool): Create the virtual environment instance. Defaults to ``False``, in which case only a prefix is created.
    """

    pys: dataclasses.InitVar[
        t.Union[Interpreter._T_hint, t.List[Interpreter._T_hint]]
    ] = None
    pkgs: dataclasses.InitVar[t.Dict[str, t.Union[str, t.List[str]]]] = None
    env: dataclasses.InitVar[t.Dict[str, t.Union[str, t.List[str]]]] = None
    name: t.Optional[str] = None
    command: t.Optional[str] = None
    venvs: t.List["Venv"] = dataclasses.field(default_factory=list)
    create: bool = False
    skip_dev_install: bool = False

    def __post_init__(self, pys, pkgs, env):
        """Normalize the data."""
        self.pys = [Interpreter(py) for py in to_list(pys)] if pys is not None else []
        self.pkgs = rm_singletons(pkgs) if pkgs else {}
        self.env = rm_singletons(env) if env else {}

    def instances(
        self,
        parent_inst: t.Optional["VenvInstance"] = None,
    ) -> t.Generator["VenvInstance", None, None]:
        # Expand out the instances for the venv.
        for env_spec in expand_specs(self.env):  # type: ignore[attr-defined]
            # Bubble up env
            env = parent_inst.env.copy() if parent_inst else {}
            env.update(dict(env_spec))

            # Bubble up pys
            pys = self.pys or [parent_inst.py if parent_inst else None]  # type: ignore[attr-defined]

            for py in pys:
                for pkgs in expand_specs(self.pkgs):  # type: ignore[attr-defined]
                    inst = VenvInstance(
                        # Bubble up name and command if not overridden
                        venv=self,
                        py=py,
                        env=env,
                        pkgs=dict(pkgs),
                        parent=parent_inst,
                    )
                    if not self.venvs:
                        yield inst
                    else:
                        for venv in self.venvs:
                            yield from venv.instances(inst)


@contextmanager
def nspkgs(inst: "VenvInstance") -> t.Generator[None, None, None]:
    src_ns_files = {}
    dst_ns_files = []
    moved_ns_files = []

    venv_sitepkgs = inst.py.base_venv_site_packages_path

    # Collect the namespaces to copy over
    for sitepkgs in (_ for _ in inst.site_packages_list[2:] if _ != venv_sitepkgs):
        try:
            for ns in (_ for _ in os.listdir(sitepkgs) if _.endswith("nspkg.pth")):
                if ns not in src_ns_files:
                    src_ns_files[ns] = sitepkgs
        except FileNotFoundError:
            pass

    # Copy over the namespaces
    for ns, src_sitepkgs in src_ns_files.items():
        src_ns_path = os.path.join(src_sitepkgs, ns)
        dst_ns_path = os.path.join(venv_sitepkgs, ns)

        # if the destination file exists already we make a backup copy as it
        # belongs to the base venv and we don't want to overwrite it
        if os.path.isfile(dst_ns_path):
            shutil.move(dst_ns_path, dst_ns_path + ".bak")
            moved_ns_files.append(dst_ns_path)

        with open(src_ns_path) as ns_in, open(dst_ns_path, "w") as ns_out:
            # https://github.com/pypa/setuptools/blob/b62705a84ab599a2feff059ececd33800f364555/setuptools/namespaces.py#L44
            # TODO: Cache the file content to avoid re-reading it
            ns_out.write(
                ns_in.read().replace(
                    "sys._getframe(1).f_locals['sitedir']",
                    f"'{src_sitepkgs}'",
                )
            )

        dst_ns_files.append(dst_ns_path)

    yield

    # Clean up the base venv
    for ns_file in dst_ns_files:
        os.remove(ns_file)

    for ns_file in moved_ns_files:
        shutil.move(ns_file + ".bak", ns_file)


@dataclasses.dataclass
class VenvInstance:
    venv: Venv
    pkgs: t.Dict[str, str]
    py: Interpreter
    env: t.Dict[str, str]
    parent: t.Optional["VenvInstance"] = None

    name: t.Optional[str] = dataclasses.field(init=False)
    command: t.Optional[str] = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        """Venv instance post-initialization."""
        self.name = self._inherited("name")
        self.command = self._inherited("command")

        if self.venv.create:
            # If the venv is marked as create, then we need to make sure that
            # all of the packages from acestor venv instances are installed.
            ancestor = self.parent
            while ancestor:
                for pkg in ancestor.pkgs:
                    if pkg not in self.pkgs:
                        self.pkgs[pkg] = ancestor.pkgs[pkg]
                if ancestor.venv.create:
                    break
                ancestor = ancestor.parent

    def _inherited(self, attr: str) -> t.Optional[t.Any]:
        return getattr(self.venv, attr) or (
            getattr(self.parent, attr) if self.parent is not None else None
        )

    def matches_pattern(self, pattern: t.Pattern[str]) -> bool:
        """Return whether this VenvInstance matches the provided pattern.

        The pattern is checked against the instance ``name`` and ``short_hash``.
        """
        return (
            True
            if self.name and pattern.match(self.name)
            else bool(pattern.match(self.short_hash))
        )

    @property
    def prefix(self) -> t.Optional[Path]:
        """Return path to directory where dependencies should be installed.

        This will return a python version + package specific path name.
        If no packages are defined it will return ``None``.
        """
        if self.py is None:
            return None

        venv_path: Path = self.py.base_venv_path
        assert venv_path is not None, self

        ident = self.ident
        assert ident is not None, self

        prefix_path = venv_path.parent / "_".join((venv_path.name, ident))

        return (
            venv_path.parent / "_".join((venv_path.name, self.short_hash))
            if len(str(prefix_path)) > 255
            else prefix_path
        )

    @property
    def venv_path(self) -> t.Optional[Path]:
        # Try to take the closest created ancestor
        current: t.Optional[VenvInstance] = self
        while current:
            if current.venv.create:
                return current.prefix
            current = current.parent

        # If no created ancestors, return the base venv path
        if self.py is not None:
            return self.py.base_venv_path

        return None

    @property
    def ident(self) -> t.Optional[str]:
        """Return prefix identifier string based on packages."""
        return "_".join(
            (
                f"{rmchars('<=>.,:+@/', n)}"
                for n in self.full_pkg_str.replace("'", "").split()
            )
        )

    @property
    def full_pkg_str(self) -> str:
        """Return pip friendly install string from defined packages."""
        chain: t.List[VenvInstance] = [self]
        current: t.Optional[VenvInstance] = self
        while current is not None:
            chain.insert(0, current)
            current = current.parent

        pkgs: t.Dict[str, str] = {}
        for inst in chain:
            pkgs.update(dict(inst.pkgs))

        return pip_deps(pkgs)

    @property
    def long_hash(self) -> str:
        return hex(hash(self))[2:]

    @property
    def short_hash(self) -> str:
        return self.long_hash[:7]

    def __hash__(self):
        """Compute a hash for the venv instance."""
        h = sha256()
        h.update(repr(self.name).encode())
        h.update(repr(self.py).encode())
        h.update(self.full_pkg_str.encode())
        return int(h.hexdigest(), 16)

    @property
    def requirements(self) -> str:
        """Requirements for dependencies with pinned versions."""
        # Transform full_pkg_str into requirements.in format
        pkgs = "\n".join(self.full_pkg_str.replace("'", "").split(" "))
        _dir: Path = config.riot_folder / "requirements"
        _dir.mkdir(parents=True, exist_ok=True)

        in_path = (_dir / self.short_hash).with_suffix(".in")

        self.py.run("-m", "pip", "install", "pip-tools")

        if self.py.version_info() < (3, 8):
            self.py.run("-m", "pip", "install", "-U", "pip<23.2")

        cmd = [
            "-m",
            "piptools",
            "compile",
            "-q",
            "--no-annotate",
            str(in_path),
        ]
        if self.py.version_info() >= (3, 7):
            cmd.append("--resolver=backtracking")

        logger.info("Compiling requirements file %s at %s.", in_path, self.prefix)

        in_path.write_bytes(pkgs.encode("utf-8"))

        return self.py.run(*cmd)

    @property
    def path(self) -> str:
        paths = []

        current: t.Optional[VenvInstance] = self
        while current is not None and not current.venv.create:
            if current.pkgs:
                assert current.prefix is not None, current
                paths.append(current.prefix / "bin")
            current = current.parent

        if not self.venv.create and self.py:
            if self.py.bin_path is not None:
                paths.append(self.py.bin_path)

        return join_paths(*paths)

    @property
    def site_packages_list(self) -> t.List[Path]:
        """Return a list of all the site-packages paths along the parenting relation.

        The list starts with the empty string and is followed by the site-packages path
        of the current instance, then the parent site-packages paths follow.
        """
        paths = [Path(""), Path.cwd()]  # mimick 'python -m'

        current: t.Optional[VenvInstance] = self
        while current is not None and not current.venv.create:
            if current.pkgs:
                assert current.prefix is not None, current
                paths.append(site_pkgs(current.prefix, self.py.version_info()))
            current = current.parent

        if not self.venv.create and self.py:
            if self.py.base_venv_site_packages_path is not None:
                paths.append(self.py.base_venv_site_packages_path)

        return paths

    @property
    def pythonpath(self) -> str:
        return join_paths(*self.site_packages_list)

    def match_venv_pattern(self, pattern: t.Pattern[str]) -> bool:
        current: t.Optional[VenvInstance] = self
        idents = []
        while current is not None:
            ident = current.ident
            if ident is not None:
                idents.append(ident)
            current = current.parent

        if not idents:
            return True

        return bool(pattern.search("_".join(idents[::-1])))

    def prepare(
        self,
        env: t.Dict[str, str],
        py: t.Optional[Interpreter] = None,
        recreate: bool = False,
        skip_deps: bool = False,
        recompile_reqs: bool = False,
        child_was_installed: bool = False,
    ) -> None:
        # Propagate the interpreter down the parenting relation
        self.py = py = py or self.py
        if recompile_reqs:
            recreate = True

        exists = self.prefix is not None and self.prefix.exists()

        installed = False
        if (
            py is not None
            and self.prefix is not None
            # We only install dependencies if the prefix directory does not
            # exist already. If it does exist, we assume it is in a good state.
            and (not self.prefix.exists() or recreate or recompile_reqs)
            and not child_was_installed
        ):
            venv_path = self.venv_path
            assert venv_path is not None, py

            virtualenv = VirtualEnv(py, venv_path)

            if self.venv.create:
                virtualenv.create()
                if not self.venv.skip_dev_install:
                    virtualenv.install()

            pkg_str = pip_deps(self.pkgs)
            assert pkg_str is not None
            compiled_requirements_file: Path = (
                config.riot_folder / "requirements" / self.short_hash
            ).with_suffix(".txt")
            if recompile_reqs or not compiled_requirements_file.exists():
                self.requirements
            cmd = (
                f"pip --disable-pip-version-check install --prefix '{self.prefix}' --no-warn-script-location "
                f"-r {compiled_requirements_file}"
            )
            logger.info(
                "Installing venv dependencies %s at %s.",
                compiled_requirements_file,
                self.prefix,
            )
            try:
                if self.venv.create:
                    deps_virtualenv = VirtualEnv(py, venv_path)
                    assert deps_virtualenv.exists()
                else:
                    deps_venv_path = venv_path.parent / "_".join(
                        (venv_path.name, "deps")
                    )
                    deps_virtualenv = VirtualEnv(py, deps_venv_path)
                    deps_virtualenv.create()
                    if py.version_info() < (3,):
                        # Use the same binary. This is necessary for Python 2.7
                        deps_bin = (deps_venv_path / "bin" / "python").resolve()
                        venv_bin = (venv_path / "bin" / "python").resolve()
                        deps_bin.unlink()
                        deps_bin.symlink_to(venv_bin)
                deps_virtualenv.run(cmd, env=env)
            except CmdFailure as e:
                raise CmdFailure(
                    f"Failed to install venv dependencies {pkg_str}\n{e.proc.stdout}",
                    e.proc,
                )
            else:
                installed = True

        if not self.venv.create and self.parent is not None:
            self.parent.prepare(
                env, py, child_was_installed=installed or exists or child_was_installed
            )


@dataclasses.dataclass
class VenvInstanceResult:
    instance: VenvInstance
    venv_name: str
    code: int = 1
    output: str = ""
