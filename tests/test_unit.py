import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, Generator, List

import pytest
import riot.riot as riot_module
from riot.riot import (
    install_dev_pkg,
    Interpreter,
    run_cmd,
    Session,
    Venv,
    VenvInstance,
)
from tests.test_cli import DATA_DIR

RIOT_TESTS_PATH = os.path.join(os.path.dirname(__file__), ".riot")
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

        # Create the virtualenv
        current_interpreter.create_venv(recreate=True, path=command_env["VENV_PATH"])

        # Check folder exists and is empty of packages
        result = _get_pip_freeze(command_env)
        assert os.path.isdir(command_env["VENV_PATH"])
        assert result == ""

        # return the command environment to reuse in other commands
        yield command_env

        assert os.path.isdir(command_env["VENV_PATH"])
    finally:
        shutil.rmtree(RIOT_TESTS_PATH, ignore_errors=True)


@pytest.fixture
def session_virtualenv() -> Generator[Session, None, None]:
    try:
        session = Session.from_config_file(os.path.join(DATA_DIR, "nested_riotfile.py"))
        os.environ["RIOT_ENV_BASE_PATH"] = RIOT_TESTS_PATH

        session.generate_base_venvs(re.compile(""), True, False, set())
        yield session
    finally:
        shutil.rmtree(RIOT_TESTS_PATH, ignore_errors=True)


