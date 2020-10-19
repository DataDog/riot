__all__ = ["main"]

import pkg_resources
import logging
import re

import click

from .riot import Session


try:
    __version__ = pkg_resources.get_distribution("riot").version
except pkg_resources.DistributionNotFound:
    # package is not installed
    __version__ = "dev"


PATTERN_ARG = click.argument("pattern", envvar="RIOT_PATTERN", default=r".*")
RECREATE_VENVS_ARG = click.option(
    "-r", "--recreate-venvs", "recreate_venvs", is_flag=True, default=False
)
SKIP_BASE_INSTALL_ARG = click.option(
    "-s", "--skip-base-install", "skip_base_install", is_flag=True, default=False
)
PYTHON_VERSIONS_ARG = click.option(
    "-p", "--python", "pythons", type=float, default=[], multiple=True
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
    ctx.obj["session"] = Session.from_config_file(riotfile)


@main.command("list", help="List sessions")
@PATTERN_ARG
@click.pass_context
def list_suites(ctx, pattern):
    ctx.obj["session"].list_suites(re.compile(pattern))


@main.command(help="Generate virtual environments")
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


@main.command(help="Run suites")
@RECREATE_VENVS_ARG
@SKIP_BASE_INSTALL_ARG
@click.option("--pass-env", "pass_env", is_flag=True, default=False)
@PYTHON_VERSIONS_ARG
@PATTERN_ARG
@click.pass_context
def run(ctx, recreate_venvs, skip_base_install, pass_env, pythons, pattern):
    ctx.obj["session"].run_suites(
        pattern=re.compile(pattern),
        recreate_venvs=recreate_venvs,
        skip_base_install=skip_base_install,
        pass_env=pass_env,
        pythons=pythons,
    )
