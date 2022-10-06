from riot import Venv

venv = Venv(
    venvs=[
        Venv(
            name="test",
            command="exit 0",
            pys=["2.7", "3.5", "3.6", "3.7", "3.8", "3.9"],
            venvs=[
                Venv(pkgs={"pytest": ["==5.4.3", ""]},),
            ],
        ),
    ]
)
