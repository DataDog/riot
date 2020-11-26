Contributing
============

Development of riot takes place at https://github.com/Datadog/riot.


Formatting
----------

Code formatting is managed with `black <https://github.com/psf/black>`_. To
format code::

        $ riot run fmt


Release notes
-------------

Release notes are managed by `reno <https://docs.openstack.org/reno/latest/>`_.
To create a new release note::

        $ riot run releasenote <slug>

where `<slug>` is a short identifier for the change.


Documentation
-------------

Documentation is published to `readthedocs <https://readthedocs.org/>`_. To
build the docs locally::

        $ riot run docs

To serve the docs locally use::

        $ riot run servedocs

This will serve the docs on port 8000 by default. To specify a different port::

        $ riot run servedocs <port>
