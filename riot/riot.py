import importlib.abc
import importlib.util
import itertools
import logging
import os
import shutil
import subprocess
import sys
import typing as t

import attr


logger = logging.getLogger(__name__)


SHELL = "/bin/bash"
ENCODING = "utf-8"


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


PkgSpec = t.Tuple[str, t.List[str]]
EnvSpec = t.Tuple[str, t.List[str]]


@attr.s
class Case:
    pys: t.List[float] = attr.ib()
    pkgs: t.List[PkgSpec] = attr.ib(default=[])
    env: t.List[EnvSpec] = attr.ib(default=[])


@attr.s
class Suite:
    name: str = attr.ib()
    command: str = attr.ib()
    cases: t.List[Case] = attr.ib()
    env: t.List[EnvSpec] = attr.ib(default=[])


@attr.s
class CaseInstance:
    py: float = attr.ib()
    case: Case = attr.ib()
    suite: Suite = attr.ib()
    pkgs: t.List[PkgSpec] = attr.ib()
    env: t.List[EnvSpec] = attr.ib()


@attr.s
class CaseResult:
    case: CaseInstance = attr.ib()
    venv: str = attr.ib()
    pkgstr: str = attr.ib()
    code: int = attr.ib(default=1)


class CmdFailure(Exception):
    def __init__(self, msg, completed_proc):
        self.msg = msg
        self.proc = completed_proc
        self.code = completed_proc.returncode
        super().__init__(self, msg)


