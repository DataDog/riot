import io
import re

from riot.riot import Session, Venv


def test_venv_pythonpath(temp_dir: str, current_venv: Venv):
    current_venv.command = (
        "python -c 'import json,site; print(json.dumps(site.getsitepackages()))'"
    )
    session = Session(venv=current_venv)

    pattern = re.compile(r".*")
    session.run(pattern, pattern, skip_base_install=True)
    import pdb

    pdb.set_trace()
    pass
