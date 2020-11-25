from riot import Venv

venv = Venv(
    venvs=[
        Venv(
            name="test",
            command="exit 0",
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
