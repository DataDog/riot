from riot import latest, Venv

venv = Venv(
    pys=3,
    venvs=[
        Venv(
            name="test",
            command="pytest {cmdargs}",
            pys=["3.6", "3.7", "3.8", "3.9", "3.10"],
            pkgs={
                "pytest": latest,
                "pytest-cov": latest,
                "mock": latest,
                "typing-extensions": latest,
            },
        ),
        Venv(
            pkgs={
                "black": "==20.8b1",
            },
            venvs=[
                Venv(
                    name="black",
                    command="black {cmdargs}",
                ),
                Venv(
                    name="fmt",
                    command="black .",
                ),
            ],
        ),
        Venv(
            name="flake8",
            command="flake8 {cmdargs}",
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
            name="mypy",
            command="mypy --install-types --non-interactive {cmdargs}",
            pkgs={
                "mypy": latest,
                "pytest": latest,
            },
            create=True,
        ),
        Venv(
            pys=[3],
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
        Venv(
            name="servedocs",
            command="python -m http.server --directory docs/_build {cmdargs}",
        ),
        Venv(
            pkgs={
                "reno": latest,
            },
            venvs=[
                Venv(
                    name="releasenote",
                    command="reno new --edit {cmdargs}",
                ),
                Venv(
                    name="reno",
                    command="reno {cmdargs}",
                ),
            ],
        ),
    ],
)
