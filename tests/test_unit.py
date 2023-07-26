from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Dict
from typing import Generator

import pytest

from riot.interpreter import Interpreter
from riot.riot import Session
from riot.utils import join_paths
from riot.utils import run_cmd
from riot.venv import Venv
from riot.venv import VenvInstance
from riot.venv import VirtualEnv
from tests.test_cli import DATA_DIR


RIOT_TESTS_PATH = Path(__file__).parent.resolve() / ".riot"
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

        venv_path = Path(command_env["VENV_PATH"])

        # Create the virtualenv
        virtualenv = VirtualEnv(current_interpreter, venv_path)
        virtualenv.create(force=True)

        # Check folder exists and is empty of packages
        result = _get_pip_freeze(command_env)
        assert virtualenv.exists()
        assert result == ""

        # return the command environment to reuse in other commands
        yield command_env

        assert virtualenv.exists()
    finally:
        shutil.rmtree(RIOT_TESTS_PATH, ignore_errors=True)


@pytest.fixture
def session_virtualenv() -> Generator[Session, None, None]:
    from riot.config import config

    current_riot_folder = config.riot_folder
    try:
        session = Session.from_config_file(DATA_DIR / "nested_riotfile.py")
        config.riot_folder = RIOT_TESTS_PATH

        session.generate_base_venvs(re.compile(""), True, False, set())
        yield session
    finally:
        shutil.rmtree(RIOT_TESTS_PATH, ignore_errors=True)
        config.riot_folder = current_riot_folder


def _get_env(env_name: str) -> Dict[str, str]:
    """Return a dictionary with riot venv paths to add to the environment."""
    venv_path = RIOT_TESTS_PATH / env_name
    venv_site_packages_path = (
        venv_path / "lib" / f"python{current_py_hint}" / "site-packages"
    )

    venv_python_path = venv_path / "bin"
    command_env = {
        "RIOT_ENV_BASE_PATH": str(RIOT_TESTS_PATH),
        "PYTHONPATH": str(venv_python_path),
        "PATH": join_paths(venv_python_path, venv_site_packages_path),
        "VENV_PATH": str(venv_path),
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
        (3.9, 3.9, True),
        (3.9, "3.9", True),
        ("3.9", "3.9", True),
        ("3.9", 3.9, True),
        (3.8, 3.9, False),
        (3.8, "3.9", False),
        (3.9, 3.9, True),
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
    assert (
        current_interpreter.base_venv_path
        == (Path(".riot") / "venv_py{}".format(py_version)).resolve()
    )


def test_venv_instance_venv_path(current_interpreter: Interpreter) -> None:
    venv = VenvInstance(
        venv=Venv(name="test", command="echo test"),
        env={"env": "test"},
        pkgs={"pip": ""},
        py=current_interpreter,
    )

    py_version = "".join((str(_) for _ in sys.version_info[:3]))
    assert venv.prefix == (Path(".riot") / f"venv_py{py_version}_pip").resolve()


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

    venv_path = Path(venv["VENV_PATH"])
    virtualenv = VirtualEnv(current_interpreter, venv_path)
    virtualenv.create(force=False)

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

    virtualenv = VirtualEnv(current_interpreter, Path(venv["VENV_PATH"]))
    virtualenv.create(force=True)

    result = _get_pip_freeze(venv)
    assert result == ""


def _get_base_env_path() -> Path:
    return RIOT_TESTS_PATH / "venv_py{}{}{}".format(*sys.version_info[:3])


def test_session_generate(session_virtualenv: Session) -> None:
    """Validate session, generation of virtualenvs.

    Generate new base venv and validate the virtualenv exists
    """
    assert _get_base_env_path().exists()


def test_session_run(session_virtualenv: Session) -> None:
    """Validate session run method.

    Generate new base venv and validate the nested packages.
    """
    session_virtualenv.run(re.compile(""), re.compile(""), False, False)

    env_name = "venv_py%s%s%s_itsdangerous110_isort5101_six1150" % sys.version_info[:3]
    command_env = _get_env(env_name)
    # Check exists and is empty of packages
    result = _get_pip_freeze(command_env)
    regex = r"isort==5\.10\.1itsdangerous==1\.1\.0(.*)six==1\.15\.0"
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
    regex = r"isort==5\.10\.1itsdangerous==0\.24(.*)six==1\.15\.0"
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
    regex = r"isort==5\.10\.1itsdangerous==0\.24(.*)six==1\.15\.0"
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
    regex = r"isort==5\.10\.1itsdangerous==1\.1\.0(.*)six==1\.15\.0"
    expected = re.match(regex, result.replace("\n", ""))
    assert expected, "error: {}".format(result)
