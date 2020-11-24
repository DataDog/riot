from riot import Venv

venv = Venv(
    pys=[3.8],
    venvs=[
        Venv(
            name="test",
            command="pytest --color=yes --cov=riot/ --cov=tests/ --cov-append --cov-report= {cmdargs} tests/",
            env={
                "LC_ALL": ["C.UTF-8"],
                "LANG": ["C.UTF-8"],
            },
            pys=[3.6, 3.7, 3.8, 3.9],
            pkgs={
                "pytest": [""],
                "pytest-cov": [""],
                "mock": [""],
            },
        ),
        Venv(
            name="check_format",
            command="black --check .",
            pkgs={
                "black": ["==20.8b1"],
            },
        ),
        Venv(
            name="flake8",
            command="flake8",
            pkgs={
                "flake8": [""],
                "flake8-blind-except": [""],
                "flake8-builtins": [""],
                "flake8-docstrings": [""],
                "flake8-logging-format": [""],
                "flake8-rst-docstrings": [""],
                # needed for some features from flake8-rst-docstrings
                "pygments": [""],
            },
        ),
        Venv(
            name="typing",
            command="mypy",
            pkgs={
                "mypy": [""],
                "pytest": [""],
            },
        ),
    ],
)
