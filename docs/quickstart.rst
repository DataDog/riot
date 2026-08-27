Quickstart
==========

riot is configured with a single Python file typically placed at the root of
your project and named ``riotfile.py``.


Here is a ``riotfile.py`` which defines 5 virtual environment instances. One
defines how to run ``mypy``, another for ``black`` and 3 instances to run tests
with ``pytest``::

        from riot import latest, Venv

        venv = Venv(
            pys=[3.9],
            venvs=[
                Venv(
                    name="fmt",
                    command="black .",
                    pkgs={
                        "black": "==20.8b1",
                    },
                ),
                Venv(
                    name="mypy",
                    command="mypy",
                    pkgs={
                        "mypy": latest,
                    },
                ),
                Venv(
                    name="test",
                    pys=["3.8", "3.9"],
                    command="pytest",
                    pkgs={
                        "pytest": latest,
                    },
                ),
            ],
        )


To run an instance the ``run`` command can be used which will run all instances
with a ``name`` matching the argument:

.. code-block:: bash

        $ riot run fmt

will run the first instance which is the command ``black .`` in a Python 3.9
virtual environment with ``black`` version ``20.8b1`` installed.


To view all the instances that are produced use the ``list`` command:

.. code-block:: bash

        $ riot list
        fmt  Python 3.9 'black==20.8b1'
        mypy  Python 3.9 'mypy'
        test  Python 3.8 'pytest'
        test  Python 3.9 'pytest'


The ``black`` and ``mypy`` instances will be run with Python 3.9 and the
``pytest`` instance will be run in Python 3.8 and 3.9.


Using Pre-built Wheels
----------------------

By default, riot installs your project in editable mode (``pip install -e .``).
If you want to test with pre-built wheels instead, use the ``--wheel-path`` option:

.. code-block:: bash

        $ pip wheel --no-deps -w dist/ .
        $ riot --wheel-path dist/ run test

See :doc:`wheel_sources` for more details on using pre-built wheels.


Overriding the Command
-----------------------

Each venv instance runs the command it was configured with. To run a
different command inside a matching venv without changing ``riotfile.py``,
pass ``--command`` to ``run``:

.. code-block:: bash

        $ riot run --command "mypy --strict" test

The override replaces the venv's ``command`` entirely, but still benefits
from the venv's dependencies and environment setup, including
``--pass-env`` and any environment variables declared on the ``Venv``.
Instances with no ``command`` of their own are otherwise skipped, but will
still run when ``--command`` is given.

As with a venv's regular command, ``{cmdargs}`` in the override is replaced
with any extra arguments passed after ``--``:

.. code-block:: bash

        $ riot run --command "pytest {cmdargs}" test -- -k test_foo

This is useful for running external tooling (e.g. a separate test runner)
inside a riot venv so that it inherits the venv's full environment without
having to reconstruct riot's activation logic itself.

