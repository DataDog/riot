import os
import re
import site
import sys

import mock
import pytest
from riot.riot import (Interpreter, Venv, get_python_sitepackages,
                       get_venv_sitepackages)

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


def test_interpreter_pythonpath(current_interpreter: Interpreter) -> None:
    assert current_interpreter.pythonpath == ":".join(site.getsitepackages())


def test_venv_instance_pythonpath(current_venv: Venv) -> None:
    """Test the value of VenvInstance.pythonpath.

    The result from VenvInstance.pythonpath
      When no VenvInstance.pkgs are defined
        Will be the Interpreter.pythonpath
    """
    instances = list(current_venv.instances(default_venv_pattern))
    assert instances
    for instance in instances:
        assert instance.pythonpath == instance.py.pythonpath


@pytest.mark.skip(reason="turn into integration test")
def test_venv_instance_with_pkgs_pythonpath(current_venv: Venv) -> None:
    """Test the value of VenvInstance.pythonpath.

    The result from VenvInstance.pythonpath
      When there are VenvInstance.pkgs defined
        Will be the Interpreter.pythonpath + ":" + the virtual envs site-packages
    """
    current_venv.pkgs = {"flask": [""]}
    instances = list(current_venv.instances(default_venv_pattern))
    assert instances
    for instance in instances:
        venv_sitepackages = [
            os.path.abspath(
                ".riot/venv_py394_flask/lib/python%s/site-packages" % (current_py_hint,)
            )
        ]
        # We cannot run venv commands in tests, so we have to mock this
        with mock.patch("riot.riot.get_venv_sitepackages") as m:
            m.return_value = venv_sitepackages

            expected = ":".join([instance.py.pythonpath] + venv_sitepackages)
            assert instance.pythonpath == expected
