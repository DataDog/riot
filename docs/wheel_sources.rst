Using Pre-built Wheels
======================

By default, riot installs your project in editable mode (``pip install -e .``) when
creating virtual environments. However, you can configure riot to install from
pre-built wheels instead. This is useful for:

- **CI/CD pipelines**: Using pre-built wheels from a previous build step
- **Testing distributions**: Verifying that your built wheels work correctly
- **Faster environment creation**: Avoiding repeated package builds
- **Reproducibility**: Testing with exact wheel artifacts


Specifying a Wheel Path
------------------------

There are two ways to specify a wheel path:


Command-line Option
~~~~~~~~~~~~~~~~~~~

Use the global ``--wheel-path`` option before any subcommand:

.. code-block:: bash

    # With a local directory containing wheels
    riot --wheel-path /path/to/wheels run test

    # With a remote URL (e.g., index.html)
    riot --wheel-path https://example.com/wheels/ generate

    # Works with all commands
    riot --wheel-path /tmp/wheels shell mypy


Environment Variable
~~~~~~~~~~~~~~~~~~~~

Set the ``RIOT_WHEEL_PATH`` environment variable:

.. code-block:: bash

    export RIOT_WHEEL_PATH=/path/to/wheels
    riot run test

This is particularly useful in CI/CD environments where you want to configure
wheel paths without modifying commands.


Package Name Resolution
-----------------------

When using wheel paths, riot needs to know the package name to install. It
determines this automatically by:

1. **Checking the ``RIOT_PACKAGE_NAME`` environment variable** (highest priority)
2. **Parsing ``pyproject.toml``**: Reads the ``[project]`` table's ``name`` field

For projects using ``pyproject.toml`` with a ``[project]`` section, no additional
configuration is needed:

.. code-block:: toml

    [project]
    name = "my-package"
    version = "1.0.0"

For projects not using ``pyproject.toml`` or with custom naming, set the
``RIOT_PACKAGE_NAME`` environment variable:

.. code-block:: bash

    export RIOT_PACKAGE_NAME=my-package
    export RIOT_WHEEL_PATH=/tmp/wheels
    riot run test


How It Works
------------

When a wheel path is specified:

1. **Download**: riot downloads the wheel using ``pip download --no-index --find-links``
   to ensure only wheels from the specified source are used (not PyPI)
2. **Install**: The downloaded wheel is installed into the virtual environment
3. **No Fallback**: If the wheel is not found, riot fails with a clear error message
   (no fallback to editable install)

This ensures reproducibility and prevents accidental use of incorrect package versions.


Example: CI/CD Workflow
-----------------------

A typical CI/CD workflow using wheel paths:

.. code-block:: bash

    # Step 1: Build wheels
    pip wheel --no-deps -w dist/ .

    # Step 2: Run tests with built wheels
    riot --wheel-path dist/ run test

    # Step 3: Verify wheels work in clean environments
    riot --wheel-path dist/ generate --recreate-venvs


Example: Testing with Remote Wheels
------------------------------------

Test against wheels published to a remote location:

.. code-block:: bash

    # Test against wheels on an S3 bucket or web server
    riot --wheel-path https://artifacts.example.com/wheels/v1.2.3/ run test

The wheel path can be any location supported by pip's ``--find-links`` option,
including:

- Local directories (``/path/to/wheels``)
- File URLs (``file:///path/to/wheels``)
- HTTP/HTTPS URLs with index.html (``https://example.com/wheels/``)


Compatibility with Existing Options
------------------------------------

Wheel sources work with all existing riot options:

.. code-block:: bash

    # Recreate environments with wheels
    riot --wheel-path /tmp/wheels run --recreate-venvs test

    # Skip base install (wheels already installed)
    riot --wheel-path /tmp/wheels run --skip-base-install test

    # Generate base environments with wheels
    riot --wheel-path /tmp/wheels generate


Troubleshooting
---------------

**Wheel not found error**:

If you see an error like "Wheel download failed", verify:

- The wheel file exists in the specified location
- The package name matches (check ``RIOT_PACKAGE_NAME`` or ``pyproject.toml``)
- For URLs, the index.html or directory listing is accessible

**Package name cannot be determined**:

If you see "Could not determine package name", either:

- Add a ``[project]`` section with ``name`` field to ``pyproject.toml``
- Set the ``RIOT_PACKAGE_NAME`` environment variable


Environment Variables Reference
--------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Variable
     - Description
   * - ``RIOT_WHEEL_PATH``
     - Path or URL to wheel files. When set, installs from wheels instead of editable mode.
   * - ``RIOT_PACKAGE_NAME``
     - Package name to use when installing from wheels. Overrides automatic detection from ``pyproject.toml``.
