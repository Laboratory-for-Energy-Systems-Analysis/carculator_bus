.. _install:

Installation
============

Python Version
--------------
``carculator_bus`` requires Python 3.12 (``>=3.12,<3.13``).
Because ``carculator_bus`` is still at an early development stage, we recommend installing it in a separate environment.

Using Conda environment
-----------------------

Create a conda environment:

.. code-block:: bash

    conda create -n <name of the environment> python=3.12

Once your environment created, you should activate it:

.. code-block:: bash

    conda activate <name of the environment>

And install the ``carculator_bus`` library in your new environment via Conda:

.. code-block:: bash

    conda install -c romainsacchi carculator_bus

Using Pip
---------

Use the following command to install the ``carculator_bus`` via ``pip``:

.. code-block:: bash

    pip install carculator_bus

.. note:: This will install the package and the required dependencies.

How to update this package?
---------------------------

Within the conda environment, type:

.. code-block:: bash

    conda update carculator_bus

Or from Pypi using pip:

.. code-block:: bash

    pip install carculator_bus --upgrade