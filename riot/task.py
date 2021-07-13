import dataclasses
import logging
import os
import sys
import typing as t

from riot.interpreter import Interpreter
from riot.utils import CmdFailure, expand_specs, rm_singletons, run_cmd_venv
from riot.venv import Venv, VenvSpec

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class TaskResult:
    task_name: str
    env: t.Dict[str, str]
    venv: Venv
    venv_name: str
    code: int = 1
    output: str = ""


@dataclasses.dataclass
class Task:
    name: str
    command: str
    env: dataclasses.InitVar[t.Dict[str, t.Union[str, t.List[str]]]] = None
    venvs: t.List[VenvSpec] = dataclasses.field(default_factory=list)
    # subtasks: t.List["Task"] = dataclasses.field(default_factory=list)

    def __post_init__(self, env):
        """Normalize the data."""
        self.env = rm_singletons(env) if env else {}

    @property
    def venv_instances(self):
        for spec in self.venvs:
            yield from spec.instances()

    def run(
        self,
        venv_pattern: t.Pattern[str],
        cmdargs: t.Optional[t.Sequence[str]] = None,
        out: t.TextIO = sys.stdout,
        pass_env: bool = False,
        pythons: t.Optional[t.Set[Interpreter]] = None,
        skip_missing: bool = False,
        exit_first: bool = False,
    ) -> t.List[TaskResult]:
        assert self.command is not None

        results: t.List[TaskResult] = []

        for venv in self.venv_instances:
            if venv.py is None:
                logger.warning(
                    "Skipping venv instance %s due to missing interpreter specification",
                    venv,
                )
                continue
            if pythons and venv.py not in pythons:
                logger.debug(
                    "Skipping venv instance %s due to interpreter mismatch", venv
                )
                continue

            try:
                venv.py.venv_path
            except FileNotFoundError:
                if skip_missing:
                    logger.warning("Skipping missing interpreter %s", venv.py)
                    continue
                else:
                    raise

            venv_path = venv.venv_path
            assert venv_path is not None

            logger.info("Running with %s", venv.py)

            venv_path = venv.venv_path
            if not venv_pattern.search(venv_path):
                logger.debug(
                    "Skipping venv instance '%s' due to pattern mismatch", venv_path
                )
                continue

            for e in (dict(_) for _ in expand_specs(self.env)):
                # Generate the environment for the instance.
                if pass_env:
                    env = os.environ.copy()
                    env.update(e)
                else:
                    env = e.copy()

                venv.prepare(env)

                env["PYTHONPATH"] = venv.pythonpath
                script_path = venv.scriptpath
                if script_path:
                    env["PATH"] = ":".join(
                        (script_path, env.get("PATH", os.environ["PATH"]))
                    )

                # Result which will be updated with the test outcome.
                result = TaskResult(
                    task_name=self.name,
                    env=e,
                    venv=venv,
                    venv_name=venv_path,
                )
                results.append(result)

                # Finally, run the test in the venv.
                if cmdargs is not None:
                    command = self.command.format(cmdargs=(" ".join(cmdargs))).strip()
                env_str = " ".join(f"{k}={v}" for k, v in env.items())
                logger.info(
                    "Running command '%s' with environment '%s'.",
                    command,
                    env_str,
                )
                try:
                    # Pipe the command output directly to `out` since we
                    # don't need to store it.
                    output = run_cmd_venv(venv_path, command, stdout=out, env=env)
                    result.output = output.stdout
                except CmdFailure as e:
                    if exit_first:
                        raise
                    result.code = e.code
                except KeyboardInterrupt:
                    result.code = 1
                    return results
                else:
                    result.code = 0

        return results