@attr.s
class Session:
    suites: t.List[Suite] = attr.ib(factory=list)
    global_deps: t.List[str] = attr.ib(factory=list)
    global_env: t.List[t.Tuple[str, str]] = attr.ib(factory=list)

    @classmethod
    def from_config_file(cls, path: str) -> "Session":
        spec = importlib.util.spec_from_file_location("riotfile", path)
        config = importlib.util.module_from_spec(spec)

        # DEV: MyPy has `ModuleSpec.loader` as `Optional[_Loader`]` which doesn't have `exec_module`
        # https://github.com/python/typeshed/blob/fe58699ca5c9ee4838378adb88aaf9323e9bbcf0/stdlib/3/_importlib_modulespec.pyi#L13-L44
        t.cast(importlib.abc.Loader, spec.loader).exec_module(config)

        suites = getattr(config, "suites", [])
        global_deps = getattr(config, "global_deps", [])
        global_env = getattr(config, "global_env", [])

        return cls(suites=suites, global_deps=global_deps, global_env=global_env)

    def run_suites(
        self,
        pattern: t.Pattern,
        skip_base_install=False,
        recreate_venvs=False,
        out: t.TextIO = sys.stdout,
        pass_env=False,
        pythons=[],
    ):
        """Runs the command for each case in `suites` in a virtual environment
        determined by its dependencies.
        """
        results = []

        self.generate_base_venvs(
            pattern,
            recreate=recreate_venvs,
            skip_deps=skip_base_install,
            pythons=pythons,
        )

        for case in suites_iter(self.suites, pattern=pattern):
            if pythons and case.py not in pythons:
                logger.debug("Skipping case %s due to Python version", case)
                continue

            base_venv = get_base_venv_path(case.py)

            # Resolve the packages required for this case.
            pkgs: t.Dict[str, str] = {
                name: version for name, version in case.pkgs if version is not None
            }

            if pkgs:
                # Strip special characters for the venv directory name.
                venv_postfix = "_".join(
                    [f"{n}{rmchars('<=>.,', v)}" for n, v in pkgs.items()]
                )
                venv = f"{base_venv}_{venv_postfix}"
                pkg_str = " ".join(
                    [f"'{get_pep_dep(lib, version)}'" for lib, version in pkgs.items()]
                )
            else:
                venv = base_venv
                pkg_str = ""

            # Case result which will contain metadata about the test execution.
            result = CaseResult(case=case, venv=venv, pkgstr=pkg_str)

            try:
                if pkgs:
                    # Copy the base venv to use for this case.
                    logger.info(
                        "Copying base virtualenv '%s' into case virtual env '%s'.",
                        base_venv,
                        venv,
                    )
                    try:
                        run_cmd(["cp", "-r", base_venv, venv], stdout=subprocess.PIPE)
                    except CmdFailure as e:
                        raise CmdFailure(
                            f"Failed to create case virtual env '{venv}'\n{e.proc.stdout}",
                            e.proc,
                        )

                    logger.info("Installing case dependencies %s.", pkg_str)
                    try:
                        run_cmd_venv(venv, f"pip install {pkg_str}")
                    except CmdFailure as e:
                        raise CmdFailure(
                            f"Failed to install case dependencies {pkg_str}\n{e.proc.stdout}",
                            e.proc,
                        )

                # Generate the environment for the test case.
                env = os.environ.copy() if pass_env else {}
                env.update({k: v for k, v in self.global_env})

                # Add in the suite env vars.
                for k, v in case.suite.env:
                    resolved_val = v(AttrDict(pkgs=pkgs)) if callable(v) else v
                    if resolved_val is not None:
                        if k in env:
                            logger.debug("Suite overrides environment variable %s", k)
                        env[k] = resolved_val

                # Add in the case env vars.
                for k, v in case.env:
                    resolved_val = v(AttrDict(pkgs=pkgs)) if callable(v) else v
                    if resolved_val is not None:
                        if k in env:
                            logger.debug("Case overrides environment variable %s", k)
                        env[k] = resolved_val

                # Finally, run the test in the venv.
                cmd = case.suite.command
                env_str = " ".join(f"{k}={v}" for k, v in env.items())
                logger.info(
                    "Running suite command '%s' with environment '%s'.", cmd, env_str
                )
                try:
                    # Pipe the command output directly to `out` since we
                    # don't need to store it.
                    run_cmd_venv(venv, cmd, stdout=out, env=env)
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
            except Exception as e:
                logger.error("Test runner failed: %s", e, exc_info=True)
                sys.exit(1)
            else:
                result.code = 0
            finally:
                results.append(result)

        print("\n-------------------summary-------------------", file=out)
        for r in results:
            failed = r.code != 0
            status_char = "✖️" if failed else "✔️"
            env_str = get_env_str(case.env)
            s = f"{status_char}  {r.case.suite.name}: {env_str} python{r.case.py} {r.pkgstr}"
            print(s, file=out)

        if any(True for r in results if r.code != 0):
            sys.exit(1)

    def list_suites(self, pattern, out=sys.stdout):
        curr_suite = None
        for case in suites_iter(self.suites, pattern):
            if case.suite != curr_suite:
                curr_suite = case.suite
                print(f"{case.suite.name}:", file=out)
            pkgs_str = " ".join(
                f"'{get_pep_dep(name, version)}'" for name, version in case.pkgs
            )
            env_str = get_env_str(case.env)
            py_str = f"Python {case.py}"
            print(f" {env_str} {py_str} {pkgs_str}", file=out)

    def generate_base_venvs(self, pattern: t.Pattern, recreate, skip_deps, pythons):
        """Generate all the required base venvs for `suites`."""
        # Find all the python versions used.
        required_pys = set(
            [case.py for case in suites_iter(self.suites, pattern=pattern)]
        )
        # Apply Python filters.
        if pythons:
            required_pys = required_pys.intersection(pythons)

        logger.info(
            "Generating virtual environments for Python versions %s",
            ",".join(str(s) for s in required_pys),
        )

        for py in required_pys:
            try:
                venv_path = create_base_venv(py, recreate=recreate)
            except CmdFailure as e:
                logger.error("Failed to create virtual environment.\n%s", e.proc.stdout)
            except FileNotFoundError:
                logger.error("Python version '%s' not found.", py)
            else:
                if skip_deps:
                    logger.info("Skipping global deps install.")
                    continue

                # Install the global dependencies into the base venv.
                global_deps_str = " ".join([f"'{dep}'" for dep in self.global_deps])
                logger.info(
                    "Installing base dependencies %s into virtualenv.", global_deps_str
                )

                try:
                    run_cmd_venv(venv_path, f"pip install {global_deps_str}")
                except CmdFailure as e:
                    logger.error(
                        "Base dependencies failed to install, aborting!\n%s",
                        e.proc.stdout,
                    )
                    sys.exit(1)

                # Install the dev package into the base venv.
                logger.info("Installing dev package.")
                try:
                    run_cmd_venv(venv_path, "pip install -e .")
                except CmdFailure as e:
                    logger.error("Dev install failed, aborting!\n%s", e.proc.stdout)
                    sys.exit(1)


