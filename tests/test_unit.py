import sys

import pytest
from riot.riot import Interpreter


@pytest.fixture
def current_interpreter() -> Interpreter:
    version = ".".join((str(sys.version_info[0]), str(sys.version_info[1])))
    return Interpreter(version)


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
    assert current_interpreter.venv_path() == ".riot/venv_py{}".format(py_version)


def test_sitepackages_path(current_interpreter: Interpreter) -> None:
    py_full_version = "".join((str(_) for _ in sys.version_info[:3]))
    py_dot_version = ".".join((str(_) for _ in sys.version_info[:2]))

    expected = ".riot/venv_py{}/lib/python{}/site-packages".format(
        py_full_version, py_dot_version
    )
    assert current_interpreter.site_packages_path().endswith(expected)
