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


_K = t.TypeVar("_K")
_V = t.TypeVar("_V")


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

    hint: dataclasses.InitVar[_T_hint]
    _hint: str = dataclasses.field(init=False)

    def __post_init__(self, hint: _T_hint) -> None:
        """Normalize the data."""
        self._hint = str(hint)

    def __str__(self) -> str:
        """Return the path of the interpreter executable."""
        return repr(self)

    def version(self) -> str:
        path = self.path()

        # Redirect stderr to stdout because Python 2 prints version on stderr
        output = subprocess.check_output([path, "--version"], stderr=subprocess.STDOUT)
        version = output.decode().strip().split(" ")[1]
        return version

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

    def venv_path(self) -> str:
        """Return the path to the virtual environment for this interpreter."""
        version = self.version().replace(".", "")
        return f".riot/.venv_py{version}"

    def create_venv(self, recreate: bool) -> str:
        """Attempt to create a virtual environment for this intepreter."""
        path: str = self.venv_path()

        if os.path.isdir(path) and not recreate:
            logger.info(
                "Skipping creation of virtualenv '%s' as it already exists.", path
            )
            return path

        py_ex = self.path()
        logger.info("Creating virtualenv '%s' with interpreter '%s'.", path, py_ex)
        run_cmd(["virtualenv", f"--python={py_ex}", path], stdout=subprocess.PIPE)
        return path


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

    def venv_path(self) -> str:
        """Return path to directory of the instance."""
        base_path = self.py.venv_path()
        venv_postfix = "_".join([f"{n}{rmchars('<=>.,', v)}" for n, v in self.pkgs])
        return f"{base_path}_{venv_postfix}"


@dataclasses.dataclass
class VenvInstanceResult:
    instance: VenvInstance
    venv_name: str
    pkgstr: str
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

        self.generate_base_venvs(
            pattern,
            recreate=recreate_venvs,
            skip_deps=skip_base_install,
            pythons=pythons,
        )

        for inst in self.venv.instances(pattern=pattern):
            if pythons and inst.py not in pythons:
                logger.debug(
                    "Skipping venv instance %s due to interpreter mismatch", inst
                )
                continue

            base_venv_path: str = inst.py.venv_path()

            # Resolve the packages required for this instance.
            pkgs: t.Dict[str, str] = {
                name: version for name, version in inst.pkgs if version is not None
            }

            if pkgs:
                venv_path = inst.venv_path()
                pkg_str = " ".join(
                    [f"'{get_pep_dep(lib, version)}'" for lib, version in pkgs.items()]
                )
            else:
                venv_path = base_venv_path
                pkg_str = ""

            if not venv_pattern.search(venv_path):
                logger.debug(
                    "Skipping venv instance '%s' due to pattern mismatch", venv_path
                )
                continue

            # Result which will be updated with the test outcome.
            result = VenvInstanceResult(
                instance=inst, venv_name=venv_path, pkgstr=pkg_str
            )

            try:
                if pkgs:
                    # Copy the base venv to use for this venv.
                    logger.info(
                        "Copying base virtualenv '%s' into virtualenv '%s'.",
                        base_venv_path,
                        venv_path,
                    )
                    try:
                        shutil.copytree(base_venv_path, venv_path)
                    except FileNotFoundError:
                        logger.info("Base virtualenv '%s' does not exist", venv_path)
                        continue
                    except FileExistsError:
                        # Assume the venv already exists and works fine
                        logger.info("Virtualenv '%s' already exists", venv_path)

                    logger.info("Installing venv dependencies %s.", pkg_str)
                    try:
                        run_cmd_venv(
                            venv_path,
                            f"pip --disable-pip-version-check install {pkg_str}",
                        )
                    except CmdFailure as e:
                        raise CmdFailure(
                            f"Failed to install venv dependencies {pkg_str}\n{e.proc.stdout}",
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
                    run_cmd_venv(venv_path, inst.command, stdout=out, env=env)
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
            s = f"{status_char}  {r.instance.name}: {env_str} {r.instance.py} {r.pkgstr}"
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

    def generate_base_venvs(
        self,
        pattern: t.Pattern[str],
        recreate: bool,
        skip_deps: bool,
        pythons: t.Optional[t.Set[Interpreter]],
    ) -> None:
        """Generate all the required base venvs."""
        # Find all the python interpreters used.
        required_pys: t.Set[Interpreter] = set(
            [inst.py for inst in self.venv.instances(pattern=pattern)]
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
                venv_path = py.create_venv(recreate)
            except CmdFailure as e:
                logger.error("Failed to create virtual environment.\n%s", e.proc.stdout)
            except FileNotFoundError:
                logger.error("Python version '%s' not found.", py)
            else:
                if skip_deps:
                    logger.info("Skipping global deps install.")
                    continue

                # Install the dev package into the base venv.
                logger.info("Installing dev package.")
                try:
                    run_cmd_venv(
                        venv_path, "pip --disable-pip-version-check install -e ."
                    )
                except CmdFailure as e:
                    logger.error("Dev install failed, aborting!\n%s", e.proc.stdout)
                    sys.exit(1)


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


_T_stdio = t.Union[None, int, t.IO[t.Any]]


def run_cmd(
    args: t.Union[str, t.Sequence[str]],
    shell: bool = False,
    stdout: _T_stdio = subprocess.PIPE,
    executable: t.Optional[str] = None,
) -> _T_CompletedProcess:
    if shell:
        executable = SHELL

    logger.debug("Running command %s", args)
    # FIXME Remove type: ignore when https://github.com/python/typeshed/pull/4789 is released
    r = subprocess.run(args, encoding=ENCODING, stdout=stdout, executable=executable, shell=shell)  # type: ignore[arg-type]
    logger.debug(r.stdout)

    if r.returncode != 0:
        raise CmdFailure("Command %s failed with code %s." % (args[0], r.returncode), r)
    return r


def get_venv_command(venv_path: str, cmd: str) -> str:
    """Return the command string used to execute `cmd` in virtual env located at `venv_path`."""
    return f"source {venv_path}/bin/activate && {cmd}"


def run_cmd_venv(
    venv: str,
    args: str,
    stdout: _T_stdio = subprocess.PIPE,
    executable: t.Optional[str] = None,
    env: t.Dict[str, str] = None,
) -> _T_CompletedProcess:
    cmd = get_venv_command(venv, args)

    if env is None:
        env = {}

    env_str = " ".join(f"{k}={v}" for k, v in env.items())

    logger.debug("Executing command '%s' with environment '%s'", cmd, env_str)
    return run_cmd(cmd, stdout=stdout, executable=executable, shell=True)


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
