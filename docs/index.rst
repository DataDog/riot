.. toctree::
   :maxdepth: 2
   :hidden:

   self
   quickstart
   configuration
   wheel_sources
   usage
   release_notes
   contributing


riot
====

riot is a tool for declaratively constructing Python virtual environments to
run commands in. It can be used to run one-off commands like ``mypy`` or it can
be used to test large test matrices with ease.


System Requirements
-------------------

riot supports CPython 3.8+.


Installation
------------

riot can be installed from PyPI with::

        pip install riot


.. note::
   riot does not yet have a stable API so it is recommended to pin the riot
   version to avoid having to deal with breaking changes.
