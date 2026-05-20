Configuration
=============


riotfile.py
-----------

riot is configured using a single Python file called ``riotfile.py``. This file
is typically placed in the root directory of the project for ease of access.


A ``riotfile.py`` must define the following:

- ``venv`` a :ref:`Venv` that declares how to build the virtual environments.


.. note::

        By default, riot looks for ``riotfile.py`` in the current directory. It
        can also be named and located differently but then has to be specified
        with the ``--file`` option.


.. _Venv:

Venv
----

.. autoclass:: riot.venv.Venv
   :members:


Environment variables
---------------------

The following environment variables influence riot's behaviour:

``RIOT_PATTERN``
    Default value for the ``pattern`` argument of ``list``, ``run`` and
    ``generate``.

``RIOT_ENV_BASE_PATH``
    Base directory under which virtual environments are created.
    Defaults to ``.riot`` (relative to the current working directory).

``RIOT_PIP_COMPILE_BACKEND``
    Selects the compiler used when generating lockfiles via the
    ``requirements`` command. Supported values:

    - ``piptools`` (default) — invoke ``python -m piptools compile``;
      ``pip-tools`` is auto-installed on demand.
    - ``uv`` — invoke ``uv pip compile``. The ``uv`` executable must
      already be available on ``PATH``; a clear error is raised
      otherwise.

``RIOT_PIP_COMPILE_EXCLUDE_NEWER``
    When set together with ``RIOT_PIP_COMPILE_BACKEND=uv``, the value is
    forwarded to ``uv pip compile`` as ``--exclude-newer=<value>`` so
    that releases published after the given timestamp are not picked up
    during lockfile resolution. Useful for enforcing a supply-chain
    "cooldown" on freshly published transitive dependencies. Ignored
    with a warning when the backend is ``piptools``.
