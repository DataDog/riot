import re

import pytest

from .proctest import TestDir


@pytest.fixture
def tdir():
    yield TestDir()


def test_no_riotfile(tdir: TestDir) -> None:
    result = tdir.run("riot")
    assert (
        result.stdout
        == """
Usage: riot [OPTIONS] COMMAND [ARGS]...

Options:
  -f, --file PATH  [default: riotfile.py]
  -v, --verbose
  -d, --debug
  --version        Show the version and exit.
  --help           Show this message and exit.

Commands:
  generate  Generate base virtual environments.
  list      List all virtual env instances matching a pattern.
  run       Run virtualenv instances with names matching a pattern.
""".lstrip()
    )
    assert result.stderr == ""
    assert result.returncode == 0

    result = tdir.run("riot list")
    assert (
        result.stderr
        == """
Usage: riot [OPTIONS] COMMAND [ARGS]...
Try 'riot --help' for help.

Error: Invalid value for '-f' / '--file': Path 'riotfile.py' does not exist.
""".lstrip()
    )
    assert result.stdout == ""
    assert result.returncode == 2


def test_bad_riotfile(tdir: TestDir) -> None:
    result = tdir.run("riot --file rf.py")
    assert (
        result.stderr
        == """
Usage: riot [OPTIONS] COMMAND [ARGS]...
Try 'riot --help' for help.

Error: Invalid value for '-f' / '--file': Path 'rf.py' does not exist.
""".lstrip()
    )
    assert result.returncode == 2

    tdir.mkfile(
        "rf",
        """
from riot import Venv
venv = Venv()
""",
    )
    result = tdir.run("riot --file rf list")
    assert (
        result.stderr
        == """
Failed to construct config file:
Invalid file format for riotfile. Expected file with .py extension got 'rf'.
""".lstrip()
    )
    assert result.returncode == 1

    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv()typo1234
""",
    )
    result = tdir.run("riot --file riotfile.py list")
    assert (
        """
Failed to construct config file:
Failed to parse riotfile 'riotfile.py'.
""".lstrip()
        in result.stderr
    )
    assert (
        """
SyntaxError: invalid syntax
""".lstrip()
        in result.stderr
    )
    assert result.returncode == 1


def test_help(tdir: TestDir) -> None:
    result = tdir.run("riot --help")
    assert (
        result.stdout
        == """
Usage: riot [OPTIONS] COMMAND [ARGS]...

Options:
  -f, --file PATH  [default: riotfile.py]
  -v, --verbose
  -d, --debug
  --version        Show the version and exit.
  --help           Show this message and exit.

Commands:
  generate  Generate base virtual environments.
  list      List all virtual env instances matching a pattern.
  run       Run virtualenv instances with names matching a pattern.
""".lstrip()
    )
    assert result.stderr == ""
    assert result.returncode == 0


def test_version(tdir: TestDir) -> None:
    result = tdir.run("riot --version")
    assert result.stdout.startswith("riot, version ")
    assert result.stderr == ""
    assert result.returncode == 0


def test_list_no_file_empty_file(tdir: TestDir) -> None:
    result = tdir.run("riot list")
    assert (
        result.stderr
        == """
Usage: riot [OPTIONS] COMMAND [ARGS]...
Try 'riot --help' for help.

Error: Invalid value for '-f' / '--file': Path 'riotfile.py' does not exist.
""".lstrip()
    )
    assert result.returncode == 2

    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
""",
    )
    result = tdir.run("riot list")
    assert result.stderr == ""
    assert result.stdout == ""
    assert result.returncode == 0


def test_list_configurations(tdir: TestDir) -> None:
    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    name="test",
    pys=[3],
    command="echo hi",
)
""",
    )
    result = tdir.run("riot list")
    assert result.stderr == ""
    assert result.stdout == "test  Interpreter(_hint='3') \n"
    assert result.returncode == 0

    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    name="test",
    pys=[3],
    command="echo hi",
    pkgs={
        "pkg1": ["==1.0", "==2.0"],
    }
)
""",
    )
    result = tdir.run("riot list")
    assert result.stderr == ""
    assert re.search(
        r"""
test  .* 'pkg1==1.0'
test  .* 'pkg1==2.0'
""".lstrip(),
        result.stdout,
    )
    assert result.returncode == 0

    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    name="test",
    pys=[3],
    command="echo hi",
    pkgs={
        "pkg1": ["==1.0", "==2.0"],
        "pkg2": ["==2.0", "==3.0"],
    }
)
""",
    )
    result = tdir.run("riot list")
    assert result.stderr == ""
    assert re.search(
        r"""
test  .* 'pkg1==1.0' 'pkg2==2.0'
test  .* 'pkg1==1.0' 'pkg2==3.0'
test  .* 'pkg1==2.0' 'pkg2==2.0'
test  .* 'pkg1==2.0' 'pkg2==3.0'
""".lstrip(),
        result.stdout,
    )
    assert result.returncode == 0

    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    pys=[3],
    venvs=[
        Venv(
            name="test1",
            command="echo hi",
            pkgs={
                "pkg1": ["==1.0", "==2.0"],
                "pkg2": ["==3.0", "==4.0"],
            }
        ),
        Venv(
            name="test2",
            command="echo hi",
            pkgs={
                "pkg1": ["==1.0", "==2.0"],
                "pkg2": ["==3.0", "==4.0"],
            }
        ),
    ]
)
""",
    )
    result = tdir.run("riot list")
    assert result.stderr == ""
    assert re.search(
        r"""
test1  .* 'pkg1==1.0' 'pkg2==3.0'
test1  .* 'pkg1==1.0' 'pkg2==4.0'
test1  .* 'pkg1==2.0' 'pkg2==3.0'
test1  .* 'pkg1==2.0' 'pkg2==4.0'
test2  .* 'pkg1==1.0' 'pkg2==3.0'
test2  .* 'pkg1==1.0' 'pkg2==4.0'
test2  .* 'pkg1==2.0' 'pkg2==3.0'
test2  .* 'pkg1==2.0' 'pkg2==4.0'
""".lstrip(),
        result.stdout,
    )
    assert result.returncode == 0


