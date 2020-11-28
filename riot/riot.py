import dataclasses
import importlib.abc
import importlib.util
import itertools
import logging
import os
import shutil
import subprocess
import sys
import traceback
import typing as t


logger = logging.getLogger(__name__)

SHELL = "/bin/bash"
ENCODING = sys.getdefaultencoding()


if t.TYPE_CHECKING or sys.version_info[:2] >= (3, 9):
    _T_CompletedProcess = subprocess.CompletedProcess[str]
else:
    _T_CompletedProcess = subprocess.CompletedProcess


_T_stdio = t.Union[None, int, t.IO[t.Any]]
_K = t.TypeVar("_K")
_V = t.TypeVar("_V")


@dataclasses.dataclass(frozen=True, eq=True)
class VE:
    path: str
    interp: "Interpreter"

    def bin_dir(self) -> str:
        return os.path.join(self.path, "bin")

    def site_packages_dir(self, d: str = "site-packages") -> str:
        # TODO
        # version = self.version()
        # sp_dir = os.path.join(path, "lib", f"python{version}", d)
        sp_dir = os.path.join(self.path, "lib", "python3.8", "site-packages")
        return sp_dir

    # def path_env_var(self) -> str:
    #     env_path = os.environ.get("PATH", "")
    #     return os.pathsep.join((os.path.join(self.path, "bin"), env_path))

    def create(self) -> None:
        if os.path.isdir(self.path):
            return
        py_ex = self.interp.exc_path()
        run_cmd(f"virtualenv --python={py_ex} {self.path}", stdout=subprocess.PIPE)

    def run(self, args: str, env: t.Dict[str, str] = {},
        stdout: _T_stdio = subprocess.PIPE,
            ) -> _T_CompletedProcess:
        ves = [self] + [self.interp._ve]
        pythonpath = os.pathsep.join([ve.site_packages_dir() for ve in ves])
        path = os.pathsep.join([ve.bin_dir() for ve in ves] + [os.environ.get("PATH", "")])
        env = env.copy()
        env.update(dict(
            PATH=path, PYTHONPATH=pythonpath
            ))
        return run_cmd(args, env=env, stdout=stdout)


def rm_singletons(d: t.Dict[_K, t.Union[_V, t.List[_V]]]) -> t.Dict[_K, t.List[_V]]:
    """Convert single values in a dictionary to a list with that value.

    >>> rm_singletons({ "k": "v" })
    {'k': ['v']}
    >>> rm_singletons({ "k": ["v"] })
    {'k': ['v']}
    >>> rm_singletons({ "k": ["v", "x", "y"] })
    {'k': ['v', 'x', 'y']}
    >>> rm_singletons({ "k": [1, 2, 3] })
    {'k': [1, 2, 3]}
    """
    return {k: to_list(v) for k, v in d.items()}


def to_list(x: t.Union[_K, t.List[_K]]) -> t.List[_K]:
    """Convert a single value to a list containing that value.

    >>> to_list(["x", "y", "z"])
    ['x', 'y', 'z']
    >>> to_list(["x"])
    ['x']
    >>> to_list("x")
    ['x']
    >>> to_list(1)
    [1]
    """
    return [x] if not isinstance(x, list) else x


