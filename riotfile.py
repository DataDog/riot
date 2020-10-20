from riot import Case, Suite

global_deps = [
    "mock",
    "pytest",
]

global_env = [("PYTEST_ADDOPTS", "--color=yes")]

suites = [
    Suite(
        name="test",
        command="pytest tests/",
        cases=[
            Case(
                env=[("LC_ALL", ["C.UTF-8"]), ("LANG", ["C.UTF-8"])],
                pys=[3.6, 3.7, 3.8, 3.9],
                pkgs=[],
            ),
        ],
    ),
    Suite(
        name="check_format",
        command="black --check .",
        cases=[
            Case(
                pys=[3.8],
                pkgs=[("black", ["==20.8b1"])],
            ),
        ],
    ),
    Suite(
        name="typing",
        command="mypy riot/ tests/",
        cases=[
            Case(
                pys=[3.8],
                pkgs=[("mypy", [""])],
            ),
        ],
    ),
]
