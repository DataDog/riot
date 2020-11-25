from riot import latest, Venv

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
                "pytest": latest,
                "pytest-cov": latest,
                "mock": latest,
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
                "flake8": latest,
                "flake8-blind-except": latest,
                "flake8-builtins": latest,
                "flake8-docstrings": latest,
                "flake8-import-order": latest,
                "flake8-logging-format": latest,
                "flake8-rst-docstrings": latest,
                # needed for some features from flake8-rst-docstrings
                "pygments": latest,
            },
        ),
        Venv(
            name="typing",
            command="mypy",
            pkgs={
                "mypy": latest,
                "pytest": latest,
            },
        ),
        Venv(
            pys=[3.6, 3.7, 3.8, 3.9],
            name="codecov",
            command="bash <(curl -s https://codecov.io/bash)",
            pkgs={
                "coverage": latest,
            },
        ),
        Venv(
            name="docs",
            command="sphinx-build {cmdargs} -W -b html docs docs/_build/",
            pkgs={
                "sphinx": "==3.3",
                "sphinx-rtd-theme": "==0.5.0",
                "sphinx-click": "==2.5.0",
                "reno": latest,
            },
        ),
    ],
)
