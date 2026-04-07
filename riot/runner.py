import logging
import os
from pathlib import Path
import subprocess
import sys
import typing as t

from .constants import _T_CompletedProcess, _T_stdio, ENCODING, SHELL
from .exceptions import CmdFailure

logger = logging.getLogger(__name__)

ALWAYS_PASS_ENV = frozenset(
    {
        "LANG",
        "LANGUAGE",
        "SSL_CERT_FILE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "PIP_INDEX_URL",
        "PATH",
    }
)


def run_cmd(
    args: t.Union[str, t.Sequence[str]],
    shell: bool = False,
    stdout: _T_stdio = subprocess.PIPE,
    executable: t.Optional[str] = None,
    env: t.Optional[t.Dict[str, str]] = None,
) -> _T_CompletedProcess:
    if shell:
        executable = SHELL

    logger.debug("Running command %s", args)
    r = subprocess.run(
        args,
        encoding=ENCODING,
        stdout=stdout,
        executable=executable,
        shell=shell,
        env=env,
    )
    logger.debug(r.stdout)

    if r.returncode != 0:
        raise CmdFailure("Command %s failed with code %s." % (args[0], r.returncode), r)
    return r


def run_cmd_venv(
    venv: str,
    args: str,
    stdout: _T_stdio = subprocess.PIPE,
    executable: t.Optional[str] = None,
    env: t.Optional[t.Dict[str, str]] = None,
) -> _T_CompletedProcess:
    env = {} if env is None else env.copy()

    abs_venv = os.path.abspath(venv)
    env["VIRTUAL_ENV"] = abs_venv
    env["PATH"] = f"{abs_venv}/bin:" + env.get("PATH", "")

    try:
        # Ensure that we have the venv site-packages in the PYTHONPATH so
        # that the installed dev package dependencies are available.
        sitepkgs_path = next((Path(abs_venv) / "lib").glob("python*")) / "site-packages"
        pythonpath = env.get("PYTHONPATH", None)
        env["PYTHONPATH"] = (
            os.pathsep.join((pythonpath, str(sitepkgs_path)))
            if pythonpath is not None
            else str(sitepkgs_path)
        )
    except StopIteration:
        pass

    for k in ALWAYS_PASS_ENV:
        if k in os.environ and k not in env:
            env[k] = os.environ[k]

    env_str = " ".join(f"{k}={v}" for k, v in env.items())

    logger.debug("Executing command '%s' with environment '%s'", args, env_str)
    return run_cmd(args, stdout=stdout, executable=executable, env=env, shell=True)


def install_dev_pkg(venv_path: str, force: bool = False) -> None:
    dev_pkg_lockfile = Path(venv_path) / ".riot-dev-pkg-installed"
    if dev_pkg_lockfile.exists() and not force:
        logger.info("Dev package already installed. Skipping.")
        return

    for setup_file in {"setup.py", "pyproject.toml"}:
        if Path(setup_file).exists():
            break
    else:
        logger.warning("No Python setup file found. Skipping dev package installation.")
        return

    logger.info("Installing dev package (edit mode) in %s.", venv_path)
    try:
        run_cmd_venv(
            venv_path,
            "pip --disable-pip-version-check install -e .",
            env=dict(os.environ),
        )
        dev_pkg_lockfile.touch()
    except CmdFailure as e:
        logger.error("Dev install failed, aborting!\n%s", e.proc.stdout)
        sys.exit(1)