def test_list_filter(tdir: TestDir) -> None:
    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    name="test",
    pys=[3],
    command="echo hi",
)
""",
    )
    result = tdir.run("riot list test")
    assert result.stderr == ""
    assert re.search(r"test .*", result.stdout)
    assert result.returncode == 0

    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    name="test",
    pys=[3],
    command="echo hi",
    pkgs={
        "pkg1": ["==1.0", "==2.0"],
        "pkg2": ["==2.0", "==3.0"],
    }
)
""",
    )
    result = tdir.run("riot list test")
    assert result.stderr == ""
    assert re.search(
        r"""
test  .* 'pkg1==1.0' 'pkg2==2.0'
test  .* 'pkg1==1.0' 'pkg2==3.0'
test  .* 'pkg1==2.0' 'pkg2==2.0'
test  .* 'pkg1==2.0' 'pkg2==3.0'
""".lstrip(),
        result.stdout,
    )
    assert result.returncode == 0

    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    pys=[3],
    venvs=[
        Venv(
            name="test1",
            command="echo hi",
            pkgs={
                "pkg1": ["==1.0", "==2.0"],
                "pkg2": ["==3.0", "==4.0"],
            }
        ),
        Venv(
            name="test2",
            command="echo hi",
            pkgs={
                "pkg1": ["==1.0", "==2.0"],
                "pkg2": ["==3.0", "==4.0"],
            }
        ),
    ]
)
""",
    )
    result = tdir.run("riot list test2")
    assert result.stderr == ""
    assert re.search(
        r"""
test2  .* 'pkg1==1.0' 'pkg2==3.0'
test2  .* 'pkg1==1.0' 'pkg2==4.0'
test2  .* 'pkg1==2.0' 'pkg2==3.0'
test2  .* 'pkg1==2.0' 'pkg2==4.0'
""".lstrip(),
        result.stdout,
    )
    assert result.returncode == 0


def test_run(tdir: TestDir) -> None:
    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    pys=[3],
    pkgs={
        "pytest": [""],
    },
    venvs=[
        Venv(
            name="pass",
            command="pytest test_success.py",
        ),
        Venv(
            name="fail",
            command="pytest test_failure.py",
        ),
    ],
)
""",
    )
    tdir.mkfile(
        "test_success.py",
        """
def test_success():
    assert 1 == 1
""",
    )
    tdir.mkfile(
        "test_failure.py",
        """
def test_failure():
    assert 1 == 0
""",
    )
    result = tdir.run("riot run -s pass")
    assert re.search(
        r"""
============================= test session starts ==============================
platform.*
rootdir:.*
collected 1 item

test_success.py .*

============================== 1 passed in .*s ===============================

-------------------summary-------------------
✔️  pass: .* 'pytest'\n""".lstrip(),
        result.stdout,
    )
    assert result.stderr == ""
    assert result.returncode == 0

    result = tdir.run("riot run -s fail")
    assert "✖️  fail:  Interpreter(_hint='3') 'pytest'\n" in result.stdout
    assert result.stderr == ""
    assert result.returncode == 1


def test_run_cmdargs(tdir: TestDir) -> None:
    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    pys=[3],
    name="test_cmdargs",
    command="echo hi",
)
""",
    )
    result = tdir.run("riot run -s test_cmdargs -- -k filter")
    assert "cmdargs=-k filter" not in result.stdout
    assert result.stderr == ""
    assert result.returncode == 0

    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    pys=3,
    name="test_cmdargs",
    command="echo cmdargs={cmdargs}",
)
""",
    )
    result = tdir.run("riot run -s test_cmdargs -- -k filter")
    assert "cmdargs=-k filter" in result.stdout
    assert result.stderr == ""
    assert result.returncode == 0


def test_dev_install_fail(tdir: TestDir) -> None:
    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    pys=3,
    name="test",
    command="echo hello",
)
""",
    )
    result = tdir.run("riot run test")
    assert (
        """
ERROR: File "setup.py" not found. Directory cannot be installed in editable mode:
""".strip()
        in result.stderr
    )
    assert "Dev install failed, aborting!" in result.stderr
    assert result.stdout == ""
    assert result.returncode == 1


def test_bad_interpreter(tdir: TestDir) -> None:
    tdir.mkfile(
        "riotfile.py",
        """
from riot import Venv
venv = Venv(
    pys="DNE",
    name="test",
    command="echo hello",
)
""",
    )
    result = tdir.run("riot run -s -pDNE test")
    assert (
        """
FileNotFoundError: Python interpreter DNE not found
""".strip()
        in result.stderr
    )
    assert result.stdout == ""
    assert result.returncode == 1