@dataclasses.dataclass(unsafe_hash=True, eq=True)
class Interpreter:
    _T_hint = t.Union[float, int, str]

    hint: dataclasses.InitVar[_T_hint] = dataclasses.field(compare=False, hash=False, repr=False)
    _hint: str = dataclasses.field(init=False, hash=True, compare=True, repr=True)
    _ve: VE = dataclasses.field(init=False, hash=False, compare=False, repr=False)

    def __post_init__(self, hint: _T_hint) -> None:
        """Normalize the data."""
        self._hint = str(hint)
        self._ve = VE(self.venv_path(), self)

    def __str__(self) -> str:
        """Return the path of the interpreter executable."""
        return repr(self.exc_path())

    def version(self) -> str:
        path = self.exc_path()
        output = subprocess.check_output([path, "--version"])
        version = output.decode().strip().split(" ")[1]
        return version

    def exc_path(self) -> str:
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

        raise FileNotFoundError(f"Python interpreter for '{self._hint}' not found.")

    def venv_path(self) -> str:
        """Return the path to the virtual environment for this interpreter."""
        version = self.version().replace(".", "")
        return os.path.abspath(os.path.join(".riot", f".venv_py{version}"))

    def create_venv(self, recreate: bool, install_local: bool) -> None:
        """Create a virtual environment for this intepreter."""
        self._ve.create()

        if install_local:
            logger.info("Installing dev package.")
            try:
                pass
                # self._ve.run("pip --disable-pip-version-check install -e .")
            except CmdFailure as e:
                logger.error("Dev install failed, aborting!\n%s", e.proc.stdout)
                sys.exit(1)


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
    """

    pys: dataclasses.InitVar[t.List[Interpreter]] = None
    pkgs: dataclasses.InitVar[t.Dict[str, t.List[str]]] = None
    env: dataclasses.InitVar[t.Dict[str, t.List[str]]] = None
    name: t.Optional[str] = None
    command: t.Optional[str] = None
    venvs: t.List["Venv"] = dataclasses.field(default_factory=list)

    def __post_init__(self, pys, pkgs, env):
        """Normalize the data."""
        self.pys = [Interpreter(py) for py in to_list(pys)] if pys is not None else []
        self.pkgs = rm_singletons(pkgs) if pkgs else {}
        self.env = rm_singletons(env) if env else {}

    def resolve(self, parents: t.List["Venv"]) -> "Venv":
        if not parents:
            return self
        else:
            venv = Venv()
            for parent in parents + [self]:
                if parent.name:
                    venv.name = parent.name
                if parent.pys:
                    venv.pys = parent.pys
                if parent.command:
                    venv.command = parent.command
                venv.env.update(parent.env)
                venv.pkgs.update(parent.pkgs)
            return venv

    def instances(
        self,
        pattern: t.Pattern[str],
        parents: t.List["Venv"] = [],
    ) -> t.Generator["VenvInstance", None, None]:
        for venv in self.venvs:
            if venv.name and not pattern.match(venv.name):
                logger.debug("Skipping venv '%s' due to mismatch.", venv.name)
                continue
            else:
                for inst in venv.instances(parents=parents + [self], pattern=pattern):
                    if inst:
                        yield inst
        else:
            resolved = self.resolve(parents)

            # If the venv doesn't have a command or python then skip it.
            if not resolved.command or not resolved.pys:
                logger.debug("Skipping venv %r as it's not runnable.", self)
                return

            # Expand out the instances for the venv.
            for env in expand_specs(resolved.env):
                for py in resolved.pys:
                    for pkgs in expand_specs(resolved.pkgs):
                        yield VenvInstance(
                            name=resolved.name,
                            command=resolved.command,
                            py=py,
                            env=env,
                            pkgs=pkgs,
                        )


@dataclasses.dataclass
class VenvInstance:
    command: str
    env: t.Tuple[t.Tuple[str, str]]
    name: t.Optional[str]
    pkgs: t.Tuple[t.Tuple[str, str]]
    py: Interpreter
    _ve: VE = dataclasses.field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the virtual environment."""
        self._ve = VE(self.venv_path(), self.py)

    def venv_name(self) -> str:
        # FIXME[kyle] confirm or make this safe/unique for all possible versions.
        return "_".join([f"{n}{rmchars('<=>.,', v)}" for n, v in self.pkgs])

    def venv_path(self) -> str:
        """Return path to directory of the instance."""
        base_path = self.py.venv_path()
        name = self.venv_name()
        return f"{base_path}_{name}"

    def install(self) -> None:
        py_ex = self.py.exc_path()
        path = self.venv_path()
        if not os.path.isdir(path):
            logger.info("Creating virtualenv '%s' with interpreter '%s'.", path, py_ex)
            run_cmd(f"virtualenv --python={py_ex} {path}", stdout=subprocess.PIPE)

        # Resolve the packages required for this instance.
        pkgs: t.Dict[str, str] = {
            n: v for n, v in self.pkgs if v is not None
        }
        pkg_str = " ".join(
            [f"{get_pep_dep(lib, version)}" for lib, version in pkgs.items()]
        )
        env_path = os.environ.get("PATH", "")
        env_path = os.pathsep.join((os.path.join(self.venv_path(), "bin"), path))
        logger.info("Installing venv dependencies %s.", pkg_str)
        run_cmd(f"pip --disable-pip-version-check install {pkg_str}", env=dict(
            PATH=env_path,
        ))


