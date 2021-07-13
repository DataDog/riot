from riot import Task, Venv, latest

black_venv = Venv(
    pys=[3],
    pkgs={
        "black": "==20.8b1",
    },
)

checks = [
    Task(
        name="black",
        command="black {cmdargs}",
        venvs=[black_venv],
    ),
    Task(
        name="fmt",
        command="black .",
        venvs=[black_venv],
    ),
    Task(
        name="flake8",
        command="flake8 {cmdargs}",
        venvs=[
            Venv(
                pys=[3],
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
        ],
    ),
    Task(
        name="mypy",
        command="mypy --install-types --non-interactive --show-error-codes {cmdargs}",
        venvs=[
            Venv(
                pys=[3],
                pkgs={
                    "mypy": latest,
                    "pytest": latest,
                },
            ),
        ],
    ),
    Task(
        name="codecov",
        command="bash <(curl -s https://codecov.io/bash)",
        venvs=[
            Venv(
                pys=[3],
                pkgs={
                    "coverage": latest,
                },
            )
        ],
    ),
]

tests = [
    Task(
        name="test",
        command="pytest {cmdargs}",
        venvs=[
            Venv(
                pkgs={
                    "click": latest,
                    "pytest": latest,
                    "pytest-cov": latest,
                    "mock": latest,
                    "typing-extensions": latest,
                },
                venvs=[
                    Venv(
                        pys=[3.6],
                        pkgs={
                            "dataclasses": latest,
                        },
                    ),
                    Venv(
                        pys=[3.7, 3.8, 3.9],
                    ),
                ],
            ),
        ],
    ),
]

reno_venv = Venv(
    pys=[3],
    pkgs={
        "reno": latest,
    },
)

docs = [
    Task(
        name="docs",
        command="sphinx-build {cmdargs} -W -b html docs docs/_build/",
        venvs=[
            Venv(
                pys=[3],
                pkgs={
                    "click": latest,
                    "sphinx": "==3.3",
                    "sphinx-rtd-theme": "==0.5.0",
                    "sphinx-click": "==2.5.0",
                    "reno": latest,
                },
            )
        ],
    ),
    Task(
        name="servedocs",
        command="python -m http.server --directory docs/_build {cmdargs}",
        venvs=[Venv(pys=[3])],
    ),
    Task(
        name="releasenote",
        command="reno new --edit {cmdargs}",
        venvs=[reno_venv],
    ),
    Task(
        name="reno",
        command="reno {cmdargs}",
        venvs=[reno_venv],
    ),
]

tasks = checks + tests + docs
