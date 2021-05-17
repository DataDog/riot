__all__ = ["main"]

import logging
import re
import sys


import click
import pkg_resources

from .riot import Interpreter, Session


try:
    __version__ = pkg_resources.get_distribution("riot").version
except pkg_resources.DistributionNotFound:
    # package is not installed
    __version__ = "dev"


class InterpreterParamType(click.ParamType):
    name = "interpreter"

    def convert(self, value, param, ctx):
        return Interpreter(value)


PATTERN_ARG = click.argument("pattern", envvar="RIOT_PATTERN", default=r".*")
VENV_PATTERN_ARG = click.option("--venv-pattern", "venv_pattern", default=r".*")
RECREATE_VENVS_ARG = click.option(
    "-r",
    "--recreate-venvs",
    "recreate_venvs",
    is_flag=True,
    default=False,
)
SKIP_BASE_INSTALL_ARG = click.option(
    "-s", "--skip-base-install", "skip_base_install", is_flag=True, default=False
)
PYTHON_VERSIONS_ARG = click.option(
    "-p", "--python", "pythons", type=InterpreterParamType(), default=[], multiple=True
)


@click.group()
@click.option(
    "-f",
    "--file",
    "riotfile",
    default="riotfile.py",
    show_default=True,
    type=click.Path(exists=True),
)
@click.option("-v", "--verbose", "log_level", flag_value=logging.INFO)
@click.option("-d", "--debug", "log_level", flag_value=logging.DEBUG)
@click.version_option(__version__)
@click.pass_context
def main(ctx, riotfile, log_level):
    if log_level:
        logging.basicConfig(level=log_level)

    ctx.ensure_object(dict)
    try:
        ctx.obj["session"] = Session.from_config_file(riotfile)
    except Exception as e:
        click.echo(f"Failed to construct config file:\n{str(e)}", err=True)
        sys.exit(1)


@main.command("list", help="""List all virtual env instances matching a pattern.""")
@PYTHON_VERSIONS_ARG
@PATTERN_ARG
@VENV_PATTERN_ARG
@click.pass_context
def list_venvs(ctx, pythons, pattern, venv_pattern):
    ctx.obj["session"].list_venvs(
        re.compile(pattern), re.compile(venv_pattern), pythons=pythons
    )


@main.command(
    help="""Generate base virtual environments.

A base virtual environment is a virtual environment with the local package
installed.

Generating the base virtual environments is useful for performance to avoid
having to reinstall the local package repeatedly.

Once the base virtual environments are built, the ``--skip-base-install`` option
can be used for the run command to avoid having to install the local package."""
)
@RECREATE_VENVS_ARG
@SKIP_BASE_INSTALL_ARG
@PYTHON_VERSIONS_ARG
@PATTERN_ARG
@click.pass_context
def generate(ctx, recreate_venvs, skip_base_install, pythons, pattern):
    ctx.obj["session"].generate_base_venvs(
        pattern=re.compile(pattern),
        recreate=recreate_venvs,
        skip_deps=skip_base_install,
        pythons=pythons,
    )


@main.command(
    help="""Run virtualenv instances with names matching a pattern.""",
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
)
@RECREATE_VENVS_ARG
@SKIP_BASE_INSTALL_ARG
@click.option("--pass-env", "pass_env", is_flag=True, default=False)
@PYTHON_VERSIONS_ARG
@click.option("--skip-missing", "skip_missing", is_flag=True, default=False)
@click.option("--exitfirst", "-x", "exit_first", is_flag=True, default=False)
@PATTERN_ARG
@VENV_PATTERN_ARG
@click.pass_context
def run(
    ctx,
    recreate_venvs,
    skip_base_install,
    pass_env,
    pythons,
    skip_missing,
    exit_first,
    pattern,
    venv_pattern,
):
    ctx.obj["session"].run(
        pattern=re.compile(pattern),
        venv_pattern=re.compile(venv_pattern),
        recreate_venvs=recreate_venvs,
        skip_base_install=skip_base_install,
        pass_env=pass_env,
        cmdargs=ctx.args,
        pythons=pythons,
        skip_missing=skip_missing,
        exit_first=exit_first,
    )