def _get_env(env_name: str) -> Dict[str, str]:
    """Return a dictionary with riot venv paths to add to the environment."""
    venv_path = os.path.join(RIOT_TESTS_PATH, env_name)
    venv_site_packages_path = os.path.join(
        venv_path, "lib", f"python{current_py_hint}", "site-packages"
    )

    venv_python_path = os.path.join(venv_path, "bin")
    command_env = {
        "RIOT_ENV_BASE_PATH": RIOT_TESTS_PATH,
        "PYTHONPATH": venv_python_path,
        "PATH": venv_python_path + ":" + venv_site_packages_path,
        "VENV_PATH": venv_path,
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
        (3.7, 3.7, True),
        (3.7, "3.7", True),
        ("3.7", "3.7", True),
        ("3.7", 3.7, True),
        (3.8, 3.7, False),
        (3.8, "3.7", False),
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
        venv=Venv(name="test", command="echo test"),
        env={"env": "test"},
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


def test_pythonpath_entries_include_inherited_site_packages(
    current_interpreter: Interpreter,
) -> None:
    parent = VenvInstance(
        venv=Venv(command="echo test", pkgs={"pip": ""}),
        env={"env": "test"},
        pkgs={"pip": ""},
        py=current_interpreter,
    )
    venv = VenvInstance(
        venv=Venv(command="uwsgi --version", pkgs={"pytest": ""}),
        env={"env": "test"},
        pkgs={"pytest": ""},
        parent=parent,
        py=current_interpreter,
    )

    assert venv.site_packages_path is not None
    assert venv.pythonpath_entries == [
        str(
            riot_module.get_riot_sitecustomize_bootstrap_path(
                pathlib.Path(venv.site_packages_path)
            )
        ),
        "",
        os.getcwd(),
        parent.site_packages_path,
        current_interpreter.site_packages_path,
    ]


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

    current_interpreter.create_venv(recreate=False, path=str(venv["VENV_PATH"]))

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

    current_interpreter.create_venv(recreate=True, path=str(venv["VENV_PATH"]))

    result = _get_pip_freeze(venv)
    assert result == ""


def test_install_dev_pkg_uses_stable_build_requirements(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text("""
[build-system]
requires = ["meson-python", "ninja>=1.11"]
build-backend = "mesonpy"
""".strip())

    venv_path = tmp_path / "venv"
    venv_path.mkdir()

    calls = []

    def fake_run_cmd_venv(
        cls,
        venv,
        args,
        stdout=subprocess.PIPE,
        executable=None,
        env=None,
    ):
        calls.append((venv, args))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Session, "run_cmd_venv", classmethod(fake_run_cmd_venv))

    install_dev_pkg(str(venv_path), force=True)

    assert len(calls) == 3
    assert calls[0][0] == str(venv_path)
    assert calls[0][1].startswith("pip --disable-pip-version-check install setuptools")
    assert calls[1][0] == str(venv_path)
    assert calls[1][1].startswith("pip --disable-pip-version-check install ")
    assert "meson-python" in calls[1][1]
    assert "ninja>=1.11" in calls[1][1]
    assert (
        calls[2][1]
        == "pip --disable-pip-version-check install --no-build-isolation -e ."
    )
    assert (venv_path / ".riot-dev-pkg-installed").exists()


def test_prepare_bootstraps_existing_deps_venv(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    riot_path = tmp_path / ".riot"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RIOT_ENV_BASE_PATH", str(riot_path))

    inst = VenvInstance(
        venv=Venv(command="echo test", pkgs={"pytest": ""}),
        env={},
        pkgs={"pytest": ""},
        py=Interpreter(current_py_hint),
    )

    requirements_dir = riot_path / "requirements"
    requirements_dir.mkdir(parents=True)
    (requirements_dir / f"{inst.short_hash}.txt").write_text("pytest\n")

    deps_venv_path = pathlib.Path(f"{inst.py.venv_path}_deps")
    deps_venv_path.mkdir(parents=True)

    ensured = []
    created = []
    run_cmd_calls = []

    monkeypatch.setattr(
        riot_module,
        "ensure_riot_site_packages_bootstrap",
        lambda venv_path: ensured.append(venv_path),
    )

    def fake_create_venv(self, recreate, path=None):
        created.append(path or self.venv_path)

    def fake_run_cmd_venv(
        cls,
        venv,
        args,
        stdout=subprocess.PIPE,
        executable=None,
        env=None,
    ):
        run_cmd_calls.append((venv, args))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="")

    monkeypatch.setattr(Interpreter, "create_venv", fake_create_venv)
    monkeypatch.setattr(Session, "run_cmd_venv", classmethod(fake_run_cmd_venv))

    inst.prepare({})

    assert created == []
    assert ensured == [str(deps_venv_path), str(inst.prefix)]
    assert run_cmd_calls == [
        (
            str(deps_venv_path),
            (
                f"pip --disable-pip-version-check install --prefix '{inst.prefix}' "
                f"--no-warn-script-location -r {riot_module.DEFAULT_RIOT_PATH}/requirements/{inst.short_hash}.txt"
            ),
        )
    ]


def test_prepare_bootstraps_existing_deps_venv_when_prefix_is_reused(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    riot_path = tmp_path / ".riot"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RIOT_ENV_BASE_PATH", str(riot_path))

    inst = VenvInstance(
        venv=Venv(command="echo test", pkgs={"pytest": ""}),
        env={},
        pkgs={"pytest": ""},
        py=Interpreter(current_py_hint),
    )

    assert inst.prefix is not None
    pathlib.Path(inst.prefix).mkdir(parents=True)

    deps_venv_path = pathlib.Path(f"{inst.py.venv_path}_deps")
    deps_venv_path.mkdir(parents=True)

    ensured = []

    monkeypatch.setattr(
        riot_module,
        "ensure_riot_site_packages_bootstrap",
        lambda venv_path: ensured.append(venv_path),
    )

    inst.prepare({})

    assert ensured == [str(deps_venv_path), str(inst.prefix)]


def test_site_packages_bootstrap_is_idempotent(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps_site_packages = tmp_path / "deps" / "site-packages"
    deps_site_packages.mkdir(parents=True)
    inherited_site_packages = tmp_path / "inherited" / "site-packages"
    inherited_site_packages.mkdir(parents=True)

    bootstrap_globals: Dict[str, Any] = {
        "__file__": str(deps_site_packages / "_riot_site_packages.py")
    }
    exec(riot_module.RIOT_SITE_PACKAGES_BOOTSTRAP, bootstrap_globals)

    added = []

    def fake_addsitedir(path, known_paths=None):
        added.append(path)
        bootstrap_globals["activate"]()

    monkeypatch.setenv(riot_module.RIOT_SITE_PACKAGES_ENV, str(inherited_site_packages))
    monkeypatch.setattr(bootstrap_globals["site"], "addsitedir", fake_addsitedir)

    bootstrap_globals["activate"]()

    assert added == [str(inherited_site_packages)]


def test_site_packages_bootstrap_discards_imported_modules(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inherited_site_packages = tmp_path / "inherited" / "site-packages"
    inherited_site_packages.mkdir(parents=True)
    (inherited_site_packages / "bootstrap_leak.py").write_text("value = 1\n")
    (inherited_site_packages / "bootstrap_leak.pth").write_text(
        "import bootstrap_leak\n"
    )

    bootstrap_globals: Dict[str, Any] = {
        "__file__": str(inherited_site_packages / "_riot_site_packages.py")
    }
    exec(riot_module.RIOT_SITE_PACKAGES_BOOTSTRAP, bootstrap_globals)

    monkeypatch.setenv(riot_module.RIOT_SITE_PACKAGES_ENV, str(inherited_site_packages))

    bootstrap_globals["activate"]()

    assert "bootstrap_leak" not in sys.modules


def _get_base_env_path() -> str:
    return os.path.abspath(
        os.path.join(
            RIOT_TESTS_PATH,
            "venv_py{}{}{}".format(
                sys.version_info.major,
                sys.version_info.minor,
                sys.version_info.micro,
            ),
        )
    )


def test_session_generate(session_virtualenv: Session) -> None:
    """Validate session, generation of virtualenvs.

    Generate new base venv and validate the virtualenv exists
    """
    venv_path = _get_base_env_path()
    assert os.path.isdir(venv_path)


def test_session_run(session_virtualenv: Session) -> None:
    """Validate session run method.

    Generate new base venv and validate the nested packages.
    """
    session_virtualenv.run(re.compile(""), re.compile(""), False, False)

    env_name = "venv_py%s%s%s_itsdangerous110_isort5101_six1150" % sys.version_info[:3]
    command_env = _get_env(env_name)
    # Check exists and is empty of packages
    result = _get_pip_freeze(command_env)
    regex = r".*isort==5\.10\.1.*itsdangerous==1\.1\.0.*six==1\.15\.0.*"
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
    regex = r".*isort==5\.10\.1.*itsdangerous==0\.24.*six==1\.15\.0.*"
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
    regex = r".*isort==5\.10\.1.*itsdangerous==0\.24.*six==1\.15\.0.*"
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
    regex = r".*isort==5\.10\.1.*itsdangerous==1\.1\.0.*six==1\.15\.0.*"
    expected = re.match(regex, result.replace("\n", ""))
    assert expected, "error: {}".format(result)


def test_requirements_upgrades_compatible_pip_tools(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.chdir(tmp_path)
    calls: List[List[str]] = []

    interpreter = Interpreter("3")
    monkeypatch.setattr(interpreter, "path", lambda: "/fake/python")
    monkeypatch.setattr(interpreter, "version", lambda: "3.14.2")

    def _fake_check_output(cmd: List[str], *args: Any, **kwargs: Any) -> bytes:
        calls.append(cmd)
        if cmd[:4] == ["/fake/python", "-m", "piptools", "compile"]:
            return b"# compiled output\nrequests==2.31.0\n"
        return b""

    monkeypatch.setattr("riot.riot.subprocess.check_output", _fake_check_output)

    venv = VenvInstance(
        venv=Venv(name="test", command="echo test"),
        env={},
        pkgs={"requests": ""},
        py=interpreter,
    )

    _ = venv.requirements

    assert calls[0] == [
        "/fake/python",
        "-m",
        "pip",
        "install",
        "--upgrade",
        "pip<26",
        "pip-tools>=7.5.0,<8",
    ]
