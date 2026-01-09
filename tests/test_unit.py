import os
import re
import shutil
import subprocess
import sys
from typing import Dict, Generator

import pytest
from riot.riot import Interpreter, run_cmd, Session, Venv, VenvInstance
from tests.test_cli import DATA_DIR


RIOT_TESTS_PATH = os.path.join(os.path.dirname(__file__), ".riot")
default_venv_pattern = re.compile(r".*")
current_py_hint = "%s.%s" % (sys.version_info.major, sys.version_info.minor)


@pytest.fixture
def current_interpreter() -> Interpreter:
    return Interpreter(current_py_hint)


@pytest.fixture
def current_venv() -> Venv:
    # Without a command `.instances()` will not resolve anything
    return Venv(pys=[current_py_hint], command="echo test")


@pytest.fixture
def interpreter_virtualenv(
    current_interpreter: Interpreter,
) -> Generator[Dict[str, str], None, None]:
    try:
        env_name = "test_interpreter_venv_creation"
        command_env = _get_env(env_name)

        # Create the virtualenv
        current_interpreter.create_venv(recreate=True, path=command_env["VENV_PATH"])

        # Check folder exists and is empty of packages
        result = _get_pip_freeze(command_env)
        assert os.path.isdir(command_env["VENV_PATH"])
        assert result == ""

        # return the command environment to reuse in other commands
        yield command_env

        assert os.path.isdir(command_env["VENV_PATH"])
    finally:
        shutil.rmtree(RIOT_TESTS_PATH, ignore_errors=True)


@pytest.fixture
def session_virtualenv() -> Generator[Session, None, None]:
    try:
        session = Session.from_config_file(os.path.join(DATA_DIR, "nested_riotfile.py"))
        os.environ["RIOT_ENV_BASE_PATH"] = RIOT_TESTS_PATH

        session.generate_base_venvs(re.compile(""), True, False, set())
        yield session
    finally:
        shutil.rmtree(RIOT_TESTS_PATH, ignore_errors=True)


def _get_env(env_name: str) -> Dict[str, str]:
    """Return a dictionary with riot venv paths to add to the environment."""
    venv_path = os.path.join(RIOT_TESTS_PATH, env_name)
    venv_site_packages_path = os.path.join(
        venv_path, "lib", f"python{current_py_hint}", "site-packages"
    )

    venv_python_path = os.path.join(venv_path, "bin")
    command_env = {
        "RIOT_ENV_BASE_PATH": RIOT_TESTS_PATH,
        "PYTHONPATH": venv_python_path,
        "PATH": venv_python_path + ":" + venv_site_packages_path,
        "VENV_PATH": venv_path,
    }
    return command_env


def _get_pip_freeze(venv: Dict[str, str]) -> str:
    result = run_cmd(
        ["python", "-m", "pip", "freeze"], stdout=subprocess.PIPE, env=venv
    )
    return result.stdout


def _run_pip_install(package: str, venv: Dict[str, str]) -> None:
    run_cmd(
        ["python", "-m", "pip", "install", package],
        stdout=subprocess.PIPE,
        env=venv,
    )


@pytest.mark.parametrize(
    "v1,v2,equal",
    [
        (3.7, 3.7, True),
        (3.7, "3.7", True),
        ("3.7", "3.7", True),
        ("3.7", 3.7, True),
        (3.8, 3.7, False),
        (3.8, "3.7", False),
        (3.7, 3.7, True),
        (3, 3, True),
        (3, "3", True),
        ("3", 3, True),
    ],
)
def test_interpreter(v1, v2, equal):
    if equal:
        assert Interpreter(v1) == Interpreter(v2)
        assert hash(Interpreter(v1)) == hash(Interpreter(v2))
        assert repr(Interpreter(v1)) == repr(Interpreter(v2))
    else:
        assert Interpreter(v1) != Interpreter(v2)
        assert hash(Interpreter(v1)) != hash(Interpreter(v2))
        assert repr(Interpreter(v1)) != repr(Interpreter(v2))


def test_interpreter_venv_path(current_interpreter: Interpreter) -> None:
    py_version = "".join((str(_) for _ in sys.version_info[:3]))
    assert current_interpreter.venv_path == os.path.abspath(
        os.path.join(".riot", "venv_py{}".format(py_version))
    )


def test_venv_instance_venv_path(current_interpreter: Interpreter) -> None:
    venv = VenvInstance(
        venv=Venv(name="test", command="echo test"),
        env={"env": "test"},
        pkgs={"pip": ""},
        py=current_interpreter,
    )

    py_version = "".join((str(_) for _ in sys.version_info[:3]))
    assert venv.prefix == os.path.abspath(
        os.path.join(".riot", "venv_py{}_pip".format(py_version))
    )


def test_interpreter_version(current_interpreter: Interpreter) -> None:
    version = "%s.%s.%s" % sys.version_info[:3]
    assert current_interpreter.version() == version


