from riot import Venv

venv = Venv(
    name="lvl_1",
    pkgs={
        "itsdangerous": "==1.1.0",
    },
    env={
        "ENV_LVL": "1",
    },
    venvs=[
        Venv(
            pys=["3"],
            name="lvl_2",
            create=True,
            pkgs={
                "isort": "==5.10.1",
            },
            env={
                "ENV_LVL": "2",
            },
            venvs=[
                Venv(
                    name="lvl_3_1",
                    create=True,
                    pkgs={
                        "six": "==1.16.0",
                    },
                    env={
                        "ENV_LVL": "3",
                    },
                    command="python -c 'print(\"lvl_3_1\")'",
                ),
                Venv(
                    name="lvl_3_2",
                    create=True,
                    pkgs={
                        "six": "==1.15.0",
                    },
                    env={
                        "ENV_LVL": "3",
                    },
                    command="python -c 'print(\"lvl_3_2\")'",
                ),
            ],
        )
    ],
)
