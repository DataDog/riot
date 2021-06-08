import os
import re
import site
import sys

import mock
import pytest
from riot.riot import Interpreter, Venv

default_venv_pattern = re.compile(r".*")
current_py_hint = "%s.%s" % (sys.version_info.major, sys.version_info.minor)


@pytest.fixture
def current_interpreter() -> Interpreter:
    return Interpreter(current_py_hint)


@pytest.fixture
def current_venv() -> Venv:
    # Without a command `.instances()` will not resolve anything
    return Venv(pys=[current_py_hint], command="echo test")


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


def test_venv_path(current_interpreter: Interpreter) -> None:
    py_version = "".join((str(_) for _ in sys.version_info[:3]))
    assert current_interpreter.venv_path() == os.path.join(
        ".riot", "venv_py{}".format(py_version)
    )


def test_sitepackages_path(current_interpreter: Interpreter) -> None:
    py_dot_version = ".".join((str(_) for _ in sys.version_info[:2]))

    expected = os.path.abspath(
        os.path.join(
            current_interpreter.venv_path(),
            "lib",
            "python{}".format(py_dot_version),
            "site-packages",
        )
    )
    assert current_interpreter.site_packages_path() == expected


def test_venv_instance_venv_path(current_interpreter: Interpreter) -> None:
    venv = VenvInstance(
        command="echo test",
        env=(("env", "test"),),
        name="test",
        pkgs=(("flask", ""),),
        py=current_interpreter,
    )

    py_version = "".join((str(_) for _ in sys.version_info[:3]))
    assert venv.venv_path() == os.path.join(
        ".riot", "venv_py{}_flask".format(py_version)
    )


def test_venv_instance_site_packages_path(current_interpreter: Interpreter) -> None:
    venv = VenvInstance(
        command="echo test",
        env=(("env", "test"),),
        name="test",
        pkgs=(("flask", ""),),
        py=current_interpreter,
    )

    py_dot_version = ".".join((str(_) for _ in sys.version_info[:2]))

    expected = os.path.abspath(
        os.path.join(
            venv.venv_path(),
            "lib",
            "python{}".format(py_dot_version),
            "site-packages",
        )
    )
    assert venv.site_packages_path() == expected


def test_interpreter_version(current_interpreter: Interpreter) -> None:
    version = "%s.%s.%s" % (
        sys.version_info.major,
        sys.version_info.minor,
        sys.version_info.micro,
    )
    assert current_interpreter.version() == version


def test_interpreter_version_info(current_interpreter: Interpreter) -> None:
    assert current_interpreter.version_info() == sys.version_info[:3]
