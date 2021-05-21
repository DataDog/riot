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


def test_interpreter_version(current_interpreter: Interpreter) -> None:
    version = "%s.%s.%s" % (
        sys.version_info.major,
        sys.version_info.minor,
        sys.version_info.micro,
    )
    assert current_interpreter.version() == version


def test_interpreter_version_info(current_interpreter: Interpreter) -> None:
    assert current_interpreter.version_info() == sys.version_info[:3]