@dataclasses.dataclass
class VenvInstanceResult:
    instance: VenvInstance
    code: int = 1


class CmdFailure(Exception):
    def __init__(self, msg, completed_proc):
        self.msg = msg
        self.proc = completed_proc
        self.code = completed_proc.returncode
        super().__init__(self, msg)


@dataclasses.dataclass
class Session:
    venv: Venv

    @classmethod
    def from_config_file(cls, path: str) -> "Session":
        spec = importlib.util.spec_from_file_location("riotfile", path)
        if not spec:
            raise Exception(
                f"Invalid file format for riotfile. Expected file with .py extension got '{path}'."
            )
        config = importlib.util.module_from_spec(spec)

        # DEV: MyPy has `ModuleSpec.loader` as `Optional[_Loader`]` which doesn't have `exec_module`
        # https://github.com/python/typeshed/blob/fe58699ca5c9ee4838378adb88aaf9323e9bbcf0/stdlib/3/_importlib_modulespec.pyi#L13-L44
        try:
            t.cast(importlib.abc.Loader, spec.loader).exec_module(config)
        except Exception as e:
            raise Exception(
                f"Failed to parse riotfile '{path}'.\n{traceback.format_exc()}"
            ) from e
        else:
            venv = getattr(config, "venv", Venv())
            return cls(venv=venv)

    def run(
        self,
        pattern: t.Pattern[str],
        venv_pattern: t.Pattern[str],
        skip_base_install: bool = False,
        recreate_venvs: bool = False,
        out: t.TextIO = sys.stdout,
        pass_env: bool = False,
        cmdargs: t.Optional[t.Sequence[str]] = None,
        pythons: t.Optional[t.Set[Interpreter]] = None,
    ) -> None:
        results = []

        self.ensure_base_venvs(
            pattern,
            recreate=recreate_venvs,
            pythons=pythons,
            skip_dev_install=skip_base_install,
        )

        for inst in self.venv.instances(pattern=pattern):
            if pythons and inst.py not in pythons:
                logger.debug(
                    "Skipping venv instance %s due to interpreter mismatch", inst
                )
                continue

            # Result which will be updated with the test outcome.
            result = VenvInstanceResult(instance=inst)

            try:
                try:
                    inst.install()
                except CmdFailure as e:
                    raise CmdFailure(
                        f"Failed to install venv dependencies\n{e.proc.stdout}",
                        e.proc,
                    )

                # Generate the environment for the instance.
                env = os.environ.copy() if pass_env else {}

                # Add in the instance env vars.
                env.update(dict(inst.env))

                # Finally, run the test in the venv.
                if cmdargs is not None:
                    inst.command = inst.command.format(cmdargs=(" ".join(cmdargs)))
                env_str = " ".join(f"{k}={v}" for k, v in env.items())
                logger.info(
                    "Running command '%s' with environment '%s'.", inst.command, env_str
                )
                try:
                    # Pipe the command output directly to `out` since we
                    # don't need to store it.
                    inst._ve.run(inst.command, stdout=out, env=env)
                except CmdFailure as e:
                    raise CmdFailure(
                        f"Test failed with exit code {e.proc.returncode}", e.proc
                    )
            except CmdFailure as e:
                result.code = e.code
                print(e.msg, file=out)
            except KeyboardInterrupt:
                result.code = 1
                break
            except Exception:
                logger.error("Test runner failed", exc_info=True)
                sys.exit(1)
            else:
                result.code = 0
            finally:
                results.append(result)

        print("\n-------------------summary-------------------", file=out)
        for r in results:
            failed = r.code != 0
            status_char = "✖️" if failed else "✔️"
            env_str = env_to_str(r.instance.env)
            s = f"{status_char}  {r.instance.name}: {env_str} {r.instance.py}"
            print(s, file=out)

        if any(True for r in results if r.code != 0):
            sys.exit(1)

    def list_venvs(self, pattern, venv_pattern, pythons=None, out=sys.stdout):
        for inst in self.venv.instances(pattern=pattern):
            if pythons and inst.py not in pythons:
                continue

            if not venv_pattern.search(inst.venv_path()):
                continue
            pkgs_str = " ".join(
                f"'{get_pep_dep(name, version)}'" for name, version in inst.pkgs
            )
            env_str = env_to_str(inst.env)
            py_str = f"{inst.py}"
            print(f"{inst.name} {env_str} {py_str} {pkgs_str}", file=out)

    def ensure_base_venvs(
        self,
        pattern: t.Pattern[str],
        recreate: bool,
        pythons: t.Optional[t.Set[Interpreter]],
        skip_dev_install: bool,
    ) -> None:
        """Generate all the required base venvs."""
        # Find all the python interpreters used.
        required_pys: t.Set[Interpreter] = set(
            [inst.py for inst in self.venv.instances(pattern)]
        )
        # Apply Python filters.
        if pythons:
            required_pys = required_pys.intersection(pythons)

        logger.info(
            "Generating virtual environments for interpreters %s",
            ",".join(str(s) for s in required_pys),
        )

        for py in required_pys:
            try:
                py.create_venv(recreate, skip_dev_install)
            except CmdFailure as e:
                logger.error("Failed to create virtual environment.\n%s", e.proc.stdout)
            except FileNotFoundError:
                logger.error("Python version '%s' not found.", py)


