from riot import Venv

venv = Venv(
    venvs=[
        Venv(name="job_{}".format(i), command="exit 0", pys=["3"]) for i in range(15)
    ]
)
