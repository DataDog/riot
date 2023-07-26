import dataclasses
import importlib.abc
import importlib.util
import logging
import os
from pathlib import Path
import sys
import tempfile
import traceback
import typing as t

import click
from packaging.version import Version
import pexpect
from rich import print as rich_print
from rich.pretty import Pretty
from rich.status import Status
from rich.table import Table

from riot.interpreter import Interpreter
from riot.utils import CmdFailure
from riot.utils import SHELL
from riot.utils import env_to_str
from riot.utils import join_paths
from riot.utils import pip_deps
from riot.venv import Venv
from riot.venv import VenvInstanceResult
from riot.venv import VirtualEnv
from riot.venv import nspkgs


logger = logging.getLogger(__name__)


SHELL_RCFILE = """
source {venv_path}/bin/activate
echo -e "\e[31;1m"
echo "                 )  "
echo " (   (        ( /(  "
echo " )(  )\   (   )\()) "
echo "(()\((_)  )\ (_))/  "
echo " ((_)(_) ((_)| |_   "
echo "| '_|| |/ _ \|  _|  "
echo "|_|  |_|\___/ \__|  "
echo -e "\e[0m"
echo -e "\e[33;1mInteractive shell\e[0m"
echo ""
echo -e "* Venv name   : \e[1m{name}\e[0m"
echo -e "* Venv path   : \e[1m{venv_path}\e[0m"
echo -e "* Interpreter : \e[1m$( python -V )\e[0m"
"""