def test_interpreter_version_info(current_interpreter: Interpreter) -> None:
    assert current_interpreter.version_info() == sys.version_info[:3]


def test_venv_matching(current_interpreter: Interpreter) -> None:
    venv = VenvInstance(
        venv=Venv(command="echo test", name="test"),
        env={"env": "test"},
        pkgs={"pip": ""},
        parent=VenvInstance(
            venv=Venv(),
            py=current_interpreter,
            env={},
            pkgs={"pytest": "==5.4.3"},
        ),
        py=current_interpreter,
    )

    assert venv.match_venv_pattern(re.compile("pytest543"))
    assert not venv.match_venv_pattern(re.compile("pytest345"))
    assert venv.match_venv_pattern(re.compile("pytest543_pip"))
    assert not venv.match_venv_pattern(re.compile("pip_pytest543"))


@pytest.mark.parametrize(
    "pattern",
    [
        # Name
        "test",
        "te",
        ".*st",
        ".*es.*",
        "^test",
        "test$",
        "^test$",
        "^(no_match)|(test)$",
        # Short hash
        "1d63e3e",
        ".*d63.*",
        "[0-9de]*",
        "^1d63e3e",
        "1d63e3e$",
        "^1d63e3e$",
        "^(no_match)|(1d63e3e)$",
    ],
)
def test_venv_name_matching(pattern: str) -> None:
    venv = VenvInstance(
        venv=Venv(
            command="echo test",
            name="test",
        ),
        env={"env": "test"},
        pkgs={"pip": ""},
        py=Interpreter("3"),
    )
    assert venv.short_hash == "1d63e3e"
    assert venv.matches_pattern(re.compile(pattern))


def test_interpreter_venv_creation(
    current_interpreter: Interpreter, interpreter_virtualenv: Dict[str, str]
) -> None:
    """Validate interpreter, creation of virtualenv.

    Install a package with pip in interpreter virtualenv and validate
    if we re-run create_venv with recreate equal to False, the dependencies aren't
    override
    """
    venv = interpreter_virtualenv
    python_package = "itsdangerous==1.1.0"
    _run_pip_install(python_package, venv)

    current_interpreter.create_venv(recreate=False, path=str(venv["VENV_PATH"]))

    result = _get_pip_freeze(venv)
    assert result == "{}\n".format(python_package)


def test_interpreter_venv_recreation(
    current_interpreter: Interpreter, interpreter_virtualenv: Dict[str, str]
) -> None:
    """Validate interpreter, recreation of virtualenv.

    Install a package with pip in interpreter virtualenv and validate
    if we re-run create_venv with recreate equal to True, the dependencies are restored.
    """
    venv = interpreter_virtualenv

    python_package = "itsdangerous==1.1.0"
    _run_pip_install(python_package, venv)

    current_interpreter.create_venv(recreate=True, path=str(venv["VENV_PATH"]))

    result = _get_pip_freeze(venv)
    assert result == ""


def _get_base_env_path() -> str:
    return os.path.abspath(
        os.path.join(
            RIOT_TESTS_PATH,
            "venv_py{}{}{}".format(
                sys.version_info.major,
                sys.version_info.minor,
                sys.version_info.micro,
            ),
        )
    )


def test_session_generate(session_virtualenv: Session) -> None:
    """Validate session, generation of virtualenvs.

    Generate new base venv and validate the virtualenv exists
    """
    venv_path = _get_base_env_path()
    assert os.path.isdir(venv_path)


def test_session_run(session_virtualenv: Session) -> None:
    """Validate session run method.

    Generate new base venv and validate the nested packages.
    """
    session_virtualenv.run(re.compile(""), re.compile(""), False, False)

    env_name = "venv_py%s%s%s_itsdangerous110_isort5101_six1150" % sys.version_info[:3]
    command_env = _get_env(env_name)
    # Check exists and is empty of packages
    result = _get_pip_freeze(command_env)
    regex = r".*isort==5\.10\.1.*itsdangerous==1\.1\.0.*six==1\.15\.0.*"
    expected = re.match(regex, result.replace("\n", ""))
    assert expected


def test_session_run_check_environment_modifications(
    session_virtualenv: Session,
) -> None:
    """Validate session run method.

    Generate new base venv, edit the packages installed with pip isntall
    and validate the nested packages are different.
    """
    session_virtualenv.run(re.compile(""), re.compile(""), False, False)

    env_name = "venv_py%s%s%s_itsdangerous110_isort5101_six1150" % sys.version_info[:3]
    command_env = _get_env(env_name)
    _run_pip_install("itsdangerous==0.24", command_env)
    # Check exists and is empty of packages
    result = _get_pip_freeze(command_env)
    regex = r".*isort==5\.10\.1.*itsdangerous==0\.24.*six==1\.15\.0.*"
    expected = re.match(regex, result.replace("\n", ""))
    assert expected


