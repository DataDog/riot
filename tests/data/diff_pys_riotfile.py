from riot import Venv

venv = Venv(
    venvs=[
        Venv(
            name="test",
            command="exit 0",
            pys=["3.5", "3.8", "3.6", "3.9", "3.7", "2.7"],
            venvs=[
                Venv(
                    pkgs={"pytest": ["==5.4.3", ""]},
                ),
            ],
        ),
    ]
)
