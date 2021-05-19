import os
import sys
import tempfile
import typing

import pytest
from riot.riot import Interpreter, Venv


@pytest.fixture
def current_py_hint() -> str:
    return "%s.%s" % (sys.version_info.major, sys.version_info.minor)


@pytest.fixture
def current_interpreter(current_py_hint: str) -> Interpreter:
    return Interpreter(current_py_hint)


@pytest.fixture
def current_venv(current_py_hint: str) -> Venv:
    # Without a command `.instances()` will not resolve anything
    return Venv(pys=[current_py_hint], command="echo test")


@pytest.fixture
def temp_dir() -> typing.Generator[str, None, None]:
    cur_dir = os.getcwd()
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        try:
            yield temp_dir
        finally:
            os.chdir(cur_dir)
