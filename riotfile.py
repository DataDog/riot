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
            name="typing",
            command="mypy riot/ tests/",
            pkgs={
                "mypy": [""],
                "pytest": [""],
            },
        ),
    ],
)