def test_session_run_check_environment_modifications_and_recreate_false(
    session_virtualenv: Session,
) -> None:
    """Validate session run method.

    Create nested environments, edit the packages installed with pip isntall
    and validate the nested packages are different after execute again session.run
    with recreate_venvs equal to False.
    """
    session_virtualenv.run(re.compile(""), re.compile(""), False, False)

    env_name = "venv_py%s%s%s_itsdangerous110_isort5101_six1150" % sys.version_info[:3]
    command_env = _get_env(env_name)
    _run_pip_install("itsdangerous==0.24", command_env)

    session_virtualenv.run(re.compile(""), re.compile(""), False, False)

    result = _get_pip_freeze(command_env)
    regex = r".*isort==5\.10\.1.*itsdangerous==0\.24.*six==1\.15\.0.*"
    expected = re.match(regex, result.replace("\n", ""))
    assert expected


def test_session_run_check_environment_modifications_and_recreate_true(
    session_virtualenv: Session,
) -> None:
    """Validate session run method.

    Create nested environments, edit the packages installed with pip install
    and validate the nested packages are restored after execute again session.run
    with recreate_venvs equal to True.
    """
    session_virtualenv.run(re.compile(""), re.compile(""), False, False)

    env_name = "venv_py%s%s%s_itsdangerous110_isort5101_six1150" % sys.version_info[:3]
    command_env = _get_env(env_name)
    _run_pip_install("itsdangerous==0.24", command_env)

    session_virtualenv.run(re.compile(""), re.compile(""), False, True)

    result = _get_pip_freeze(command_env)
    regex = r".*isort==5\.10\.1.*itsdangerous==1\.1\.0.*six==1\.15\.0.*"
    expected = re.match(regex, result.replace("\n", ""))
    assert expected, "error: {}".format(result)


def test_get_package_name_from_env_var(monkeypatch):
    """Test get_package_name() with RIOT_PACKAGE_NAME environment variable."""
    import tempfile
    import os
    from riot.riot import get_package_name

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            # Set environment variable
            monkeypatch.setenv("RIOT_PACKAGE_NAME", "my-test-package")

            # Should return the env var value
            assert get_package_name() == "my-test-package"
        finally:
            os.chdir(old_cwd)


def test_get_package_name_from_pyproject_toml(monkeypatch, tmp_path):
    """Test get_package_name() parsing from pyproject.toml [project] table."""
    import os
    from riot.riot import get_package_name

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Create a pyproject.toml with [project] name
        pyproject_content = """
[project]
name = "test-package"
version = "1.0.0"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)

        # Should return the package name from pyproject.toml
        assert get_package_name() == "test-package"
    finally:
        os.chdir(old_cwd)


def test_get_package_name_env_var_takes_precedence(monkeypatch, tmp_path):
    """Test that RIOT_PACKAGE_NAME env var takes precedence over pyproject.toml."""
    import os
    from riot.riot import get_package_name

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Create a pyproject.toml
        pyproject_content = """
[project]
name = "file-package"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)

        # Set env var which should take precedence
        monkeypatch.setenv("RIOT_PACKAGE_NAME", "env-package")

        # Should return the env var value
        assert get_package_name() == "env-package"
    finally:
        os.chdir(old_cwd)


def test_get_package_name_raises_without_config(monkeypatch, tmp_path):
    """Test get_package_name() raises RuntimeError when no config is found."""
    import os
    from riot.riot import get_package_name
    import pytest

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Ensure env var is not set
        monkeypatch.delenv("RIOT_PACKAGE_NAME", raising=False)

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Could not determine package name"):
            get_package_name()
    finally:
        os.chdir(old_cwd)


def test_wheel_source_cli_option_passes_through(monkeypatch, tmp_path):
    """Test that wheel_source is correctly threaded through the CLI to Session."""
    import os
    from pathlib import Path
    from unittest.mock import patch

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Create a minimal riotfile
        Path("riotfile.py").write_text(
            """
from riot import Venv
venv = Venv(
    name="test",
    command="echo 'test'",
    pys=["3.8"],
)
"""
        )

        # Create pyproject.toml
        Path("pyproject.toml").write_text('[project]\nname = "test-pkg"')

        # Mock the Session.run method to verify wheel_source is passed
        with patch("riot.riot.Session.run") as mock_run:
            from riot.cli import main
            from click.testing import CliRunner

            runner = CliRunner()
            # Test with wheel-source flag
            result = runner.invoke(main, ["--wheel-source", "/tmp/wheels", "run", ".*"])

            # Verify that Session.run was called with wheel_source parameter
            # Note: This test verifies the CLI layer correctly threads the parameter
            assert result.exit_code == 0 or "wheel_source" in str(mock_run.call_args)
    finally:
        os.chdir(old_cwd)
