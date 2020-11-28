import contextlib
import os
import shutil
import typing


import click.testing
import mock
import pytest
import riot.cli
import riot.riot
from riot.riot import Interpreter


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


def test_list_with_venv_pattern(cli: click.testing.CliRunner) -> None:
    """Running list with a venv pattern passes."""
    with with_riotfile(cli, "simple_riotfile.py"):
        result = cli.invoke(
            riot.cli.main,
            [
                "list",
                "test",
                "--venv-pattern",
                "pytest543$",
            ],
        )
        assert result.exit_code == 0
        assert result.stdout == ""


def test_list_with_python(cli: click.testing.CliRunner) -> None:
    """Running list with a python passes through the python."""
    with mock.patch("riot.cli.Session.list_venvs") as list_venvs:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(riot.cli.main, ["list", "--python", "3.6"])
            # Success, but no output because we don't have a matching pattern
            assert result.exit_code == 0
            assert result.stdout == ""

            list_venvs.assert_called_once()
            assert list_venvs.call_args.kwargs["pythons"] == (Interpreter("3.6"),)

    # multiple pythons
    with mock.patch("riot.cli.Session.list_venvs") as list_venvs:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(
                riot.cli.main,
                ["list", "--python", "3.6", "-p", "3.8", "--python", "2.7"],
            )
            # Success, but no output because we don't have a matching pattern
            assert result.exit_code == 0
            assert result.stdout == ""

            list_venvs.assert_called_once()
            assert list_venvs.call_args.kwargs["pythons"] == (
                Interpreter("3.6"),
                Interpreter("3.8"),
                Interpreter("2.7"),
            )


def test_run_no_venv_pattern(cli: click.testing.CliRunner) -> None:
    """Running run with pattern passes in that pattern."""
    with mock.patch("riot.riot.logger.debug") as mock_debug:
        with with_riotfile(cli, "simple_riotfile.py"):
            result = cli.invoke(
                riot.cli.main,
                [
                    "run",
                    "test",
                    "-d",
                    "--skip-base-install",
                ],
            )
            assert result.exit_code == 0
            assert result.stdout == ""

            mock_debug.assert_called()
            assert not any(
                [
                    call_args
                    for call_args in mock_debug.call_args_list
                    if call_args.args[0]
                    == "Skipping venv instance '%s' due to pattern mismatch"
                ]
            )


def test_run_venv_pattern(cli: click.testing.CliRunner) -> None:
    """Running run with pattern passes in that pattern."""
    with mock.patch("riot.riot.logger.debug") as mock_debug:
        with with_riotfile(cli, "simple_riotfile.py"):
            result = cli.invoke(
                riot.cli.main,
                [
                    "run",
                    "test",
                    "-d",
                    "--skip-base-install",
                    "--venv-pattern",
                    "pytest543$",
                ],
            )
            assert result.exit_code == 0
            assert result.stdout == ""

            mock_debug.assert_called()
            assert any(
                [
                    call_args
                    for call_args in mock_debug.call_args_list
                    if call_args.args[0]
                    == "Skipping venv instance '%s' due to pattern mismatch"
                    and call_args.args[1].endswith("pytest")
                ]
            )


def test_generate_suites_with_long_args(cli: click.testing.CliRunner) -> None:
    """Generatening generate with long option names uses those options."""
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
            assert kwargs["recreate"] is True
            assert kwargs["skip_deps"] is True


def test_generate_base_venvs_with_short_args(cli: click.testing.CliRunner) -> None:
    """Generatening generate with short option names uses those options."""
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
            assert kwargs["recreate"] is True
            assert kwargs["skip_deps"] is True


def test_generate_base_venvs_with_pattern(cli: click.testing.CliRunner) -> None:
    """Generatening generate with pattern passes in that pattern."""
    with mock.patch("riot.cli.Session.generate_base_venvs") as generate_base_venvs:
        with with_riotfile(cli, "empty_riotfile.py"):
            result = cli.invoke(
                riot.cli.main, ["generate", "^pattern.*"], catch_exceptions=False
            )
            # Success, but no output because we mock generate_base_venvs
            assert result.exit_code == 0
            assert result.stdout == ""

            generate_base_venvs.assert_called_once()
            kwargs = generate_base_venvs.call_args.kwargs
            assert set(kwargs.keys()) == set(
                ["pattern", "recreate", "skip_deps", "pythons"]
            )
            assert kwargs["pattern"].pattern == "^pattern.*"
            assert kwargs["recreate"] is False
            assert kwargs["skip_deps"] is False