def rmchars(chars: str, s: str) -> str:
    """Remove chars from s.

    >>> rmchars("123", "123456")
    '456'
    >>> rmchars(">=<.", ">=2.0")
    '20'
    >>> rmchars(">=<.", "")
    ''
    """
    for c in chars:
        s = s.replace(c, "")
    return s


def get_pep_dep(libname: str, version: str) -> str:
    """Return a valid PEP 508 dependency string.

    ref: https://www.python.org/dev/peps/pep-0508/

    >>> get_pep_dep("riot", "==0.2.0")
    'riot==0.2.0'
    """
    return f"{libname}{version}"


def env_to_str(envs: t.Sequence[t.Tuple[str, str]]) -> str:
    """Return a human-friendly representation of environment variables.

    >>> env_to_str([("FOO", "BAR")])
    'FOO=BAR'
    >>> env_to_str([("K", "V"), ("K2", "V2")])
    'K=V K2=V2'
    """
    return " ".join(f"{k}={v}" for k, v in envs)


def run_cmd(
    args: str,
    shell: bool = False,
    stdout: _T_stdio = subprocess.PIPE,
    env: t.Optional[t.Dict[str, str]] = None,
) -> _T_CompletedProcess:
    env = env or {}

    logger.debug(
        "Running command '%s' with environment '%s'.",
        args,
        env_to_str(list(env.items())),
    )
    r = subprocess.run(args.split(" "), encoding=ENCODING, stdout=stdout, env=env)
    logger.debug(r.stdout)

    if r.returncode != 0:
        raise CmdFailure("Command %s failed with code %s." % (args[0], r.returncode), r)
    return r


def expand_specs(specs: t.Dict[_K, t.List[_V]]) -> t.Iterator[t.Tuple[t.Tuple[_K, _V]]]:
    """Return the product of all items from the passed dictionary.

    In summary:

    {X: [X0, X1, ...], Y: [Y0, Y1, ...]} ->
      [(X, X0), (Y, Y0)), ((X, X0), (Y, Y1)), ((X, X1), (Y, Y0)), ((X, X1), (Y, Y1)]

    >>> list(expand_specs({"x": ["x0", "x1"]}))
    [(('x', 'x0'),), (('x', 'x1'),)]
    >>> list(expand_specs({"x": ["x0", "x1"], "y": ["y0", "y1"]}))
    [(('x', 'x0'), ('y', 'y0')), (('x', 'x0'), ('y', 'y1')), (('x', 'x1'), ('y', 'y0')), (('x', 'x1'), ('y', 'y1'))]
    """
    all_vals = [[(name, val) for val in vals] for name, vals in specs.items()]

    # Need to cast because the * star typeshed of itertools.product returns Any
    return t.cast(t.Iterator[t.Tuple[t.Tuple[_K, _V]]], itertools.product(*all_vals))