def rmchars(chars: str, s: str):
    for c in chars:
        s = s.replace(c, "")
    return s


def get_pep_dep(libname: str, version: str):
    """Returns a valid PEP 508 dependency string.

    ref: https://www.python.org/dev/peps/pep-0508/
    """
    return f"{libname}{version}"


def get_env_str(envs: t.List[t.Tuple]):
    return " ".join(f"{k}={v}" for k, v in envs)


def get_base_venv_path(pyversion):
    """Given a python version return the base virtual environment path relative
    to the current directory.
    """
    pyversion = str(pyversion).replace(".", "")
    return f".riot/.venv_py{pyversion}"


def run_cmd(*args, **kwargs):
    # Provide our own defaults.
    if "shell" in kwargs and "executable" not in kwargs:
        kwargs["executable"] = SHELL
    if "encoding" not in kwargs:
        kwargs["encoding"] = ENCODING
    if "stdout" not in kwargs:
        kwargs["stdout"] = subprocess.PIPE

    logger.debug("Running command %s", args[0])
    r = subprocess.run(*args, **kwargs)
    logger.debug(r.stdout)

    if r.returncode != 0:
        raise CmdFailure("Command %s failed with code %s." % (args[0], r.returncode), r)
    return r


def create_base_venv(pyversion, path=None, recreate=True):
    """Attempts to create a virtual environment for `pyversion`.

    :param pyversion: string or int representing the major.minor Python
                      version. eg. 3.7, "3.8".
    """
    path = path or get_base_venv_path(pyversion)

    if os.path.isdir(path) and not recreate:
        logger.info("Skipping creation of virtualenv '%s' as it already exists.", path)
        return path

    py_ex = f"python{pyversion}"
    py_ex = shutil.which(py_ex)

    if not py_ex:
        logger.debug("%s interpreter not found", py_ex)
        raise FileNotFoundError
    else:
        logger.info("Found Python interpreter '%s'.", py_ex)

    logger.info("Creating virtualenv '%s' with Python '%s'.", path, py_ex)
    r = run_cmd(["virtualenv", f"--python={py_ex}", path], stdout=subprocess.PIPE)
    return path


def get_venv_command(venv_path, cmd):
    """Return the command string used to execute `cmd` in virtual env located
    at `venv_path`.
    """
    return f"source {venv_path}/bin/activate && {cmd}"


def run_cmd_venv(venv, cmd, **kwargs):
    env = kwargs.get("env") or {}
    env_str = " ".join(f"{k}={v}" for k, v in env.items())
    cmd = get_venv_command(venv, cmd)

    logger.debug("Executing command '%s' with environment '%s'", cmd, env_str)
    r = run_cmd(cmd, shell=True, **kwargs)
    return r


def expand_specs(specs):
    """Generator over all configurations of a specification.

    [(X, [X0, X1, ...]), (Y, [Y0, Y1, ...)] ->
      ((X, X0), (Y, Y0)), ((X, X0), (Y, Y1)), ((X, X1), (Y, Y0)), ((X, X1), (Y, Y1))
    """
    all_vals = []

    for name, vals in specs:
        all_vals.append([(name, val) for val in vals])

    all_vals = itertools.product(*all_vals)
    return all_vals


def case_iter(case: Case):
    # We could itertools.product here again but I think this is clearer.
    for env_cfg in expand_specs(case.env):
        for py in case.pys:
            for pkg_cfg in expand_specs(case.pkgs):
                yield env_cfg, py, pkg_cfg


def cases_iter(cases: t.Iterable[Case]):
    """Iterator over all case instances of a suite.

    Yields the dependencies unique to the instance of the suite.
    """
    for case in cases:
        for env_cfg, py, pkg_cfg in case_iter(case):
            yield case, env_cfg, py, pkg_cfg


def suites_iter(suites: t.Iterable[Suite], pattern: t.Pattern, py=None):
    """Iterator over an iterable of suites.

    :param pattern: An optional pattern to match suite names against.
    :param py: An optional python version to match against.
    """
    for suite in suites:
        if not pattern.match(suite.name):
            logger.debug("Skipping suite '%s' due to mismatch.", suite.name)
            continue

        for case, env, spy, pkgs in cases_iter(suite.cases):
            if py and spy != py:
                continue
            yield CaseInstance(suite=suite, case=case, env=env, py=spy, pkgs=pkgs)
