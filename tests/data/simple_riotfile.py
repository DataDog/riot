from riot import Task, Venv

venv = Venv(
    venvs=[
        Venv(
            venvs=[
                Venv(
                    pkgs={
                        "pytest": ["==5.4.3", ""],
                    },
                    pys=[3],
                ),
            ],
        ),
    ]
)


tasks = [
    Task(
        name="test",
        command="echo hello",
        venvs=[venv],
    ),
]
