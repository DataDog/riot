import contextlib
import os
import re
import shutil
import typing


import click.testing
import mock
import pytest

import riot.cli
import riot.riot


HERE = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(HERE, "data")


@pytest.fixture
def cli() -> click.testing.CliRunner:
    return click.testing.CliRunner()


@contextlib.contextmanager
def with_riotfile(
    cli: click.testing.CliRunner, riotfile: str, dst_filename: str = "riotfile.py"
) -> typing.Generator[None, None, None]:
    with cli.isolated_filesystem() as fs_dir:
        shutil.copy(
            os.path.join(DATA_DIR, riotfile), os.path.join(fs_dir, dst_filename)
        )
        yield


@contextlib.contextmanager
def without_riotfile(
    cli: click.testing.CliRunner,
) -> typing.Generator[None, None, None]:
    with cli.isolated_filesystem():
        yield


def test_main(cli: click.testing.CliRunner):
    """Running main with no command returns usage"""
    result = cli.invoke(riot.cli.main)
    assert result.exit_code == 0
    assert result.stdout.startswith("Usage: main")


def test_main_help(cli: click.testing.CliRunner):
    """Running main with --help returns usage"""
    result = cli.invoke(riot.cli.main, ["--help"])
    assert result.exit_code == 0
    assert result.stdout.startswith("Usage: main")


