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
                    pys=["3.7", "3.8", "3.9"],
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
        test  Python 3.7 'pytest'
        test  Python 3.8 'pytest'
        test  Python 3.9 'pytest'


The ``black`` and ``mypy`` instances will be run with Python 3.9 and the
``pytest`` instance will be run in Python 3.7, 3.8 and 3.9.

