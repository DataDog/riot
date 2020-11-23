from riot import Venv

venvs = [
    Venv(
        name="test",
        command="pytest --color=yes tests/",
        env={
            "LC_ALL": ["C.UTF-8"],
            "LANG": ["C.UTF-8"],
        },
        pys=[3.6, 3.7, 3.8, 3.9],
        pkgs={
            "pytest": [""],
            "mock": [""],
        },
    ),
    Venv(
        name="check_format",
        command="black --check .",
        pys=[3.8],
        pkgs={
            "black": ["==20.8b1"],
        },
    ),
    Venv(
        name="typing",
        command="mypy riot/ tests/",
        pys=[3.8],
        pkgs={
            "mypy": [""],
            "pytest": [""],
        },
    ),
]