def test_main_version(cli: click.testing.CliRunner):
    """Running main with --version returns version string"""
    result = cli.invoke(riot.cli.main, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.startswith("main, version ")


def test_list_empty(cli: click.testing.CliRunner):
    """Running list with an empty riotfile prints nothing"""
    with with_riotfile(cli, "empty_riotfile.py"):
        result = cli.invoke(riot.cli.main, ["list"])
        assert result.exit_code == 0
        assert result.stdout == ""


def test_list_no_riotfile(cli: click.testing.CliRunner):
    """Running list with no riotfile fails with an error"""
    with without_riotfile(cli):
        result = cli.invoke(riot.cli.main, ["list"])
        assert result.exit_code == 2
        assert result.stdout.startswith("Usage: main")
        assert result.stdout.endswith(
            "Error: Invalid value for '-f' / '--file': Path 'riotfile.py' does not exist.\n"
        )


def test_list_default_pattern(cli: click.testing.CliRunner):
    """Running list with no pattern passes through the default pattern"""
    with mock.patch("riot.cli.Session.list_suites") as list_suites:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(riot.cli.main, ["list"])
            # Success, but no output because we don't have a matching pattern
            assert result.exit_code == 0
            assert result.stdout == ""

            list_suites.assert_called_once()
            assert list_suites.call_args.args[0].pattern == ".*"


def test_list_with_pattern(cli: click.testing.CliRunner):
    """Running list with a pattern passes through the pattern"""
    with mock.patch("riot.cli.Session.list_suites") as list_suites:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(riot.cli.main, ["list", "^pattern.*"])
            # Success, but no output because we don't have a matching pattern
            assert result.exit_code == 0
            assert result.stdout == ""

            list_suites.assert_called_once()
            assert list_suites.call_args.args[0].pattern == "^pattern.*"


def test_run_suites(cli: click.testing.CliRunner):
    """Running run with default options"""
    with mock.patch("riot.cli.Session.run_suites") as run_suites:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(riot.cli.main, ["run"])
            # Success, but no output because we mock run_suites
            assert result.exit_code == 0
            assert result.stdout == ""

            run_suites.assert_called_once()
            kwargs = run_suites.call_args.kwargs
            assert set(kwargs.keys()) == set(
                [
                    "pattern",
                    "recreate_venvs",
                    "skip_base_install",
                    "pass_env",
                    "pythons",
                ]
            )
            assert kwargs["pattern"].pattern == ".*"
            assert kwargs["recreate_venvs"] == False
            assert kwargs["skip_base_install"] == False
            assert kwargs["pass_env"] == False


def test_run_suites_with_long_args(cli: click.testing.CliRunner):
    """Running run with long option names uses those options"""
    with mock.patch("riot.cli.Session.run_suites") as run_suites:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(
                riot.cli.main,
                ["run", "--recreate-venvs", "--skip-base-install", "--pass-env"],
            )
            # Success, but no output because we mock run_suites
            assert result.exit_code == 0
            assert result.stdout == ""

            run_suites.assert_called_once()
            kwargs = run_suites.call_args.kwargs
            assert set(kwargs.keys()) == set(
                [
                    "pattern",
                    "recreate_venvs",
                    "skip_base_install",
                    "pass_env",
                    "pythons",
                ]
            )
            assert kwargs["pattern"].pattern == ".*"
            assert kwargs["recreate_venvs"] == True
            assert kwargs["skip_base_install"] == True
            assert kwargs["pass_env"] == True


def test_run_suites_with_short_args(cli: click.testing.CliRunner):
    """Running run with short option names uses those options"""
    with mock.patch("riot.cli.Session.run_suites") as run_suites:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(riot.cli.main, ["run", "-r", "-s"])
            # Success, but no output because we mock run_suites
            assert result.exit_code == 0
            assert result.stdout == ""

            run_suites.assert_called_once()
            kwargs = run_suites.call_args.kwargs
            assert set(kwargs.keys()) == set(
                [
                    "pattern",
                    "recreate_venvs",
                    "skip_base_install",
                    "pass_env",
                    "pythons",
                ]
            )
            assert kwargs["pattern"].pattern == ".*"
            assert kwargs["recreate_venvs"] == True
            assert kwargs["skip_base_install"] == True
            assert kwargs["pass_env"] == False


def test_run_suites_with_pattern(cli: click.testing.CliRunner):
    """Running run with pattern passes in that pattern"""
    with mock.patch("riot.cli.Session.run_suites") as run_suites:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(riot.cli.main, ["run", "^pattern.*"])
            # Success, but no output because we mock run_suites
            assert result.exit_code == 0
            assert result.stdout == ""

            run_suites.assert_called_once()
            kwargs = run_suites.call_args.kwargs
            assert set(kwargs.keys()) == set(
                [
                    "pattern",
                    "recreate_venvs",
                    "skip_base_install",
                    "pass_env",
                    "pythons",
                ]
            )
            assert kwargs["pattern"].pattern == "^pattern.*"
            assert kwargs["recreate_venvs"] == False
            assert kwargs["skip_base_install"] == False
            assert kwargs["pass_env"] == False


def test_generate_suites_with_long_args(cli: click.testing.CliRunner):
    """Generatening generate with long option names uses those options"""
    with mock.patch("riot.cli.Session.generate_base_venvs") as generate_base_venvs:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(
                riot.cli.main,
                ["generate", "--recreate-venvs", "--skip-base-install"],
            )
            # Success, but no output because we mock generate_base_venvs
            assert result.exit_code == 0
            assert result.stdout == ""

            generate_base_venvs.assert_called_once()
            kwargs = generate_base_venvs.call_args.kwargs
            assert set(kwargs.keys()) == set(
                ["pattern", "recreate", "skip_deps", "pythons"]
            )
            assert kwargs["pattern"].pattern == ".*"
            assert kwargs["recreate"] == True
            assert kwargs["skip_deps"] == True


def test_generate_base_venvs_with_short_args(cli: click.testing.CliRunner):
    """Generatening generate with short option names uses those options"""
    with mock.patch("riot.cli.Session.generate_base_venvs") as generate_base_venvs:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(riot.cli.main, ["generate", "-r", "-s"])
            # Success, but no output because we mock generate_base_venvs
            assert result.exit_code == 0
            assert result.stdout == ""

            generate_base_venvs.assert_called_once()
            kwargs = generate_base_venvs.call_args.kwargs
            assert set(kwargs.keys()) == set(
                ["pattern", "recreate", "skip_deps", "pythons"]
            )
            assert kwargs["pattern"].pattern == ".*"
            assert kwargs["recreate"] == True
            assert kwargs["skip_deps"] == True


def test_generate_base_venvs_with_pattern(cli: click.testing.CliRunner):
    """Generatening generate with pattern passes in that pattern"""
    with mock.patch("riot.cli.Session.generate_base_venvs") as generate_base_venvs:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(riot.cli.main, ["generate", "^pattern.*"])
            # Success, but no output because we mock generate_base_venvs
            assert result.exit_code == 0
            assert result.stdout == ""

            generate_base_venvs.assert_called_once()
            kwargs = generate_base_venvs.call_args.kwargs
            assert set(kwargs.keys()) == set(
                ["pattern", "recreate", "skip_deps", "pythons"]
            )
            assert kwargs["pattern"].pattern == "^pattern.*"
            assert kwargs["recreate"] == False
            assert kwargs["skip_deps"] == False
