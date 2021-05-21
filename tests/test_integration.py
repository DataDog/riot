import os
import pathlib
import re
import subprocess
import sys
from typing import Any
from typing import Dict
from typing import Optional
from typing import Sequence
from typing import Union

import pytest

from riot.riot import _T_CompletedProcess


_T_Path = Union[str, "os.PathLike[Any]"]


def run(args: Union[str, Sequence[str]], cwd: _T_Path, env: Optional[Dict[str, str]] = None) -> _T_CompletedProcess:
    if isinstance(args, str):
        args = args.split(" ")

    return subprocess.run(
        args,
        env=env,
        encoding=sys.getdefaultencoding(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
    )


def test_no_riotfile(tmp_path: pathlib.Path) -> None:
    result = run("riot", cwd=tmp_path)
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

    result = run("riot list", cwd=tmp_path)
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


def test_bad_riotfile(tmp_path: pathlib.Path) -> None:
    result = run("riot --file rf.py", tmp_path)
    assert (
        result.stderr
        == """
Usage: riot [OPTIONS] COMMAND [ARGS]...
Try 'riot --help' for help.

Error: Invalid value for '-f' / '--file': Path 'rf.py' does not exist.
""".lstrip()
    )
    assert result.returncode == 2

    rf_path = tmp_path / "rf"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv()
""",
    )
    result = run("riot --file rf list", cwd=tmp_path)
    assert (
        result.stderr
        == """
Failed to construct config file:
Invalid file format for riotfile. Expected file with .py extension got 'rf'.
""".lstrip()
    )
    assert result.returncode == 1

    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv()typo1234
""",
    )
    result = run("riot --file riotfile.py list", cwd=tmp_path)
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


def test_help(tmp_path: pathlib.Path) -> None:
    result = run("riot --help", cwd=tmp_path)
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


def test_version(tmp_path: pathlib.Path) -> None:
    result = run("riot --version", cwd=tmp_path)
    assert result.stdout.startswith("riot, version ")
    assert result.stderr == ""
    assert result.returncode == 0


def test_list_no_file_empty_file(tmp_path: pathlib.Path) -> None:
    result = run("riot list", cwd=tmp_path)
    assert (
        result.stderr
        == """
Usage: riot [OPTIONS] COMMAND [ARGS]...
Try 'riot --help' for help.

Error: Invalid value for '-f' / '--file': Path 'riotfile.py' does not exist.
""".lstrip()
    )
    assert result.returncode == 2

    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
""",
    )
    result = run("riot list", cwd=tmp_path)
    assert result.stderr == ""
    assert result.stdout == ""
    assert result.returncode == 0

def test_list_configurations(tmp_path: pathlib.Path) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    name="test",
    pys=[3],
    command="echo hi",
)
""",
    )
    result = run("riot list", cwd=tmp_path)
    assert result.stderr == ""
    assert result.stdout == "test  Interpreter(_hint='3') \n"
    assert result.returncode == 0

    rf_path.write_text(
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
    result = run("riot list", cwd=tmp_path)
    assert result.stderr == ""
    assert re.search(
        r"""
test  .* 'pkg1==1.0'
test  .* 'pkg1==2.0'
""".lstrip(),
        result.stdout,
    )
    assert result.returncode == 0

    rf_path.write_text(
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
    result = run("riot list", cwd=tmp_path)
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

    rf_path.write_text(
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
    result = run("riot list", cwd=tmp_path)
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


def test_list_filter(tmp_path: pathlib.Path) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    name="test",
    pys=[3],
    command="echo hi",
)
""",
    )
    result = run("riot list test", cwd=tmp_path)
    assert result.stderr == ""
    assert re.search(r"test .*", result.stdout)
    assert result.returncode == 0

    rf_path.write_text(
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
    result = run("riot list test", cwd=tmp_path)
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

    rf_path.write_text(
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
    result = run("riot list test2", cwd=tmp_path)
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


def test_run(tmp_path: pathlib.Path) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
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
    success_path = tmp_path / "test_success.py"
    success_path.write_text(
        """
def test_success():
    assert 1 == 1
""",
    )
    fail_path = tmp_path / "test_failure.py"
    fail_path.write_text(
        """
def test_failure():
    assert 1 == 0
""",
    )
    result = run("riot run -s pass", cwd=tmp_path)
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

    result = run("riot run -s fail", cwd=tmp_path)
    assert "✖️  fail:  Interpreter(_hint='3') 'pytest'\n" in result.stdout
    assert result.stderr == ""
    assert result.returncode == 1

def test_run_cmdargs(tmp_path: pathlib.Path) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    pys=[3],
    name="test_cmdargs",
    command="echo hi",
)
""",
    )
    result = run("riot run -s test_cmdargs -- -k filter", cwd=tmp_path)
    assert "cmdargs=-k filter" not in result.stdout
    assert result.stderr == ""
    assert result.returncode == 0

    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    pys=3,
    name="test_cmdargs",
    command="echo cmdargs={cmdargs}",
)
""",
    )
    result = run("riot run -s test_cmdargs -- -k filter", cwd=tmp_path)
    assert "cmdargs=-k filter" in result.stdout
    assert result.stderr == ""
    assert result.returncode == 0


def test_dev_install_fail(tmp_path: pathlib.Path) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    pys=3,
    name="test",
    command="echo hello",
)
""",
    )
    result = run("riot run test", cwd=tmp_path)
    assert (
        """
ERROR: File "setup.py" not found. Directory cannot be installed in editable mode:
""".strip()
        in result.stderr
    )
    assert "Dev install failed, aborting!" in result.stderr
    assert result.stdout == ""
    assert result.returncode == 1


def test_bad_interpreter(tmp_path: pathlib.Path) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    pys="DNE",
    name="test",
    command="echo hello",
)
""",
    )
    result = run("riot run -s -pDNE test", cwd=tmp_path)
    assert (
        """
FileNotFoundError: Python interpreter DNE not found
""".strip()
        in result.stderr
    )
    assert result.stdout == ""
    assert result.returncode == 1
