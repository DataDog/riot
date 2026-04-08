from contextlib import contextmanager
import dataclasses
from hashlib import sha256
import logging
import os
from pathlib import Path
import shutil
import subprocess
import typing as t

from .constants import DEFAULT_RIOT_PATH
from .exceptions import CmdFailure
from .interpreter import Interpreter
from .runner import install_dev_pkg, run_cmd_venv
from .utils import expand_specs, pip_deps, rm_singletons, rmchars, to_list

logger = logging.getLogger(__name__)


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
                  pys=["3.8", "3.9"],
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

    venv_sitepkgs = inst.py.site_packages_path

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

    def __post_init__(self) -> None:
        """Venv instance post-initialization."""
        self.name: t.Optional[str] = self.venv.name or (
            self.parent.name if self.parent is not None else None
        )
        self.command: t.Optional[str] = self.venv.command or (
            self.parent.command if self.parent is not None else None
        )

        self.created = self.venv.create
        if self.created:
            ancestor = self.parent
            while ancestor:
                for pkg in ancestor.pkgs:
                    if pkg not in self.pkgs:
                        self.pkgs[pkg] = ancestor.pkgs[pkg]
                if ancestor.created:
                    break
                ancestor = ancestor.parent

    def matches_pattern(self, pattern: t.Pattern[str]) -> bool:
        """Return whether this VenvInstance matches the provided pattern.

        The pattern is checked against the instance ``name`` and ``short_hash``.
        """
        if self.name and pattern.match(self.name):
            return True
        return bool(pattern.match(self.short_hash))

    @property
    def prefix(self) -> t.Optional[str]:
        """Return path to directory where dependencies should be installed.

        This will return a python version + package specific path name.
        If no packages are defined it will return ``None``.
        """
        if self.py is None:
            return None

        venv_path = self.py.venv_path
        assert venv_path is not None, self

        ident = self.ident
        assert ident is not None, self
        prefix_path = "_".join((venv_path, ident))
        return (
            "_".join((venv_path, self.long_hash))[:255]
            if len(prefix_path) > 255
            else prefix_path
        )

    @property
    def venv_path(self) -> t.Optional[str]:
        # Try to take the closest created ancestor
        current: t.Optional[VenvInstance] = self
        while current:
            if current.created:
                return current.prefix
            current = current.parent

        # If no created ancestors, return the base venv path
        if self.py is not None:
            return self.py.venv_path

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
    def pkg_str(self) -> str:
        """Return pip friendly install string from defined packages."""
        return pip_deps(self.pkgs)

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
        _dir = os.path.join(DEFAULT_RIOT_PATH, "requirements")
        os.makedirs(_dir, exist_ok=True)
        in_path = os.path.join(_dir, "{}.in".format(self.short_hash))
        subprocess.check_output(
            [
                self.py.path(),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pip<26",
                "pip-tools>=7.5.0,<8",
            ],
        )
        cmd = [
            self.py.path(),
            "-m",
            "piptools",
            "compile",
            "-q",
            "--no-annotate",
            "--allow-unsafe",
            "--resolver=backtracking",
            in_path,
        ]
        logger.info(
            "Compiling requirements file %s at %s.",
            in_path,
            self.prefix,
        )
        with open(in_path, "w+b") as f:
            f.write(pkgs.encode("utf-8"))
            f.flush()

            out = subprocess.check_output(cmd)

            return out.decode("utf-8")

    @property
    def bin_path(self) -> t.Optional[str]:
        prefix = self.prefix
        if prefix is None:
            return None
        return os.path.join(prefix, "bin")

    @property
    def scriptpath(self):
        paths = []

        current: t.Optional[VenvInstance] = self
        while current is not None and not current.created:
            if current.pkgs:
                assert current.bin_path is not None, current
                paths.append(current.bin_path)
            current = current.parent

        if not self.created and self.py:
            if self.py.bin_path is not None:
                paths.append(self.py.bin_path)

        return ":".join(paths)

    @property
    def site_packages_path(self) -> t.Optional[str]:
        prefix = self.prefix
        if prefix is None:
            return None
        version = ".".join((str(_) for _ in self.py.version_info()[:2]))
        return os.path.join(prefix, "lib", f"python{version}", "site-packages")

    @property
    def site_packages_list(self) -> t.List[str]:
        """Return a list of all the site-packages paths along the parenting relation.

        The list starts with the empty string and is followed by the site-packages path
        of the current instance, then the parent site-packages paths follow.
        """
        paths = ["", os.getcwd()]  # mimick 'python -m'

        current: t.Optional[VenvInstance] = self
        while current is not None and not current.created:
            if current.pkgs:
                assert current.site_packages_path is not None, current
                paths.append(current.site_packages_path)
            current = current.parent

        if not self.created and self.py:
            if self.py.site_packages_path is not None:
                paths.append(self.py.site_packages_path)

        return paths

    @property
    def pythonpath(self) -> str:
        return ":".join(self.site_packages_list)

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

        exists = self.prefix is not None and os.path.isdir(self.prefix)

        installed = False
        if (
            py is not None
            and self.prefix is not None
            # We only install dependencies if the prefix directory does not
            # exist already. If it does exist, we assume it is in a good state.
            and (not os.path.isdir(self.prefix) or recreate or recompile_reqs)
            and not child_was_installed
        ):
            venv_path = self.venv_path
            assert venv_path is not None, py

            if self.created:
                py.create_venv(recreate, venv_path)
                if not self.venv.skip_dev_install or not skip_deps:
                    install_dev_pkg(venv_path, force=True)

            pkg_str = self.pkg_str
            compiled_requirements_file = (
                f"{DEFAULT_RIOT_PATH}/requirements/{self.short_hash}.txt"
            )
            if recompile_reqs or not os.path.exists(compiled_requirements_file):
                _ = self.requirements
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
                if self.created:
                    deps_venv_path = venv_path
                else:
                    deps_venv_path = venv_path + "_deps"
                    if not Path(deps_venv_path).exists():
                        py.create_venv(recreate=False, path=deps_venv_path)
                run_cmd_venv(deps_venv_path, cmd, env=env)
            except CmdFailure as e:
                raise CmdFailure(
                    f"Failed to install venv dependencies {pkg_str}\n{e.proc.stdout}",
                    e.proc,
                )
            else:
                installed = True

        if not self.created and self.parent is not None:
            self.parent.prepare(
                env, py, child_was_installed=installed or exists or child_was_installed
            )


@dataclasses.dataclass
class VenvInstanceResult:
    instance: VenvInstance
    venv_name: str
    code: int = 1
    output: str = ""
