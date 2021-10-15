import os
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, Generator, Optional, Sequence, Union

import pytest
from riot.riot import _T_CompletedProcess
from typing_extensions import Protocol

_T_Path = Union[str, "os.PathLike[Any]"]


def run(
    args: Union[str, Sequence[str]], cwd: _T_Path, env: Optional[Dict[str, str]] = None
) -> _T_CompletedProcess:
    return subprocess.run(
        args,
        env=env,
        encoding=sys.getdefaultencoding(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        shell=isinstance(args, str),
    )


class _T_TmpRun(Protocol):
    def __call__(
        self,
        args: Union[str, Sequence[str]],
        cwd: Optional[_T_Path] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> _T_CompletedProcess:
        ...


@pytest.fixture
def tmp_run(tmp_path: pathlib.Path) -> Generator[_T_TmpRun, None, None]:
    """Run a command by default in tmp_path."""

    def _run(
        args: Union[str, Sequence[str]],
        cwd: Optional[_T_Path] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> _T_CompletedProcess:
        if cwd is None:
            cwd = tmp_path
        return run(args, cwd, env)

    yield _run


def test_no_riotfile(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
    result = tmp_run("riot")
    assert (
        result.stdout
        == """
Usage: riot [OPTIONS] COMMAND [ARGS]...

Options:
  -f, --file PATH  [default: riotfile.py]
  -v, --verbose
  -d, --debug
  -P, --pipe       Pipe mode. Makes riot emit plain output.
  --version        Show the version and exit.
  --help           Show this message and exit.

Commands:
  generate  Generate base virtual environments.
  list      List all virtual env instances matching a pattern.
  run       Run virtualenv instances with names matching a pattern.
  shell     Launch a shell inside a venv.
""".lstrip()
    )
    assert result.stderr == ""
    assert result.returncode == 0

    result = tmp_run("riot -P list")
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


def test_bad_riotfile(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
    result = tmp_run("riot --file rf.py", tmp_path)
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
    result = tmp_run("riot --file rf list")
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
    result = tmp_run("riot --file riotfile.py list")
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
""".strip()
        in result.stderr
    )
    assert result.returncode == 1


def test_help(tmp_run: _T_TmpRun) -> None:
    result = tmp_run("riot --help")
    assert (
        result.stdout
        == """
Usage: riot [OPTIONS] COMMAND [ARGS]...

Options:
  -f, --file PATH  [default: riotfile.py]
  -v, --verbose
  -d, --debug
  -P, --pipe       Pipe mode. Makes riot emit plain output.
  --version        Show the version and exit.
  --help           Show this message and exit.

Commands:
  generate  Generate base virtual environments.
  list      List all virtual env instances matching a pattern.
  run       Run virtualenv instances with names matching a pattern.
  shell     Launch a shell inside a venv.
""".lstrip()
    )
    assert result.stderr == ""
    assert result.returncode == 0


def test_version(tmp_run: _T_TmpRun) -> None:
    result = tmp_run("riot --version")
    assert result.stdout.startswith("riot, version ")
    assert result.stderr == ""
    assert result.returncode == 0


def test_list_no_file_empty_file(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
    result = tmp_run("riot -P list")
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
    result = tmp_run("riot -P list")
    assert result.stderr == ""
    assert result.stdout == ""
    assert result.returncode == 0


def test_list_configurations(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
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
    result = tmp_run("riot -P list")
    assert result.stderr == ""
    assert (
        result.stdout
        == "[#0]  1c31170  test          Interpreter(_hint='3') Packages()\n"
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
    }
)
""",
    )
    result = tmp_run("riot -P list")
    assert result.stderr == ""
    assert re.search(
        r"""
\[\#0\]  [0-9a-f]{7}  test  .* Packages\('pkg1==1.0'\)
\[\#1\]  [0-9a-f]{7}  test  .* Packages\('pkg1==2.0'\)
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
    result = tmp_run("riot -P list")
    assert result.stderr == ""
    assert re.search(
        r"""
\[\#0\]  [0-9a-f]{7}  test  .* Packages\('pkg1==1.0' 'pkg2==2.0'\)
\[\#1\]  [0-9a-f]{7}  test  .* Packages\('pkg1==1.0' 'pkg2==3.0'\)
\[\#2\]  [0-9a-f]{7}  test  .* Packages\('pkg1==2.0' 'pkg2==2.0'\)
\[\#3\]  [0-9a-f]{7}  test  .* Packages\('pkg1==2.0' 'pkg2==3.0'\)
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
    result = tmp_run("riot -P list")
    assert result.stderr == ""
    assert re.search(
        r"""
\[\#0\]  [0-9a-f]{7}  test1  .* Packages\('pkg1==1.0' 'pkg2==3.0'\)
\[\#1\]  [0-9a-f]{7}  test1  .* Packages\('pkg1==1.0' 'pkg2==4.0'\)
\[\#2\]  [0-9a-f]{7}  test1  .* Packages\('pkg1==2.0' 'pkg2==3.0'\)
\[\#3\]  [0-9a-f]{7}  test1  .* Packages\('pkg1==2.0' 'pkg2==4.0'\)
\[\#4\]  [0-9a-f]{7}  test2  .* Packages\('pkg1==1.0' 'pkg2==3.0'\)
\[\#5\]  [0-9a-f]{7}  test2  .* Packages\('pkg1==1.0' 'pkg2==4.0'\)
\[\#6\]  [0-9a-f]{7}  test2  .* Packages\('pkg1==2.0' 'pkg2==3.0'\)
\[\#7\]  [0-9a-f]{7}  test2  .* Packages\('pkg1==2.0' 'pkg2==4.0'\)
""".lstrip(),
        result.stdout,
    )
    assert result.returncode == 0


def test_list_filter(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
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
    result = tmp_run("riot -P list test")
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
    result = tmp_run("riot -P list test")
    assert result.stderr == ""
    assert re.search(
        r"""
\[\#0\]  [0-9a-f]{7}  test  .* Packages\('pkg1==1.0' 'pkg2==2.0'\)
\[\#1\]  [0-9a-f]{7}  test  .* Packages\('pkg1==1.0' 'pkg2==3.0'\)
\[\#2\]  [0-9a-f]{7}  test  .* Packages\('pkg1==2.0' 'pkg2==2.0'\)
\[\#3\]  [0-9a-f]{7}  test  .* Packages\('pkg1==2.0' 'pkg2==3.0'\)
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
    result = tmp_run("riot -P list test2")
    assert result.stderr == ""
    assert re.search(
        r"""
\[\#4\]  [0-9a-f]{7}  test2  .* Packages\('pkg1==1.0' 'pkg2==3.0'\)
\[\#5\]  [0-9a-f]{7}  test2  .* Packages\('pkg1==1.0' 'pkg2==4.0'\)
\[\#6\]  [0-9a-f]{7}  test2  .* Packages\('pkg1==2.0' 'pkg2==3.0'\)
\[\#7\]  [0-9a-f]{7}  test2  .* Packages\('pkg1==2.0' 'pkg2==4.0'\)
""".lstrip(),
        result.stdout,
    )
    assert result.returncode == 0


def test_run(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
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
    result = tmp_run("riot run -s pass")
    assert result.returncode == 0, result.stderr
    assert re.search(
        r"""
============================= test session starts ==============================
platform.*
rootdir:.*
collected 1 item

test_success.py .*

============================== 1 passed in .*s ===============================

-------------------summary-------------------
✓ pass: .*
1 passed with 0 warnings, 0 failed\n""".lstrip(),
        result.stdout,
    ), result.stdout
    assert result.stderr == ""

    result = tmp_run("riot run -s fail")
    assert (
        "x fail:  pythonInterpreter(_hint='3') 'pytest'\n" in result.stdout
    ), result.stdout
    assert result.stderr == ""
    assert result.returncode == 1


def test_run_cmdargs(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
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
    result = tmp_run("riot run -s test_cmdargs -- -k filter")
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
    result = tmp_run("riot run -s test_cmdargs -- -k filter")
    assert "cmdargs=-k filter" in result.stdout
    assert result.stderr == ""
    assert result.returncode == 0


def test_dev_install_fail(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
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
    result = tmp_run("riot run test")
    assert 'File "setup.py"' in result.stderr, result.stderr
    assert "Dev install failed, aborting!" in result.stderr, result.stderr
    assert result.returncode == 1


def test_bad_interpreter(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
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
    result = tmp_run("riot run -s -pDNE test")
    assert (
        """
FileNotFoundError: Python interpreter DNE not found
""".strip()
        in result.stderr
    )
    assert result.returncode == 1


def test_interpreter_pythonpath(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    pys=[3],
    name="test",
    command="env",
)
""",
    )
    result = tmp_run("riot run -s test")
    env = dict(_.split("=", maxsplit=1) for _ in result.stdout.splitlines() if "=" in _)
    assert result.returncode == 0

    version = "".join((str(_) for _ in sys.version_info[:3]))
    py_dot_version = ".".join((str(_) for _ in sys.version_info[:2]))
    assert env["PYTHONPATH"] == ":".join(
        (
            "",
            str(tmp_path),
            str(
                tmp_path
                / os.path.join(
                    ".riot",
                    f"venv_py{version}",
                    "lib",
                    f"python{py_dot_version}",
                    "site-packages",
                )
            ),
        )
    )


def test_venv_instance_pythonpath(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    pys=[3],
    pkgs={"pip": ""},
    name="test",
    command="env",
    venvs=[Venv(pkgs={"pytest": ""})]
)
""",
    )
    result = tmp_run("riot run -s test")
    env = dict(_.split("=") for _ in result.stdout.splitlines() if "=" in _)
    assert result.returncode == 0

    version = "".join((str(_) for _ in sys.version_info[:3]))

    venv_name = f"venv_py{version}_pytest"
    parent_venv_name = f"venv_py{version}_pip"
    py_dot_version = ".".join((str(_) for _ in sys.version_info[:2]))

    py_venv_path = str(
        tmp_path
        / os.path.join(
            ".riot",
            f"venv_py{version}",
            "lib",
            "python{}".format(py_dot_version),
            "site-packages",
        )
    )

    parent_venv_path = str(
        tmp_path
        / os.path.join(
            ".riot",
            parent_venv_name,
            "lib",
            "python{}".format(py_dot_version),
            "site-packages",
        )
    )

    venv_path = str(
        tmp_path
        / os.path.join(
            ".riot",
            venv_name,
            "lib",
            "python{}".format(py_dot_version),
            "site-packages",
        )
    )

    paths = env["PYTHONPATH"].split(":")
    assert paths == ["", str(tmp_path), venv_path, parent_venv_path, py_venv_path]


def test_venv_instance_path(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    pys=[3],
    pkgs={"pip": ""},
    name="test",
    command="env",
    venvs=[Venv(pkgs={"pytest": ""})]
)
""",
    )
    result = tmp_run("riot run -s test")
    env = dict(_.split("=") for _ in result.stdout.splitlines() if "=" in _)
    assert result.returncode == 0, result.stderr

    venv_name = "venv_py{}_pytest".format(
        "".join((str(_) for _ in sys.version_info[:3]))
    )
    parent_venv_name = "venv_py{}_pip".format(
        "".join((str(_) for _ in sys.version_info[:3]))
    )

    parent_venv_path = str(
        tmp_path
        / os.path.join(
            ".riot",
            parent_venv_name,
            "bin",
        )
    )

    venv_path = str(
        tmp_path
        / os.path.join(
            ".riot",
            venv_name,
            "bin",
        )
    )

    paths = env["PATH"].split(":")
    assert paths.index(venv_path) < paths.index(parent_venv_path)


def test_env_bubble_up(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    pys=[3],
    pkgs={"pip": ""},
    name="test",
    command="env",
    env={"foo": "42", "baz": "stillthesame"},
    venvs=[Venv(pkgs={"pytest": ""}, env={"bar": "43", "foo": "40"})],
)
""",
    )
    result = tmp_run("riot -v run -s test")
    print(result.stdout)
    env = dict(_.split("=", maxsplit=1) for _ in result.stdout.splitlines() if "=" in _)
    assert result.returncode == 0, (result.stdout, result.stderr)

    assert env["foo"] == "40"
    assert env["bar"] == "43"
    assert env["baz"] == "stillthesame"


def test_create(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv
venv = Venv(
    name="test",
    pys=[3],
    pkgs={"pip": ""},
    venvs=[
        Venv(
            name="child",
            pkgs={"pytest": ""},
            create=True,
            command="echo $PYTHONPATH",
        ),
    ],
)
""",
    )
    result = tmp_run("riot -Pv run -s child")
    venv_path = tmp_path / ".riot/venv_py{}_pytest_pip".format(
        "".join((str(_) for _ in sys.version_info[:3]))
    )
    assert f"Creating virtualenv '{venv_path}'" in result.stderr, result.stderr
    assert (
        f"Running command 'echo $PYTHONPATH' in venv '{venv_path}'" in result.stderr
    ), result.stderr
    assert result.stdout.startswith(":".join(("", str(tmp_path))))
    assert result.returncode == 0


def test_extras(tmp_path: pathlib.Path, tmp_run: _T_TmpRun) -> None:
    rf_path = tmp_path / "riotfile.py"
    rf_path.write_text(
        """
from riot import Venv, latest
venv = Venv(
    name="test",
    pys=["3"],
    pkgs={"requests[socks]": latest},
    command="python -c 'import requests'",
)
""",
    )
    result = tmp_run("riot -v run -s test")
    assert result.returncode == 0
