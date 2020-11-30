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

.. autoclass:: riot.riot.Venv
   :members:
