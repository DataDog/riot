from riot import Venv

venv = Venv(
    pys=3.8,
    venvs=[
        Venv(
            name="test",
            command="pytest {cmdargs}",
            env={
                "LC_ALL": "C.UTF-8",
                "LANG": "C.UTF-8",
            },
            pys=[3.6, 3.7, 3.8, 3.9],
            pkgs={
                "pytest": "",
                "pytest-cov": "",
                "mock": "",
            },
        ),
        Venv(
            name="check_format",
            command="black --check .",
            pkgs={
                "black": "==20.8b1",
            },
        ),
        Venv(
            name="flake8",
            command="flake8",
            pkgs={
                "flake8": "",
                "flake8-blind-except": "",
                "flake8-builtins": "",
                "flake8-docstrings": "",
                "flake8-import-order": "",
                "flake8-logging-format": "",
                "flake8-rst-docstrings": "",
                # needed for some features from flake8-rst-docstrings
                "pygments": "",
            },
        ),
        Venv(
            name="typing",
            command="mypy",
            pkgs={
                "mypy": "",
                "pytest": "",
            },
        ),
        Venv(
            pys=[3.6, 3.7, 3.8, 3.9],
            name="codecov",
            command="bash <(curl -s https://codecov.io/bash)",
            pkgs={
                "coverage": "",
            },
        ),
        Venv(
            name="docs",
            command="sphinx-build -W -b html docs docs/_build/",
            pkgs={
                "sphinx": "==3.3",
                "reno": "",
            },
        ),
    ],
)
