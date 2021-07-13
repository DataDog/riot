import dataclasses
import importlib.abc
import importlib.util
import logging
import sys
import traceback
import typing as t

import click
from riot.interpreter import Interpreter
from riot.task import Task
from riot.utils import CmdFailure, env_to_str, get_pep_dep, run_cmd_venv

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Session:
    tasks: t.List[Task]
    warnings = (
        "deprecated",
        "deprecation",
        "warning",
        "no longer maintained",
        "not maintained",
        "did you mean",
    )

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
            # DEV: Shouldn't this raise a warning if there are no tasks?
            # DEV: Should we just look into dir(config) for all the variables
            # that are either a Task or a list/tuple of Tasks? This would allow
            # for things like:
            # checks = [Task(name="black", command="black ..."), ...]
            # tests = [Task(name="test1", command="pytest {args} tests/..."), ...]
            tasks = getattr(config, "tasks", [])
            return cls(tasks=tasks)

    def is_warning(self, output):
        if output is None:
            return False
        lower_output = output.lower()
        return any(warning in lower_output for warning in self.warnings)

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
        skip_missing: bool = False,
        exit_first: bool = False,
    ) -> None:
        results = []

        self.generate_base_venvs(
            pattern,
            recreate=recreate_venvs,
            skip_deps=skip_base_install,
            pythons=pythons,
        )

        for task in (_ for _ in self.tasks if pattern.match(_.name)):
            try:
                results = task.run(
                    venv_pattern=venv_pattern,
                    cmdargs=cmdargs,
                    out=out,
                    pass_env=pass_env,
                    pythons=pythons,
                    skip_missing=skip_missing,
                    exit_first=exit_first,
                )
            except CmdFailure as e:
                click.echo(click.style(e.msg, fg="red"))
                if exit_first:
                    break
            except Exception:
                logger.error("Test runner failed", exc_info=True)
                sys.exit(1)

        click.echo(
            click.style("\n-------------------summary-------------------", bold=True)
        )

        num_failed = 0
        num_passed = 0
        num_warnings = 0

        for r in results:
            failed = r.code != 0
            env_str = env_to_str(r.env)
            s = f"{r.task_name}: {env_str} python{r.venv.py} {r.venv.pkg_str}"

            if failed:
                num_failed += 1
                s = f"{click.style('x', fg='red', bold=True)} {click.style(s, fg='red')}"
                click.echo(s)
            else:
                num_passed += 1
                if self.is_warning(r.output):
                    num_warnings += 1
                    s = f"{click.style('⚠', fg='yellow', bold=True)} {click.style(s, fg='yellow')}"
                    click.echo(s)
                else:
                    s = f"{click.style('✓', fg='green', bold=True)} {click.style(s, fg='green')}"
                    click.echo(s)

        s_num = f"{num_passed} passed with {num_warnings} warnings, {num_failed} failed"
        click.echo(click.style(s_num, fg="blue", bold=True))

        if any(True for r in results if r.code != 0):
            sys.exit(1)

    def list_venvs(self, pattern, venv_pattern, pythons=None, out=sys.stdout):
        for task in (_ for _ in self.tasks if pattern.match(_.name)):
            for venv in task.venv_instances:
                if pythons and venv.py not in pythons or venv.venv_path is None:
                    continue

                if not venv_pattern.search(venv.venv_path):
                    continue
                pkgs_str = " ".join(
                    f"'{get_pep_dep(name, version)}'" for name, version in venv.pkgs
                )
                env_str = env_to_str(task.env)
                py_str = f"Python {venv.py}"
                click.echo(f"{task.name} {env_str} {py_str} {pkgs_str}")

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
            [
                venv.py
                for task in self.tasks
                for venv in task.venv_instances
                if pattern.match(task.name) and venv.py is not None
            ]
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