@dataclasses.dataclass
class Session:
    venv: Venv
    warnings = (
        "deprecated",
        "deprecation",
        "warning",
        "no longer maintained",
        "not maintained",
        "did you mean",
    )

    @classmethod
    def from_config_file(cls, path: Path) -> "Session":
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
        recompile_reqs: bool = False,
    ) -> None:
        results = []

        self.generate_base_venvs(
            pattern,
            recreate=recreate_venvs,
            skip_deps=skip_base_install,
            pythons=pythons,
        )

        for inst in self.venv.instances():
            if inst.command is None:
                logger.debug("Skipping venv instance %s due to missing command", inst)
                continue

            if inst.name and not inst.matches_pattern(pattern):
                logger.debug(
                    "Skipping venv instance %s due to name pattern mismatch.", inst
                )
                continue

            assert inst.py is not None, inst
            if pythons and inst.py not in pythons:
                logger.debug(
                    "Skipping venv instance %s due to interpreter mismatch", inst
                )
                continue

            try:
                venv_path = inst.venv_path
                assert venv_path is not None, inst
            except FileNotFoundError:
                if skip_missing:
                    logger.warning("Skipping missing interpreter %s", inst.py)
                    continue
                else:
                    raise

            if not inst.match_venv_pattern(venv_pattern):
                logger.debug(
                    "Skipping venv instance '%s' due to pattern mismatch", venv_path
                )
                continue

            logger.info("Running with %s", inst.py)

            # Result which will be updated with the test outcome.
            result = VenvInstanceResult(instance=inst, venv_name=str(venv_path))

            # Generate the environment for the instance.
            if pass_env:
                env = os.environ.copy()
                env.update(dict(inst.env))
            else:
                env = dict(inst.env)

            # Add riot specific environment variables
            env.update(
                {
                    "RIOT": "1",
                    "RIOT_PYTHON_HINT": str(inst.py),
                    "RIOT_PYTHON_VERSION": inst.py.version(),
                    "RIOT_VENV_HASH": inst.short_hash,
                    "RIOT_VENV_IDENT": inst.ident or "",
                    "RIOT_VENV_NAME": inst.name or "",
                    "RIOT_VENV_PKGS": pip_deps(inst.pkgs),
                    "RIOT_VENV_FULL_PKGS": inst.full_pkg_str,
                }
            )

            inst.prepare(
                env,
                skip_deps=skip_base_install or inst.venv.skip_dev_install,
                recreate=recreate_venvs,
                recompile_reqs=recompile_reqs,
            )

            pythonpath = inst.pythonpath
            if pythonpath:
                env["PYTHONPATH"] = (
                    f"{pythonpath}:{env['PYTHONPATH']}"
                    if "PYTHONPATH" in env
                    else pythonpath
                )
            script_path = inst.path
            if script_path:
                env["PATH"] = join_paths(
                    script_path, env.get("PATH", os.environ.get("PATH"))
                )

            try:
                # Finally, run the test in the base venv.
                command = inst.command
                assert command is not None
                if cmdargs is not None:
                    command = command.format(
                        cmdargs=(" ".join(f"'{arg}'" for arg in cmdargs))
                    ).strip()
                env_str = "\n".join(f"{k}={v}" for k, v in env.items())
                logger.info(
                    "Running command '%s' in venv '%s' with environment:\n%s.",
                    command,
                    venv_path,
                    env_str,
                )
                with nspkgs(inst):
                    try:
                        virtualenv = VirtualEnv(inst.py, venv_path)
                        output = virtualenv.run(command, stdout=out, env=env)
                        result.output = output.stdout
                    except CmdFailure as e:
                        raise CmdFailure(
                            f"Test failed with exit code {e.proc.returncode}", e.proc
                        )
            except CmdFailure as e:
                result.code = e.code
                click.echo(click.style(e.msg, fg="red"))
                if exit_first:
                    break
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

        click.echo(
            click.style("\n-------------------summary-------------------", bold=True)
        )

        num_failed = 0
        num_passed = 0
        num_warnings = 0

        for r in results:
            failed = r.code != 0
            env_str = env_to_str(r.instance.env)
            s = f"{r.instance.name}: [{r.instance.short_hash}] {env_str} python{r.instance.py} {r.instance.full_pkg_str}"

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

    def list_venvs(
        self,
        pattern,
        venv_pattern,
        pythons=None,
        out=sys.stdout,
        pipe_mode=False,
        interpreters=False,
        hash_only=False,
    ):
        python_interpreters = set()
        venv_hashes = set()
        table = None
        if not (pipe_mode or interpreters or hash_only):
            table = Table(
                "No.",
                "Hash",
                "Name",
                "Interpreter",
                "Environment",
                "Packages",
                box=None,
            )

        for n, inst in enumerate(self.venv.instances()):
            if not inst.name or not inst.matches_pattern(pattern):
                continue

            if pythons and inst.py not in pythons:
                continue

            if not inst.match_venv_pattern(venv_pattern):
                continue
            pkgs_str = inst.full_pkg_str
            env_str = env_to_str(inst.env)
            if interpreters or hash_only:
                python_interpreters.add(inst.py._hint)
                venv_hashes.add(inst.short_hash)
                continue

            if pipe_mode:
                print(
                    f"[#{n}]  {inst.short_hash}  {inst.name:12} {env_str} {inst.py} Packages({pkgs_str})"
                )
            else:
                table.add_row(
                    f"[cyan]#{n}[/cyan]",
                    f"[bold cyan]{inst.short_hash}[/bold cyan]",
                    f"[bold]{inst.name}[/bold]",
                    Pretty(inst.py),
                    env_str or "--",
                    f"[italic]{pkgs_str}[/italic]",
                )

        if table:
            rich_print(table)

        elif hash_only and venv_hashes:
            print("\n".join(sorted(venv_hashes)))

        elif interpreters and python_interpreters:
            print("\n".join(sorted(python_interpreters, key=Version)))

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
                inst.py
                for inst in self.venv.instances()
                if inst.py is not None
                and (not inst.name or inst.matches_pattern(pattern))
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
            base_virtualenv = VirtualEnv(py, py.base_venv_path)
            install_required = not (base_virtualenv.exists() and skip_deps) or recreate
            try:
                # We check if the venv existed already. If it didn't, we know we
                # have to install the dev package. Otherwise we assume that it
                # already has the dev package installed.
                base_virtualenv.create(force=recreate)
            except CmdFailure as e:
                logger.error("Failed to create virtual environment.\n%s", e.proc.stdout)
            except FileNotFoundError:
                logger.error("Python version '%s' not found.", py)
            else:
                if not install_required:
                    logger.info("Skipping global deps install.")
                    continue

                # Install the dev package into the base venv.
                base_virtualenv.install()

    def _generate_shell_rcfile(self):
        with tempfile.NamedTemporaryFile() as rcfile:
            rcfile.write()
            rcfile.flush()

    def _venvs_matching_identifier(self, identifier):
        for n, inst in enumerate(self.venv.instances()):
            if identifier != f"#{n}" and not inst.long_hash.startswith(identifier):
                continue

            assert inst.py is not None, inst
            try:
                venv_path = inst.venv_path
            except FileNotFoundError:
                raise RuntimeError("%s not available" % inst.py)
            yield inst, venv_path

    def requirements(self, ident):
        for inst, _ in self._venvs_matching_identifier(ident):
            with Status("Producing requirements.txt"):
                inst.requirements

    def shell(self, ident, pass_env):
        for inst, venv_path in self._venvs_matching_identifier(ident):
            logger.info("Launching shell inside venv instance %s", inst)
            logger.debug("Setting venv path to %s", venv_path)

            # Generate the environment for the instance.
            if pass_env:
                env = os.environ.copy()
                env.update(dict(inst.env))
            else:
                env = dict(inst.env)

            # Should we expect the venv to be ready?
            with Status("Preparing shell virtual environment"):
                virtualenv = VirtualEnv(inst.py, venv_path)
                virtualenv.create(force=False)
                inst.prepare(env)

            pythonpath = inst.pythonpath
            if pythonpath:
                env["PYTHONPATH"] = join_paths(pythonpath, env.get("PYTHONPATH"))
            script_path = inst.path
            if script_path:
                env["PATH"] = join_paths(
                    script_path, env.get("PATH", os.environ.get("PATH"))
                )

            with nspkgs(inst):
                with tempfile.NamedTemporaryFile() as rcfile:
                    rcfile.write(
                        SHELL_RCFILE.format(
                            venv_path=venv_path, name=inst.name
                        ).encode()
                    )
                    rcfile.flush()

                    try:
                        w, h = os.get_terminal_size()
                    except OSError:
                        w, h = 80, 24
                    c = pexpect.spawn(SHELL, ["-i"], dimensions=(h, w), env=env)
                    c.setecho(False)
                    c.sendline(f"source {rcfile.name}")
                    try:
                        c.interact()
                    except Exception:
                        pass
                    c.close()
                    sys.exit(c.exitstatus)

        else:
            logger.error(
                "No venv instance found for %s. Use 'riot list' to get a list of valid numbers.",
                ident,
            )
