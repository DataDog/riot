import os
import re
import shutil
import subprocess
import sys
from typing import Dict, Generator

import pytest
from riot.riot import Interpreter, run_cmd, Venv, VenvInstance

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
def interpreter_virtualenv(current_interpreter: Interpreter) -> Generator[Dict[str, str], None, None]:
    venv_path = ""
    try:
        # Define env paths and variables
        env_name = "test_interpreter_venv_creation"
        venv_path = os.path.abspath(os.path.join(".riot", env_name))
        venv_site_packages_path = os.path.abspath(
            os.path.join(venv_path, "lib", "python3.8", "site-packages")
        )
        venv_python_path = os.path.join(venv_path, "bin")
        command_env = {
            "PYTHONPATH": venv_python_path,
            "PATH": venv_python_path + ":" + venv_site_packages_path,
            "VENV_PATH": venv_path,
        }

        # Create the virtualenv
        current_interpreter.create_venv(recreate=True, path=str(venv_path))

        # Check exists and is empty of packages
        result = run_cmd(
            ["python", "-m", "pip", "freeze"], stdout=subprocess.PIPE, env=command_env
        )
        assert os.path.isdir(venv_path)
        assert result.stdout == ""

        # return the cmmand environment to reuse in other commands
        yield command_env

        assert os.path.isdir(venv_path)
    finally:
        if venv_path:
            shutil.rmtree(venv_path, ignore_errors=True)


@pytest.mark.parametrize(
    "v1,v2,equal",
    [
        (3.6, 3.6, True),
        (3.6, "3.6", True),
        ("3.6", "3.6", True),
        ("3.6", 3.6, True),
        (3.6, 3.7, False),
        (3.6, "3.7", False),
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
        command="echo test",
        env={"env": "test"},
        name="test",
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
        command="echo test",
        env={"env": "test"},
        name="test",
        pkgs={"pip": ""},
        parent=VenvInstance(
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
        "137331a",
        ".*733.*",
        "[0-9]*a",
        "^137331a",
        "137331a$",
        "^137331a$",
        "^(no_match)|(137331a)$",
    ],
)
def test_venv_name_matching(pattern: str) -> None:
    venv = VenvInstance(
        command="echo test",
        env={"env": "test"},
        name="test",
        pkgs={"pip": ""},
        py=Interpreter("3"),
    )
    assert venv.short_hash == "137331a"
    assert venv.matches_pattern(re.compile(pattern))


def test_interpreter_venv_creation(interpreter_virtualenv: Dict[str, str]) -> None:
    venv = interpreter_virtualenv

    run_cmd(
        ["python", "-m", "pip", "install", "itsdangerous==2.1.2"],
        stdout=subprocess.PIPE,
        env=venv,
    )
    result = run_cmd(
        ["python", "-m", "pip", "freeze"], stdout=subprocess.PIPE, env=venv
    )
    assert result.stdout == "itsdangerous==2.1.2\n"


def test_interpreter_venv_recreation(
    current_interpreter: Interpreter, interpreter_virtualenv: Dict[str, str]
) -> None:
    venv = interpreter_virtualenv

    run_cmd(
        ["python", "-m", "pip", "install", "itsdangerous==2.1.2"],
        stdout=subprocess.PIPE,
        env=venv,
    )

    current_interpreter.create_venv(recreate=True, path=str(venv["VENV_PATH"]))

    result = run_cmd(
        ["python", "-m", "pip", "freeze"], stdout=subprocess.PIPE, env=venv
    )
    assert result.stdout == ""
